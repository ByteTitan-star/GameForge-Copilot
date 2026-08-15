"""design_doc 结构化解析（Batch A · B-A4）与 v2 结构校验。"""

import json

from app.forge.design_doc import parse_design_doc, validate_design_doc


def test_parse_design_doc_json() -> None:
    raw = '{"title":"霓虹蛇","gameplay":"吃豆","controls":"方向键","levels":["A","B"]}'
    doc = parse_design_doc(raw, "fallback")
    assert doc["title"] == "霓虹蛇"
    assert doc["gameplay"] == "吃豆"
    # v2 把 controls 归一化为面向玩家的操作说明数组（兼容旧的字符串/对象写法）
    assert doc["controls"] == ["方向键"]
    assert doc["levels"] == ["A", "B"]


def test_validate_design_doc_accepts_complete_v2() -> None:
    """完整 v2 设计稿应通过校验（无错误）。"""
    from tests.conftest import _valid_design_doc_json

    doc = parse_design_doc(_valid_design_doc_json(), "测试")
    assert validate_design_doc(doc) == []


def test_validate_design_doc_rejects_minimal_legacy_doc() -> None:
    """旧版四字段最小稿缺键盘/触控、状态、关卡规格等，应被拒并给出可读错误。"""
    raw = '{"title":"T","gameplay":"G","controls":"方向键","levels":["A"]}'
    errors = validate_design_doc(parse_design_doc(raw, "T"))
    assert errors  # 非空：缺触控操作、缺必需状态、level_specs 不完整等
    assert any("触控" in e for e in errors)


def test_parse_design_doc_fallback() -> None:
    doc = parse_design_doc("纯文本策划稿", "默认标题")
    assert doc["title"] == "默认标题"
    assert doc["gameplay"] == "纯文本策划稿"
    assert doc["levels"] == []


def test_parse_design_doc_markdown_fence() -> None:
    raw = '说明\n```json\n{"title":"T","gameplay":"G","controls":"C","levels":[]}\n```'
    doc = parse_design_doc(raw, "fb")
    assert doc["title"] == "T"
    assert doc["gameplay"] == "G"


def test_coerce_engine_defaults_canvas_when_absent() -> None:
    """老设计稿无 engine 字段应自动补 canvas，保证向后兼容。"""
    doc = parse_design_doc('{"title":"T","gameplay":"G","controls":"方向键"}', "T")
    assert doc["engine"]["id"] == "canvas"
    assert doc["engine"]["rationale"] == ""


def test_coerce_engine_falls_back_for_unknown_id() -> None:
    """非法 engine.id 应回退 canvas，不阻断生成。"""
    doc = parse_design_doc('{"engine":{"id":"unity"}}', "T")
    assert doc["engine"]["id"] == "canvas"


def test_coerce_engine_preserves_valid_choice() -> None:
    doc = parse_design_doc(
        '{"engine":{"id":"phaser3","rationale":"r","version":"phaser@3.80.1"}}', "T"
    )
    assert doc["engine"]["id"] == "phaser3"
    assert doc["engine"]["version"] == "phaser@3.80.1"


def test_coerce_build_routing_defaults() -> None:
    doc = parse_design_doc('{"title":"T","gameplay":"G"}', "T")
    assert doc["build_routing"]["build"] == "none"
    assert doc["build_routing"]["renderer"] == "canvas"
    assert doc["build_routing"]["ui"] == "none"


def test_coerce_build_routing_from_plan() -> None:
    raw = json.dumps(
        {
            "title": "T",
            "gameplay": "G",
            "controls": ["键盘"],
            "levels": ["L1"],
            "build_routing": {
                "build": "vite",
                "renderer": "phaser3",
                "ui": "none",
                "dependencies": ["matter-js"],
            },
        }
    )
    doc = parse_design_doc(raw, "T")
    assert doc["build_routing"]["build"] == "vite"
    assert doc["build_routing"]["dependencies"] == ["matter-js"]


def test_validate_requires_engine_rationale() -> None:
    from tests.conftest import _valid_design_doc_json

    doc = parse_design_doc(_valid_design_doc_json(), "T")
    doc["engine"]["rationale"] = ""  # 清空选型理由
    errors = validate_design_doc(doc)
    assert any("engine.rationale" in e for e in errors)


def test_validate_requires_engine_version_for_cdn_engines() -> None:
    """phaser3/pixijs 需钉版本号防 CDN 404；canvas 无 CDN 不要求 version。"""
    from tests.conftest import _valid_design_doc_json

    doc = parse_design_doc(_valid_design_doc_json(), "T")
    doc["engine"] = {"id": "phaser3", "rationale": "需要物理碰撞", "version": ""}
    errors = validate_design_doc(doc)
    assert any("engine.version" in e for e in errors)
