"""C 级视觉验收（#160）：playtest 成功后用平台视觉模型判截图是否贴合设计意图。

定位与边界：
- B 级（动效冒烟）仍是唯一硬门禁；本模块只产出 warning，不改 qa_ok、不阻断 promote。
- 配置来自 admin 后台的平台视觉模型（未配置即整体跳过），用户侧零配置。
- 任何失败（超时 / HTTP 错误 / 空 content / 坏 JSON）一律降级为跳过，绝不抛出。
- prompt 协议必须「先客观描述、再比对」：直接把期望答案塞给弱模型会被锚定复述。
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from app.core.config import settings

log = logging.getLogger(__name__)

_SYSTEM = (
    "You are a visual QA reviewer for a game build screenshot. "
    "First describe objectively what you see (background brightness, dominant "
    "colors, key UI elements and their positions), THEN compare it with the "
    "design brief. Only report mismatches you can actually see in the image; "
    "do not invent details."
)

_INSTRUCTION = (
    "Compare the screenshot with the design brief below.\n"
    "Reply ONLY with JSON, no markdown fence:\n"
    '{"observed":{"background":"light"|"dark","summary":"<one sentence>",'
    '"elements":[{"label":str,"position":"left"|"center"|"right"}]},'
    '"checks":{"theme":true|false,"layout":true|false,'
    '"style":true|false,"content":true|false},'
    '"confidence":0-1,'
    '"issues":[{"kind":"theme|layout|style|content","severity":"low|medium|high",'
    '"detail":"<one sentence>"}]}\n'
    "Work strictly left to right: first fill observed.elements by locating each "
    "key UI element and labeling its position as the third of the screen width "
    "it sits in (left / center / right). Then judge each check USING those "
    "observations: theme = overall light/dark and palette; layout = each "
    "element the brief places on a specific side actually sits in that third "
    "(a check is false only if an element is clearly in a different third or "
    "missing); style = art direction look; content = required title/elements "
    "present. Every false check MUST also appear in issues. If everything "
    "matches, all checks are true and issues is empty."
)

_KINDS = ("theme", "layout", "style", "content")
_SEVERITIES = ("low", "medium", "high")


def build_visual_brief(design_doc: dict[str, Any], art_direction: dict[str, Any]) -> str:
    """从设计稿/美术方向压缩出短 brief：只保留视觉模型能「看见」的意图。"""
    parts: list[str] = []
    title = str(design_doc.get("title") or "").strip()
    if title:
        parts.append(f"Title: {title}")
    presentation = design_doc.get("presentation") or {}
    visual_style = str(presentation.get("visual_style") or "").strip()
    if visual_style:
        parts.append(f"Visual style: {visual_style}")
    overview = design_doc.get("overview") or {}
    if str(overview.get("genre") or "").strip():
        parts.append(f"Genre: {overview['genre']}")
    if str(overview.get("target_experience") or "").strip():
        parts.append(f"Target experience: {overview['target_experience']}")
    if art_direction:
        clipped = json.dumps(art_direction, ensure_ascii=False)
        if len(clipped) > 600:
            clipped = clipped[:600] + "…"
        parts.append(f"Art direction: {clipped}")
    return "\n".join(parts) or "No explicit style intent declared."


def _as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in ("true", "false"):
        return value.strip().lower() == "true"
    return None


def parse_verdict(content: str) -> dict[str, Any] | None:
    """解析判定 JSON；容忍 ```json 围栏与轻度字段越界，坏输出返回 None。"""
    text = (content or "").strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text[:4].lower() == "json":
            text = text[4:].strip()
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    raw_checks_obj = data.get("checks")
    raw_checks = raw_checks_obj if isinstance(raw_checks_obj, dict) else {}
    checks = {
        key: value
        for key, value in (
            (key, _as_bool(raw_checks.get(key))) for key in ("theme", "layout", "style", "content")
        )
        if value is not None
    }
    match = _as_bool(data.get("match"))
    if match is None:
        match = all(checks.values()) if checks else None
    if match is None:
        return None

    issues: list[dict[str, str]] = []
    raw_issues = data.get("issues")
    for item in raw_issues if isinstance(raw_issues, list) else []:
        if not isinstance(item, dict):
            continue
        detail = str(item.get("detail") or "").strip()
        if not detail:
            continue
        kind = str(item.get("kind") or "style")
        severity = str(item.get("severity") or "low")
        issues.append(
            {
                "kind": kind if kind in _KINDS else "style",
                "severity": severity if severity in _SEVERITIES else "low",
                "detail": detail[:200],
            }
        )

    try:
        confidence = max(0.0, min(1.0, float(data.get("confidence", 0.5))))
    except (TypeError, ValueError):
        confidence = 0.5
    raw_observed = data.get("observed")
    observed = raw_observed if isinstance(raw_observed, dict) else {}
    elements = [
        {
            "label": str(e.get("label") or "")[:60],
            "position": str(e.get("position") or "")[:10],
        }
        for e in (observed.get("elements") or [])[:8]
        if isinstance(e, dict) and e.get("label")
    ]
    return {
        "match": match,
        "checks": checks,
        "confidence": confidence,
        "observed": {
            "background": str(observed.get("background") or "")[:40],
            "summary": str(observed.get("summary") or "")[:200],
            "elements": elements,
        },
        "issues": issues[:5],
    }


async def evaluate_visual_acceptance(
    db: Any,
    png: bytes,
    design_doc: dict[str, Any],
    art_direction: dict[str, Any],
) -> dict[str, Any] | None:
    """对一张试玩截图跑 C 级视觉判定；未配置/失败/坏输出 → None（跳过，绝不抛出）。"""
    try:
        if not png:
            return None
        from app.admin.services import get_visual_llm_config

        cfg = await get_visual_llm_config(db)
        if not (cfg["enabled"] and cfg["model"] and cfg["apikey"]):
            return None

        from app.enums import LLMProvider
        from app.llm import provider as llm_provider
        from app.llm.platform_complete import platform_complete

        brief = build_visual_brief(design_doc, art_direction)
        user_msg: list[dict[str, Any]] = [
            {"type": "text", "text": f"Design brief:\n{brief}\n\n{_INSTRUCTION}"},
            llm_provider.image_content_part(png),
        ]
        content, _usage = await asyncio.wait_for(
            platform_complete(
                LLMProvider(cfg["provider"]),
                cfg["apikey"],
                cfg["model"],
                _SYSTEM,
                user_msg,
                kind="visual_acceptance",
                base_url=cfg["base_url"].strip() or None,
                max_tokens=settings.visual_acceptance_max_tokens,
                read_timeout_s=settings.visual_acceptance_timeout_s,
                tags=["forge", "qa"],
            ),
            timeout=settings.visual_acceptance_timeout_s + 5,
        )
        if not (content or "").strip():
            # 推理模型 thinking 可能吃光 max_tokens（HTTP 200 假成功）→ 视为跳过
            log.warning("visual acceptance returned empty content, skipped")
            return None
        verdict = parse_verdict(content)
        if verdict is not None:
            conflict = _layout_conflict(brief, verdict.get("observed", {}).get("elements") or [])
            if conflict:
                verdict["layout_conflict"] = conflict
        return verdict
    except Exception:  # noqa: BLE001 软验收：任何失败都只降级跳过
        log.warning("visual acceptance failed, skipped", exc_info=True)
        return None


_SIDE_WORDS: dict[str, tuple[str, ...]] = {
    "left": ("left", "左侧", "左边", "左方"),
    "center": ("center", "居中", "中间", "中部"),
    "right": ("right", "右侧", "右边", "右方"),
}


def _layout_hints(brief: str) -> list[tuple[str, str]]:
    """brief 中明确提到方位的句子 → (句子, 期望侧)。仅识别确定性方位词。"""
    hints: list[tuple[str, str]] = []
    for sent in re.split(r"[。;\n.；]", brief or ""):
        low = sent.lower()
        for side, words in _SIDE_WORDS.items():
            if any(w in low for w in words):
                hints.append((sent.strip(), side))
                break
    return hints


def _match_element(sentence: str, elements: list[dict[str, str]]) -> dict[str, str] | None:
    """在 observed.elements 里找与本句词汇重合的元素（英文词≥4 字符或中文二元组）。"""
    low_sent = sentence.lower()
    sent_words = re.findall(r"[a-z]{4,}", low_sent)
    for el in elements:
        label = str(el.get("label") or "").lower()
        if not label:
            continue
        if any(w in label for w in sent_words):
            return el
        # 中文按二元组重合匹配（英文二元组太松：art/board 会撞车）
        for i in range(len(sentence) - 1):
            pair = sentence[i : i + 2]
            if (
                "\u4e00" <= pair[0] <= "\u9fff"
                and "\u4e00" <= pair[1] <= "\u9fff"
                and pair in label
            ):
                return el
    return None


def _layout_conflict(brief: str, elements: list[dict[str, str]]) -> tuple[str, str, str] | None:
    """确定性布局比对：brief 声明方位的元素 vs 模型提取的实际位置。

    模型提取元素位置实测稳定（远稳于其自判 layout 布尔），比对放代码里做：
    (元素 label, 期望侧, 实际侧)。找不到对应元素不判，宁漏勿误报。
    """
    for sent, side in _layout_hints(brief):
        el = _match_element(sent, elements)
        actual = str(el.get("position") or "") if el else ""
        if el and actual and actual != side:
            return (el["label"], side, actual)
    return None


def warning_lines(verdict: dict[str, Any] | None) -> list[str]:
    """判定 → 人类可读 warning 列表。

    以 issues 为准而不是聚合 match 布尔值：实测模型可能在列出具体
    不符项的同时仍给 match=true，丢弃 issues 会漏报真实漂移。
    """
    if not verdict:
        return []
    conflict = verdict.get("layout_conflict")
    # 模型自判 layout 布尔实测不稳（漏报+误报并存）：layout 类只信代码确定性比对
    lines = [
        f"[{issue['kind']}/{issue['severity']}] {issue['detail']}"
        for issue in (verdict.get("issues") or [])[:5]
        if issue["kind"] != "layout"
    ]
    if conflict:
        label, expected, actual = conflict
        lines.append(
            f"[layout/high] brief places '{label}' on the {expected}, "
            f"but the render shows it on the {actual}"
        )
    if not lines:
        failed = [
            k for k, v in (verdict.get("checks") or {}).items() if v is False and k != "layout"
        ]
        summary = str((verdict.get("observed") or {}).get("summary") or "").strip()
        suffix = f" ({summary[:80]})" if summary else ""
        if failed:
            lines = [
                f"[{k}/medium] render fails the {k} check against the design brief{suffix}"
                for k in failed[:4]
            ]
        elif verdict.get("match") is False and not verdict.get("checks"):
            # 仅旧格式（无分维度 checks）才用通用兜底：结构化判定里 layout-only
            # 的 match=false 已被丢弃，再兜底会把误报引回来
            lines.append(f"[style/low] render does not match the design brief{suffix}")
    return lines


def visual_warning_block(state: dict[str, Any]) -> str:
    """repair prompt 的视觉警告段：来自上一次成功试玩的视觉验收结果。"""
    warnings = [str(w).strip() for w in (state.get("visual_warnings") or []) if str(w).strip()]
    if not warnings:
        return ""
    lines = "\n".join(f"- {w}" for w in warnings[:5])
    return (
        "【视觉验收警告（上一轮试玩截图与设计稿不符；若与本次修改目标不冲突，请一并修正）】\n"
        f"{lines}"
    )
