"""Forge 游戏设计稿 v2 的解析、兼容归一化与结构校验。

v2 保留旧版 ``title/gameplay/controls/levels`` 四个顶层字段，旧前端和历史
数据仍可读取；新增字段为游戏生成、自动试玩和定向修复提供可执行规格。
"""

from __future__ import annotations

import copy
import json
from typing import Any

SCHEMA_VERSION = "2.0"
REQUIRED_STATE_IDS = {
    "menu",
    "playing",
    "paused",
    "level_complete",
    "game_over",
    "victory",
}


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    return default


def _text_list(value: Any) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        text = _text(item)
        if text:
            result.append(text)
    return result


def _dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [copy.deepcopy(item) for item in value if isinstance(item, dict)]


def _empty_doc(title: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "title": title or "未命名游戏",
        "gameplay": "",
        "controls": [],
        "levels": [],
        "overview": {
            "genre": "",
            "target_experience": "",
            "session_length": "",
            "scope": "单个离线 index.html 可实现的完整游戏原型",
            "assumptions": [],
        },
        "core_loop": [],
        "rules": {
            "objectives": [],
            "win_conditions": [],
            "lose_conditions": [],
            "scoring": [],
            "progression": [],
        },
        "game_states": [],
        "entities": [],
        "level_specs": [],
        "ui": {"screens": [], "hud": [], "feedback": [], "instructions": []},
        "presentation": {
            "visual_style": "",
            "color_palette": [],
            "asset_needs": [],
            "effects": [],
        },
        "technical_constraints": [
            "单个 index.html、离线运行、无外部依赖、无网络请求",
            "同时支持键盘和触控操作",
            "画面随视口自适应且核心玩法区域保持可见",
        ],
        "acceptance_criteria": [],
    }


def _decode_json(value: str) -> dict[str, Any] | None:
    text = value.strip()
    if text.startswith("```"):
        first_newline = text.find("\n")
        text = text[first_newline + 1 :] if first_newline >= 0 else text[3:]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3].rstrip()
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        # 兼容模型偶发添加的一句前后缀；只抽取最外层 JSON 对象一次。
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            parsed = json.loads(text[start : end + 1])
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None


def _legacy_controls(value: Any) -> list[str]:
    if not isinstance(value, list):
        return _text_list(value)
    controls: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            controls.append(item.strip())
        elif isinstance(item, dict):
            action = _text(item.get("action") or item.get("name"), "操作")
            inputs = _text_list(
                item.get("inputs")
                or item.get("keys")
                or item.get("keyboard")
                or item.get("bindings")
            )
            touch = _text(item.get("touch"))
            binding = " / ".join(inputs + ([touch] if touch else []))
            controls.append(f"{action}：{binding}" if binding else action)
    return controls


def _legacy_levels(value: Any) -> list[str]:
    if not isinstance(value, list):
        return _text_list(value)
    levels: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            levels.append(item.strip())
        elif isinstance(item, dict):
            name = _text(item.get("name") or item.get("title") or item.get("id"))
            if name:
                levels.append(name)
    return levels


def coerce_design_doc(value: Any, fallback_title: str = "") -> dict[str, Any]:
    """把 v2、旧版四字段设计稿或纯文本安全归一化为 v2 字典。"""
    if isinstance(value, str):
        parsed = _decode_json(value)
        source: dict[str, Any] = parsed or {"gameplay": value}
    elif isinstance(value, dict):
        source = copy.deepcopy(value)
    else:
        source = {}

    doc = _empty_doc(_text(source.get("title"), fallback_title))
    doc.update(source)
    doc["schema_version"] = SCHEMA_VERSION
    doc["title"] = _text(doc.get("title"), fallback_title or "未命名游戏")

    gameplay = doc.get("gameplay")
    if isinstance(gameplay, dict):
        gameplay = (
            gameplay.get("summary")
            or gameplay.get("description")
            or gameplay.get("core_loop")
        )
        if isinstance(gameplay, list):
            gameplay = "；".join(_text_list(gameplay))
    doc["gameplay"] = _text(gameplay)
    doc["controls"] = _legacy_controls(doc.get("controls"))
    doc["levels"] = _legacy_levels(doc.get("levels"))

    overview = doc.get("overview") if isinstance(doc.get("overview"), dict) else {}
    doc["overview"] = {
        "genre": _text(overview.get("genre")),
        "target_experience": _text(overview.get("target_experience")),
        "session_length": _text(overview.get("session_length")),
        "scope": _text(
            overview.get("scope"), "单个离线 index.html 可实现的完整游戏原型"
        ),
        "assumptions": _text_list(overview.get("assumptions")),
    }
    doc["core_loop"] = _text_list(doc.get("core_loop"))

    rules = doc.get("rules") if isinstance(doc.get("rules"), dict) else {}
    doc["rules"] = {
        key: _text_list(rules.get(key))
        for key in (
            "objectives",
            "win_conditions",
            "lose_conditions",
            "scoring",
            "progression",
        )
    }

    states: list[dict[str, Any]] = []
    for state in _dict_list(doc.get("game_states")):
        states.append(
            {
                **state,
                "id": _text(state.get("id")),
                "purpose": _text(state.get("purpose")),
                "enter_actions": _text_list(state.get("enter_actions")),
                "available_actions": _text_list(state.get("available_actions")),
                "transitions": _text_list(state.get("transitions")),
            }
        )
    doc["game_states"] = states

    entities: list[dict[str, Any]] = []
    for entity in _dict_list(doc.get("entities")):
        properties = entity.get("properties")
        entities.append(
            {
                **entity,
                "id": _text(entity.get("id")),
                "name": _text(entity.get("name")),
                "type": _text(entity.get("type")),
                "behavior": _text_list(entity.get("behavior")),
                "properties": properties if isinstance(properties, dict) else {},
            }
        )
    doc["entities"] = entities

    level_specs: list[dict[str, Any]] = []
    for index, level in enumerate(_dict_list(doc.get("level_specs")), start=1):
        level_specs.append(
            {
                **level,
                "id": _text(level.get("id"), f"level_{index}"),
                "name": _text(level.get("name"), f"第 {index} 关"),
                "goal": _text(level.get("goal")),
                "setup": _text_list(level.get("setup")),
                "mechanics": _text_list(level.get("mechanics")),
                "difficulty": _text_list(level.get("difficulty")),
                "completion": _text(level.get("completion")),
                "next": _text(level.get("next")),
            }
        )
    if not level_specs and doc["levels"]:
        level_specs = [
            {
                "id": f"level_{index}",
                "name": name,
                "goal": "",
                "setup": [],
                "mechanics": [],
                "difficulty": [],
                "completion": "",
                "next": (
                    f"level_{index + 1}"
                    if index < len(doc["levels"])
                    else "victory"
                ),
            }
            for index, name in enumerate(doc["levels"], start=1)
        ]
    if not doc["levels"] and level_specs:
        doc["levels"] = [level["name"] for level in level_specs]
    doc["level_specs"] = level_specs

    ui = doc.get("ui") if isinstance(doc.get("ui"), dict) else {}
    doc["ui"] = {
        "screens": _text_list(ui.get("screens")),
        "hud": _text_list(ui.get("hud")),
        "feedback": _text_list(ui.get("feedback")),
        "instructions": _text_list(ui.get("instructions")),
    }

    presentation = (
        doc.get("presentation")
        if isinstance(doc.get("presentation"), dict)
        else {}
    )
    asset_needs: list[dict[str, str]] = []
    for asset in _dict_list(presentation.get("asset_needs")):
        asset_needs.append(
            {
                "id": _text(asset.get("id")),
                "kind": _text(asset.get("kind")),
                "purpose": _text(asset.get("purpose")),
                "fallback": _text(asset.get("fallback")),
            }
        )
    doc["presentation"] = {
        "visual_style": _text(presentation.get("visual_style")),
        "color_palette": _text_list(presentation.get("color_palette")),
        "asset_needs": asset_needs,
        "effects": _text_list(presentation.get("effects")),
    }
    constraints = _text_list(doc.get("technical_constraints"))
    doc["technical_constraints"] = constraints or _empty_doc("")[
        "technical_constraints"
    ]

    criteria: list[dict[str, str]] = []
    for index, criterion in enumerate(
        _dict_list(doc.get("acceptance_criteria")), start=1
    ):
        criteria.append(
            {
                "id": _text(criterion.get("id"), f"AC-{index:02d}"),
                "requirement": _text(criterion.get("requirement")),
                "verification": _text(criterion.get("verification")),
            }
        )
    doc["acceptance_criteria"] = criteria
    return doc


def parse_design_doc(raw: Any, fallback_title: str = "") -> dict[str, Any]:
    """解析 LLM 输出；无效 JSON 会保留为旧版 gameplay，供校验器触发重试。"""
    return coerce_design_doc(raw, fallback_title)


def design_doc_to_text(value: Any) -> str:
    title = _text(value.get("title")) if isinstance(value, dict) else ""
    return json.dumps(
        coerce_design_doc(value, title),
        ensure_ascii=False,
        indent=2,
    )


def validate_design_doc(value: Any) -> list[str]:
    """返回面向模型的具体校验错误；空列表表示结构可进入用户确认。"""
    doc = coerce_design_doc(value)
    errors: list[str] = []

    if not doc["title"]:
        errors.append("title 不能为空")
    if not doc["gameplay"]:
        errors.append("gameplay 必须概括核心玩法与完整循环")
    if not doc["controls"]:
        errors.append("controls 至少需要一条玩家操作说明")
    controls_text = " ".join(doc["controls"]).lower()
    if not any(token in controls_text for token in ("键", "wasd", "arrow", "space")):
        errors.append("controls 必须明确键盘操作")
    if not any(token in controls_text for token in ("触", "点击", "滑动", "tap", "touch")):
        errors.append("controls 必须明确触控操作")

    if not doc["levels"]:
        errors.append("levels 至少需要一个关卡或阶段")
    if len(doc["levels"]) != len(doc["level_specs"]):
        errors.append("levels 与 level_specs 数量必须一致")
    elif [item["name"] for item in doc["level_specs"]] != doc["levels"]:
        errors.append("levels 的名称与 level_specs.name 必须按顺序完全对应")

    overview = doc["overview"]
    for key in ("genre", "target_experience", "session_length", "scope"):
        if not overview[key]:
            errors.append(f"overview.{key} 不能为空")
    if len(doc["core_loop"]) < 2:
        errors.append("core_loop 至少需要两个按游玩顺序描述的步骤")

    for key in ("objectives", "win_conditions", "lose_conditions", "progression"):
        if not doc["rules"][key]:
            errors.append(f"rules.{key} 至少需要一条明确规则")

    state_ids = {state["id"] for state in doc["game_states"] if state["id"]}
    missing_states = sorted(REQUIRED_STATE_IDS - state_ids)
    if missing_states:
        errors.append("game_states 缺少必需状态：" + ", ".join(missing_states))
    for state in doc["game_states"]:
        if not state["purpose"] or not state["transitions"]:
            errors.append(f"game_states.{state['id'] or '<empty>'} 缺少 purpose 或 transitions")

    if not doc["entities"]:
        errors.append("entities 至少需要描述玩家或核心交互实体")
    entity_ids = [entity["id"] for entity in doc["entities"]]
    if any(not entity_id for entity_id in entity_ids):
        errors.append("每个 entities 项都必须有非空 id")
    if len(entity_ids) != len(set(entity_ids)):
        errors.append("entities.id 必须唯一")

    level_ids = [level["id"] for level in doc["level_specs"]]
    if len(level_ids) != len(set(level_ids)):
        errors.append("level_specs.id 必须唯一")
    for level in doc["level_specs"]:
        for key in ("goal", "setup", "mechanics", "difficulty", "completion", "next"):
            if not level[key]:
                errors.append(f"level_specs.{level['id']}.{key} 不能为空")

    for key in ("screens", "feedback", "instructions"):
        if not doc["ui"][key]:
            errors.append(f"ui.{key} 至少需要一项")
    if not doc["presentation"]["visual_style"]:
        errors.append("presentation.visual_style 不能为空")
    if not doc["technical_constraints"]:
        errors.append("technical_constraints 至少需要一项")

    criteria = doc["acceptance_criteria"]
    if len(criteria) < 8:
        errors.append("acceptance_criteria 至少需要 8 条以覆盖完整游戏闭环")
    criterion_ids = [criterion["id"] for criterion in criteria]
    if len(criterion_ids) != len(set(criterion_ids)):
        errors.append("acceptance_criteria.id 必须唯一")
    for criterion in criteria:
        if not criterion["requirement"] or not criterion["verification"]:
            errors.append(
                f"acceptance_criteria.{criterion['id']} 缺少 requirement 或 verification"
            )

    # 去重并保留稳定顺序，避免把重复错误反馈给模型。
    return list(dict.fromkeys(errors))


__all__ = [
    "SCHEMA_VERSION",
    "coerce_design_doc",
    "design_doc_to_text",
    "parse_design_doc",
    "validate_design_doc",
]
