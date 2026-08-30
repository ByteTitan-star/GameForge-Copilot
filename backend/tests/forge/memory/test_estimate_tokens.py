"""Tokenizer-aware token budget estimates (#147 P0)."""

from __future__ import annotations

from app.forge.memory.context_builder import estimate_tokens


def test_estimate_tokens_cjk_one_per_char() -> None:
    assert estimate_tokens("塔防游戏") == 4


def test_estimate_tokens_ascii_wordpiece_style() -> None:
    # WordPiece-ish: whitespace/punct split; short words ≈1, long ≈ ceil(len/4)
    assert estimate_tokens("cat") == 1
    # tower(2)+defense(2)+game(1)+design(2) = 7
    assert estimate_tokens("tower defense game design") == 7
    # Many short tokens: wordpiece-aligned counts each word, not bag-of-chars/4
    text = "a b c d e f g h"
    assert estimate_tokens(text) == 8
    assert estimate_tokens(text) > (len(text) + 3) // 4


def test_estimate_tokens_mixed_cjk_and_latin() -> None:
    # 塔防(2) + space ignored in CJK path + "RogueLike"(≈2)
    n = estimate_tokens("塔防 RogueLike")
    assert n >= 3
    assert n <= 6


def test_estimate_tokens_empty() -> None:
    assert estimate_tokens("") == 0
