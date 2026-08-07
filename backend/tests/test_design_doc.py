"""design_doc 结构化解析（Batch A · B-A4）。"""

from app.forge.design_doc import parse_design_doc


def test_parse_design_doc_json() -> None:
    raw = '{"title":"霓虹蛇","gameplay":"吃豆","controls":"方向键","levels":["A","B"]}'
    doc = parse_design_doc(raw, "fallback")
    assert doc["title"] == "霓虹蛇"
    assert doc["gameplay"] == "吃豆"
    assert doc["controls"] == "方向键"
    assert doc["levels"] == ["A", "B"]


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
