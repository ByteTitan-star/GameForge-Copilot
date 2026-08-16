import json

import pytest
from app.forge.art_direction import parse_art_detail, parse_art_options


def test_parse_art_options_requires_two_ids_and_one_recommendation() -> None:
    parsed = parse_art_options(
        json.dumps(
            {
                "options": [
                    {"id": "B", "name": "纸雕", "summary": "CSS 纸片", "recommended": False},
                    {"id": "A", "name": "霓虹", "summary": "Canvas 粒子", "recommended": True},
                ]
            }
        )
    )
    assert [item["id"] for item in parsed["options"]] == ["A", "B"]
    assert sum(item["recommended"] for item in parsed["options"]) == 1


@pytest.mark.parametrize(
    "options",
    [
        [{"id": "A", "name": "x", "summary": "x", "recommended": True}],
        [
            {"id": "A", "name": "x", "summary": "x", "recommended": True},
            {"id": "A", "name": "y", "summary": "y", "recommended": False},
        ],
        [
            {"id": "A", "name": "x", "summary": "x", "recommended": True},
            {"id": "B", "name": "y", "summary": "y", "recommended": True},
        ],
    ],
)
def test_parse_art_options_rejects_invalid_contract(options: list[dict]) -> None:
    with pytest.raises(ValueError):
        parse_art_options({"options": options})


def test_parse_art_detail_requires_implementation_sections() -> None:
    with pytest.raises(ValueError, match="缺少有效字段"):
        parse_art_detail({"name": "霓虹", "visual_concept": "概念"}, "A")
