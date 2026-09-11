"""偏好抽取（ADR-16 §4 操作式协议）：模型只建议操作，服务层裁决。

与旧版（自由 category/key 列表）的关键差异：
- 输入带现有活跃偏好摘要（4 字段投影）与目录清单，模型据此决定 set/remove/touch；
- 契约区分长期偏好与当前任务指令（"这次简单点"不是偏好）；
- 输出操作候选仍需经 Preference Service 的目录/类型校验与合并策略，模型不直接写库。
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.core.config import settings
from app.forge.memory.catalog import PREFERENCE_CATALOG

log = logging.getLogger(__name__)


def _catalog_digest() -> str:
    lines = []
    for key, slot in sorted(PREFERENCE_CATALOG.items()):
        lines.append(f"{key}: {'|'.join(slot.values)}")
    return "\n".join(lines)


def _system_prompt() -> str:
    return (
        "你是用户游戏创作偏好管理器。根据用户消息与现有偏好，输出操作建议。\n"
        "规则：\n"
        "1. 只记录长期偏好；『这次/本局/暂时/仅本次』等当前任务指令不是偏好，"
        "输出空 operations。\n"
        "2. key 必须从下列目录选择，禁止发明：\n" + _catalog_digest() + "\n"
        "3. op 语义：set=新增或更新偏好；remove=用户明确否定某条已有偏好"
        "（如『别再默认暗色』）；touch=用户重申的内容与现有值相同，仅刷新。\n"
        "4. source：用户明确声明长期偏好用 explicit（confidence>=0.9）；"
        "弱信号推断用 inferred（confidence<=0.7）。\n"
        '5. 只输出 JSON（无围栏）：{"operations":[{"op":"set","key":"…",'
        '"value":"…","source":"…","confidence":0.0}]}；无操作输出 {"operations":[]}。'
    )


def preference_extract_configured() -> bool:
    return bool(
        settings.preference_extract_enabled
        and settings.preference_extract_model.strip()
        and settings.preference_extract_apikey.strip()
    )


def _parse_operations(content: str) -> list[dict[str, Any]]:
    text = (content or "").strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text[:4].lower() == "json":
            text = text[4:].strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    rows = data.get("operations") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        return []
    out: list[dict[str, Any]] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        op = str(item.get("op") or "").strip().lower()
        if op not in ("set", "remove", "touch"):
            continue
        out.append(
            {
                "op": op,
                "key": str(item.get("key") or "").strip(),
                "value": item.get("value"),
                "source": str(item.get("source") or "inferred").strip().lower(),
                "confidence": item.get("confidence", 0.5),
            }
        )
    return out


async def extract_preference_operations(
    text: str, current_prefs: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """调平台模型输出操作候选；未配置或失败返回 []（不写偏好）。"""
    raw = (text or "").strip()
    if not raw or not preference_extract_configured():
        return []
    from app.enums import LLMProvider
    from app.llm.platform_complete import platform_complete

    prefs_json = json.dumps(current_prefs, ensure_ascii=False)
    user_msg = f"【用户消息】\n{raw}\n\n【现有偏好】\n{prefs_json}"
    try:
        content, _usage = await platform_complete(
            LLMProvider(settings.preference_extract_provider),
            settings.preference_extract_apikey.strip(),
            settings.preference_extract_model.strip(),
            _system_prompt(),
            user_msg,
            kind="preference_extract",
            base_url=settings.preference_extract_base_url.strip() or None,
            max_tokens=512,
            tags=["forge", "memory"],
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("preference extract LLM failed: %s", type(exc).__name__)
        return []
    return _parse_operations(content)
