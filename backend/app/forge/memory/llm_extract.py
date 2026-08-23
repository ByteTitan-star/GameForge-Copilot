"""偏好 LLM 抽取（ADR-06）：正式路径禁止规则引擎。"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.core.config import settings

log = logging.getLogger(__name__)

_SYSTEM = (
    "你是用户游戏创作偏好抽取器。从用户消息中抽取长期偏好（非一次性本次需求）。\n"
    '只输出 JSON：{"preferences":[{"category":str,"key":str,'
    '"value_json":object,"source":"explicit"|"inferred","confidence":0-1}]}\n'
    '无偏好时 {"preferences":[]}。\n'
    "explicit=用户明确声明长期偏好；inferred=弱信号推断。不要编造。"
)


def preference_extract_configured() -> bool:
    """判断偏好 LLM 抽取是否已完整配置。

    场景：``extract_preferences_via_llm`` 调用前检查开关与凭据。
    参数：无。
    返回：enabled、model、apikey 均非空时为 True。
    """
    return bool(
        settings.preference_extract_enabled
        and settings.preference_extract_model.strip()
        and settings.preference_extract_apikey.strip()
    )


async def extract_preferences_via_llm(text: str) -> list[dict[str, Any]]:
    """调用轻量 chat 从用户消息抽取长期偏好。

    场景：``upsert_preferences_from_text`` 正式抽取路径（ADR-06）。
    参数：text - 用户消息文本。
    返回：偏好 dict 列表；未配置或失败时返回 []（不写偏好）。
    """
    raw = (text or "").strip()
    if not raw or not preference_extract_configured():
        return []
    from app.enums import LLMProvider
    from app.llm.platform_complete import platform_complete

    try:
        content, _usage = await platform_complete(
            LLMProvider(settings.preference_extract_provider),
            settings.preference_extract_apikey.strip(),
            settings.preference_extract_model.strip(),
            _SYSTEM,
            raw,
            kind="preference_extract",
            base_url=settings.preference_extract_base_url.strip() or None,
            max_tokens=512,
            tags=["forge", "memory"],
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("preference extract LLM failed: %s", type(exc).__name__)
        return []
    return _parse_preferences(content)


def _parse_preferences(content: str) -> list[dict[str, Any]]:
    """解析 LLM 返回的偏好 JSON 并校验字段。

    场景：``extract_preferences_via_llm`` 解析 LLM 响应。
    参数：content - LLM 原始响应文本。
    返回：校验通过的偏好 dict 列表；解析失败返回 []。
    """
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    rows = data.get("preferences") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        return []
    out: list[dict[str, Any]] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        category = str(item.get("category") or "").strip()
        key = str(item.get("key") or "").strip()
        value_json = item.get("value_json")
        if not category or not key or not isinstance(value_json, dict):
            continue
        source = str(item.get("source") or "inferred").strip().lower()
        if source not in ("explicit", "inferred"):
            source = "inferred"
        conf = float(item.get("confidence") or (0.8 if source == "explicit" else 0.4))
        conf = max(0.0, min(1.0, conf))
        out.append(
            {
                "category": category,
                "key": key,
                "value_json": value_json,
                "source": source,
                "confidence": conf,
                "status": "active",
            }
        )
    return out
