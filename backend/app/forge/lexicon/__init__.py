"""敏感词词库匹配：归一化 + 白名单掩码 + Aho-Corasick block 扫描。

【安全护栏阅读顺序 · 第 2 步下半 · 约 10min】
────────────────────────────────────────
与 blacklist.txt 分工：本包管「中文内容词」；blacklist 管越狱/恶意代码正则。
先看 matcher.LexiconMatcher.scan；normalize 负责去干扰字符防绕过。
词库目录默认 app/forge/lexicons/（block/suspect/allow）。
完整顺序见 forge/guard.py 文件头。
"""

from app.forge.lexicon.matcher import LexiconHit, LexiconMatcher, reset_lexicon_cache
from app.forge.lexicon.normalize import normalize

__all__ = [
    "LexiconHit",
    "LexiconMatcher",
    "normalize",
    "reset_lexicon_cache",
]
