"""design_doc 结构化解析（Batch A · B-A4）与 v2 结构校验。"""

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
