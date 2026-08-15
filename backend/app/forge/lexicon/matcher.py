"""词库加载与 AC 扫描：allow 掩码后扫 block，按目录 mtime 热加载。"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import ahocorasick

from app.core.config import settings
from app.forge.lexicon.normalize import normalize

log = logging.getLogger(__name__)

# 稳定 category 枚举：文件名 → 对外 category（勿直接用可变文件名当协议）
_BLOCK_CATEGORY_BY_FILE: dict[str, str] = {
    "terrorism.txt": "terrorism",
    "porn.txt": "porn",
    "gambling_drugs.txt": "gambling_drugs",
}

_DEFAULT_LEXICON_DIR = Path(__file__).resolve().parent.parent / "lexicons"
_MASK = "\0"

_cached: LexiconMatcher | None = None
_cached_mtime: float | None = None
_cached_dir: str | None = None


@dataclass(frozen=True, slots=True)
class LexiconHit:
    category: str
    word: str


class LexiconMatcher:
    """已构建的 allow + block 自动机；scan 对原文做归一化后匹配。"""

    def __init__(
        self,
        *,
        block: ahocorasick.Automaton | None,
        allow_words: list[str],
    ) -> None:
        self._block = block
        self._allow_words = allow_words

    @classmethod
    def empty(cls) -> LexiconMatcher:
        return cls(block=None, allow_words=[])

    @classmethod
    def load(cls) -> LexiconMatcher:
        """取当前生效匹配器；关闭开关或目录不可用时返回空匹配器。"""
        global _cached, _cached_mtime, _cached_dir
        if not settings.audit_lexicon_enabled:
            return cls.empty()

        root = _lexicon_root()
        mtime = _dir_mtime(root)
        root_key = str(root)
        if (
            _cached is not None
            and _cached_mtime == mtime
            and _cached_dir == root_key
        ):
            return _cached

        matcher = cls._build(root)
        _cached, _cached_mtime, _cached_dir = matcher, mtime, root_key
        return matcher

    @classmethod
    def _build(cls, root: Path) -> LexiconMatcher:
        if not root.is_dir():
            log.warning("lexicon dir missing: %s", root)
            return cls.empty()

        allow_words = _read_words(root / "allow.txt")
        block = ahocorasick.Automaton()
        word_count = 0
        block_dir = root / "block"
        if block_dir.is_dir():
            for path in sorted(block_dir.glob("*.txt")):
                category = _BLOCK_CATEGORY_BY_FILE.get(path.name)
                if category is None:
                    log.warning("lexicon block file skipped (unknown category): %s", path.name)
                    continue
                for word in _read_words(path):
                    block.add_word(word, (category, word))
                    word_count += 1
        if word_count == 0:
            return cls(block=None, allow_words=allow_words)
        block.make_automaton()
        log.info(
            "lexicon loaded: dir=%s block_words=%d allow_words=%d",
            root,
            word_count,
            len(allow_words),
        )
        return cls(block=block, allow_words=allow_words)

    def scan(self, text: str) -> LexiconHit | None:
        """归一化 → 白名单掩码 → block 扫描；命中返回首个 LexiconHit。"""
        if not settings.audit_lexicon_enabled or not text or self._block is None:
            return None
        normalized = normalize(text)
        if not normalized:
            return None
        masked = _mask_allow(normalized, self._allow_words)
        for _end, (category, word) in self._block.iter(masked):
            if _MASK in masked[_end - len(word) + 1 : _end + 1]:
                continue
            return LexiconHit(category=category, word=word)
        return None


def reset_lexicon_cache() -> None:
    """测试用：清空热加载缓存。"""
    global _cached, _cached_mtime, _cached_dir
    _cached, _cached_mtime, _cached_dir = None, None, None


def _lexicon_root() -> Path:
    if settings.audit_lexicon_dir:
        return Path(settings.audit_lexicon_dir)
    return _DEFAULT_LEXICON_DIR


def _dir_mtime(root: Path) -> float:
    """目录树内相关文件的最新 mtime；缺失则 0。"""
    latest = 0.0
    if not root.is_dir():
        return latest
    for path in root.rglob("*"):
        if path.is_file() and path.suffix == ".txt":
            try:
                latest = max(latest, path.stat().st_mtime)
            except OSError:
                continue
    return latest


def _read_words(path: Path) -> list[str]:
    if not path.is_file():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        log.warning("lexicon file unreadable: %s", path, exc_info=True)
        return []
    words: list[str] = []
    seen: set[str] = set()
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # 入库约定：过短词需人工确认；此处仍加载但 ≥2 才入自动机，单字直接跳过
        if len(line) < 2:
            continue
        if line in seen:
            continue
        seen.add(line)
        words.append(line)
    return words


def _mask_allow(text: str, allow_words: list[str]) -> str:
    """最长匹配优先：按词长降序替换为掩码，避免短敏感词误伤白名单短语。"""
    if not allow_words:
        return text
    chars = list(text)
    for word in sorted(allow_words, key=len, reverse=True):
        start = 0
        while True:
            idx = text.find(word, start)
            if idx < 0:
                break
            for i in range(idx, idx + len(word)):
                chars[i] = _MASK
            start = idx + len(word)
    return "".join(chars)
