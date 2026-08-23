"""词库加载与 AC 扫描：allow 掩码后扫 block/suspect，按目录 mtime 热加载。"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

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
_SUSPECT_CATEGORY_BY_FILE: dict[str, str] = {
    "politics.txt": "politics",
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
    level: Literal["block", "suspect"] = "block"


class LexiconMatcher:
    """已构建的 allow + block/suspect 自动机；scan 对原文做归一化后匹配。"""

    def __init__(
        self,
        *,
        block: ahocorasick.Automaton | None,
        suspect: ahocorasick.Automaton | None,
        allow_words: list[str],
    ) -> None:
        """构造已构建的 block/suspect 自动机与白名单词表。

        场景：LexiconMatcher._build / empty。
        参数：block、suspect 自动机、allow_words。
        返回：无。
        """
        self._block = block
        self._suspect = suspect
        self._allow_words = allow_words

    @classmethod
    def empty(cls) -> LexiconMatcher:
        """返回空匹配器（审核词库关闭或目录缺失时）。

        场景：audit_lexicon_enabled=False。
        参数：无。
        返回：无 block/suspect 的 LexiconMatcher。
        """
        return cls(block=None, suspect=None, allow_words=[])

    @classmethod
    def load(cls) -> LexiconMatcher:
        """取当前生效匹配器；关闭开关或目录不可用时返回空匹配器。"""
        global _cached, _cached_mtime, _cached_dir
        if not settings.audit_lexicon_enabled:
            return cls.empty()

        root = _lexicon_root()
        mtime = _dir_mtime(root)
        root_key = str(root)
        if _cached is not None and _cached_mtime == mtime and _cached_dir == root_key:
            return _cached

        matcher = cls._build(root)
        _cached, _cached_mtime, _cached_dir = matcher, mtime, root_key
        return matcher

    @classmethod
    def _build(cls, root: Path) -> LexiconMatcher:
        """从词库目录构建 block/suspect 自动机与白名单。

        场景：LexiconMatcher.load 缓存未命中时。
        参数：root - lexicons 根目录。
        返回：LexiconMatcher 实例。
        """
        if not root.is_dir():
            log.warning("lexicon dir missing: %s", root)
            return cls.empty()

        allow_words = _read_words(root / "allow.txt")
        block, block_n = _build_automaton(root / "block", _BLOCK_CATEGORY_BY_FILE)
        suspect, suspect_n = _build_automaton(root / "suspect", _SUSPECT_CATEGORY_BY_FILE)
        log.info(
            "lexicon loaded: dir=%s block_words=%d suspect_words=%d allow_words=%d",
            root,
            block_n,
            suspect_n,
            len(allow_words),
        )
        return cls(block=block, suspect=suspect, allow_words=allow_words)

    def scan(self, text: str) -> LexiconHit | None:
        """归一化 → 白名单掩码 → block 优先，再 suspect。"""
        if not settings.audit_lexicon_enabled or not text:
            return None
        if self._block is None and self._suspect is None:
            return None
        normalized = normalize(text)
        if not normalized:
            return None
        masked = _mask_allow(normalized, self._allow_words)
        block_hit = _first_hit(self._block, masked, "block")
        if block_hit is not None:
            return block_hit
        return _first_hit(self._suspect, masked, "suspect")


def reset_lexicon_cache() -> None:
    """测试用：清空热加载缓存。"""
    global _cached, _cached_mtime, _cached_dir
    _cached, _cached_mtime, _cached_dir = None, None, None


def _lexicon_root() -> Path:
    """解析词库根目录（settings 或默认 lexicons/）。

    场景：LexiconMatcher.load。
    参数：无。
    返回：Path。
    """
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


def _build_automaton(
    directory: Path, category_by_file: dict[str, str]
) -> tuple[ahocorasick.Automaton | None, int]:
    """从目录下 txt 文件构建 Aho-Corasick 自动机。

    场景：LexiconMatcher._build。
    参数：directory、category_by_file 文件名到 category 映射。
    返回：(自动机或 None, 词条数)。
    """
    if not directory.is_dir():
        return None, 0
    auto = ahocorasick.Automaton()
    count = 0
    for path in sorted(directory.glob("*.txt")):
        category = category_by_file.get(path.name)
        if category is None:
            log.warning("lexicon file skipped (unknown category): %s", path.name)
            continue
        for word in _read_words(path):
            auto.add_word(word, (category, word))
            count += 1
    if count == 0:
        return None, 0
    auto.make_automaton()
    return auto, count


def _first_hit(
    auto: ahocorasick.Automaton | None,
    masked: str,
    level: Literal["block", "suspect"],
) -> LexiconHit | None:
    """在掩码后文本上找第一个未被白名单遮住的词库命中。

    场景：LexiconMatcher.scan。
    参数：auto、masked 文本、level。
    返回：LexiconHit 或 None。
    """
    if auto is None:
        return None
    for end, (category, word) in auto.iter(masked):
        start = end - len(word) + 1
        if _MASK in masked[start : end + 1]:
            continue
        return LexiconHit(category=category, word=word, level=level)
    return None


def _read_words(path: Path) -> list[str]:
    """读取词库 txt 文件并归一化去重。

    场景：_build_automaton、allow.txt 加载。
    参数：path - 词库文件路径。
    返回：归一化后的词列表。
    """
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
        if len(line) < 2:
            continue
        # 与扫描侧同一套归一化，保证英文大小写/空格写法都能入库命中
        word = normalize(line)
        if len(word) < 2:
            continue
        if word in seen:
            continue
        seen.add(word)
        words.append(word)
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
