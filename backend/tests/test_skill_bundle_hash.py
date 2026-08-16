"""Skill catalog hash 稳定性（Exact Cache 依赖）。"""

from __future__ import annotations

import asyncio

import pytest

from app.forge.skills.catalog import catalog_skill_bundle_hash, skill_bundle_hash


def test_catalog_skill_bundle_hash_stable() -> None:
    a = catalog_skill_bundle_hash()
    b = catalog_skill_bundle_hash()
    assert a == b
    assert len(a) == 64


def test_skill_bundle_hash_order_independent() -> None:
    ids = ["art/pixel-art", "code/canvas", "policy/playtest"]
    assert skill_bundle_hash(ids) == skill_bundle_hash(list(reversed(ids)))


@pytest.mark.asyncio
async def test_catalog_hash_concurrent_reads_identical() -> None:
    results = await asyncio.gather(
        *(asyncio.to_thread(catalog_skill_bundle_hash) for _ in range(24))
    )
    assert len(set(results)) == 1
