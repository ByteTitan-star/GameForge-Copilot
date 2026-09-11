"""provider 多模态 content parts：OpenAI 兼容原样透传、Anthropic 原生转 blocks、文本投影。"""

from __future__ import annotations

import base64

from app.enums import LLMProvider
from app.llm import provider

_PNG = b"\x89PNG\r\n\x1a\nfake"


def test_image_content_part_builds_data_uri() -> None:
    part = provider.image_content_part(_PNG)
    assert part["type"] == "image_url"
    url = part["image_url"]["url"]
    assert url.startswith("data:image/png;base64,")
    assert base64.b64decode(url.split(",", 1)[1]) == _PNG


def test_build_body_openai_compat_keeps_content_parts() -> None:
    parts = [{"type": "text", "text": "light or dark?"}, provider.image_content_part(_PNG)]
    body = provider._build_body(
        LLMProvider.OPENAI_COMPAT,
        "glm-4v-flash",
        "sys",
        parts,
        "https://open.bigmodel.cn/api/paas/v4",
        max_tokens=64,
        stream=False,
    )
    assert body["messages"][0] == {"role": "system", "content": "sys"}
    assert body["messages"][1]["content"] is parts


def test_build_body_anthropic_native_converts_to_blocks() -> None:
    parts = [{"type": "text", "text": "describe"}, provider.image_content_part(_PNG)]
    body = provider._build_body(
        LLMProvider.ANTHROPIC, "claude-sonnet-5", "sys", parts, None, max_tokens=64, stream=False
    )
    blocks = body["messages"][0]["content"]
    assert blocks[0] == {"type": "text", "text": "describe"}
    assert blocks[1]["type"] == "image"
    assert blocks[1]["source"]["type"] == "base64"
    assert blocks[1]["source"]["media_type"] == "image/png"
    assert base64.b64decode(blocks[1]["source"]["data"]) == _PNG


def test_build_body_plain_string_unchanged() -> None:
    body = provider._build_body(
        LLMProvider.ANTHROPIC, "claude-sonnet-5", "sys", "hi", None, max_tokens=8, stream=False
    )
    assert body["messages"][0]["content"] == "hi"


def test_content_text_projects_images_to_placeholder() -> None:
    parts = [{"type": "text", "text": "brief"}, provider.image_content_part(_PNG)]
    assert provider.content_text(parts) == "brief\n<image>"
    assert provider.content_text("plain") == "plain"


def test_llm_timeout_read_override() -> None:
    default = provider._llm_timeout()
    short = provider._llm_timeout(read_timeout_s=7)
    assert short.read == 7
    assert short.connect == default.connect
    assert default.read != 7
