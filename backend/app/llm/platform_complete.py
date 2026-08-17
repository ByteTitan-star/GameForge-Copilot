"""平台旁路 LLM：observe_generation + provider.complete，不计用户配额/熔断。"""

from __future__ import annotations

from typing import Any

from app.core.langfuse import observe_generation, propagate_trace_attrs
from app.enums import LLMProvider
from app.llm import provider


async def platform_complete(
    prov: LLMProvider,
    apikey: str,
    model: str,
    system: str,
    user_msg: str,
    *,
    kind: str,
    base_url: str | None = None,
    max_tokens: int | None = None,
    metadata: dict[str, Any] | None = None,
    tags: list[str] | None = None,
) -> tuple[str, provider.Usage]:
    """执行一次平台 key 的非流式补全并上报 Langfuse generation。"""
    meta = dict(metadata or {})
    tag_list = list(tags or [])
    with (
        propagate_trace_attrs(
            user_id=meta.get("user_id"),
            session_id=meta.get("game_id") or meta.get("session_id"),
            tags=tag_list or None,
        ),
        observe_generation(
            model=model,
            provider=prov.value,
            system=system,
            user_msg=user_msg,
            kind=kind,
            metadata=meta,
            tags=tag_list or None,
        ) as gen,
    ):
        try:
            content, usage = await provider.complete(
                prov,
                apikey,
                model,
                system,
                user_msg,
                base_url=base_url,
                max_tokens=max_tokens,
            )
        except Exception:
            if gen is not None:
                gen.update(level="ERROR", status_message="platform llm call failed")
            raise
        if gen is not None:
            gen.update(
                output=content,
                usage_details={
                    "input": usage.input_tokens,
                    "output": usage.output_tokens,
                },
            )
    return content, usage
