"""敏感词词库匹配：归一化 + 白名单掩码 + Aho-Corasick block 扫描。"""

from app.forge.lexicon.matcher import LexiconHit, LexiconMatcher, reset_lexicon_cache
from app.forge.lexicon.normalize import normalize

__all__ = [
    "LexiconHit",
    "LexiconMatcher",
    "normalize",
    "reset_lexicon_cache",
]
