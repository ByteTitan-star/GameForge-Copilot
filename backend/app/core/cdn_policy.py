"""CDN 资源策略：用一份白名单统一管控 LLM 生成游戏可引用的外链域名。

被三方共用，单一改点：
- app.hosting.routes：build_csp() 生成产物 iframe 的 CSP 头；
- app.forge.prompts：白名单注入代码生成提示词；
- app.sandbox.playtest：validate_refs() 在试玩前拦截非白名单 CDN。

收敛此前放行整个 https: 的宽松策略——任意外站脚本不再能跑进产物 iframe，
XSS 面收窄；游戏仍可引用 three.js / tailwind / 字体等公共库保证渲染质量。

设计取舍：仅提取 HTML 属性（src/href）中的 http(s) 绝对外链；不解析 CSS
url()、不处理 importmap（当前生成产物是单 HTML 内联结构）。
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

# 内置可信 CDN 白名单：主流公共库镜像 + 字体服务。新增域名在此一处维护，
# CSP / 提示词 / 试玩三方自动同步。
ALLOWED_CDN_HOSTS: frozenset[str] = frozenset(
    {
        "cdn.jsdelivr.net",
        "unpkg.com",
        "cdnjs.cloudflare.com",
        "fonts.googleapis.com",
        "fonts.gstatic.com",
        "cdn.tailwindcss.com",
        "threejs.org",
    }
)

# 匹配 src=/href= 引号包裹的取值；HTML 属性顺序无关，按属性名定位即可。
_REF_RE = re.compile(
    r"""(?:src|href)\s*=\s*["']([^"']+)["']""",
    re.IGNORECASE,
)


def extract_external_refs(html: str) -> list[str]:
    """提取 HTML 中所有 http(s) 绝对外链，保序去重。

    覆盖 <script src>、<link href> 等以属性形式声明的外链；
    相对路径、data: URI、blob: 一律忽略。
    """
    refs: list[str] = []
    seen: set[str] = set()
    for match in _REF_RE.finditer(html or ""):
        url = match.group(1).strip()
        if url.lower().startswith(("http://", "https://")) and url not in seen:
            seen.add(url)
            refs.append(url)
    return refs


def validate_refs(
    refs: list[str], allowed: frozenset[str] = ALLOWED_CDN_HOSTS
) -> tuple[bool, list[str]]:
    """校验外链主机是否都在白名单内。

    返回 (是否全部合规, 违规外链列表)；空输入视为合规。
    """
    violations = [url for url in refs if (urlparse(url).hostname or "") not in allowed]
    return (not violations, violations)


# dist 产物内扫描 http(s) URL（§18：html/js/css 全量扫描）
_DIST_URL_RE = re.compile(r"""https?://[^\s"'<>]+""", re.IGNORECASE)


def extract_urls_from_text(text: str) -> list[str]:
    """从 dist 文本产物提取 http(s) URL，保序去重。"""
    refs: list[str] = []
    seen: set[str] = set()
    for match in _DIST_URL_RE.finditer(text or ""):
        url = match.group(0).rstrip(".,;)")
        if url not in seen:
            seen.add(url)
            refs.append(url)
    return refs


def scan_dist_external_refs(dist_dir: Path) -> list[str]:
    """扫描 dist/ 下 html/js/css 中的外链 URL。"""
    refs: list[str] = []
    seen: set[str] = set()
    if not dist_dir.is_dir():
        return refs
    for path in dist_dir.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".html", ".js", ".css"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="utf-8", errors="replace")
        for url in extract_urls_from_text(text):
            if url not in seen:
                seen.add(url)
                refs.append(url)
    return refs


def validate_dist_self_contained(refs: list[str]) -> tuple[bool, list[str]]:
    """Vite dist 默认应自包含：任何 http(s) 外链均视为违规。"""
    return (not refs, refs)


def build_csp_project() -> str:
    """多文件 Vite dist 的 CSP（§20）：仅 self，connect-src 默认 none。"""
    return (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self'; "
        "font-src 'self' data:; "
        "img-src 'self' data: blob:; "
        "media-src 'self' blob:; "
        "connect-src 'none'; "
        "worker-src 'self' blob:"
    )


def build_csp(allowed: frozenset[str] = ALLOWED_CDN_HOSTS) -> str:
    """按白名单生成产物 iframe 的 Content-Security-Policy 头。

    相比放行整个 https:，仅允许 'self' + 白名单域名，收紧脚本/样式/字体/连接来源。
    worker-src 允许 blob: 以支持 Tone.js 等库在 sandbox iframe 内创建 Web Worker。
    """
    hosts = " ".join(sorted(allowed))
    return (
        "default-src 'self'; "
        f"script-src 'self' 'unsafe-inline' {hosts}; "
        f"style-src 'self' 'unsafe-inline' {hosts}; "
        f"font-src 'self' data: {hosts}; "
        "img-src 'self' data:; "
        f"connect-src 'self' {hosts}; "
        "worker-src 'self' blob:"
    )
