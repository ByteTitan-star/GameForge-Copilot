"""匹配前轻量归一化：全角→半角、剔除干扰符号与空白。"""

from __future__ import annotations

# 匹配时剔除的干扰字符（保留 CJK / 字母数字 / 常见连接语义外的噪声）
_NOISE = frozenset(" \t\r\n　*.-_/\\|~`!@#$%^&+=<>?\"'，。、；：""''【】（）[]{}…·•")


def _to_halfwidth(ch: str) -> str:
    """全角 ASCII 区（FF01–FF5E）→ 半角；全角空格 → 半角空格。"""
    code = ord(ch)
    if code == 0x3000:
        return " "
    if 0xFF01 <= code <= 0xFF5E:
        return chr(code - 0xFEE0)
    return ch


def normalize(text: str) -> str:
    """归一化文本供 AC 扫描；不回映原文区间（P1 evidence 用命中词面）。

    拉丁字母统一小写，避免英文大小写绕过；CJK 不变。
    """
    out: list[str] = []
    for ch in text:
        ch = _to_halfwidth(ch)
        if ch in _NOISE:
            continue
        if "A" <= ch <= "Z":
            ch = ch.lower()
        out.append(ch)
    return "".join(out)
