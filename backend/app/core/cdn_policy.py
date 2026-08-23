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
    """提取 HTML 中所有 http(s) 绝对外链。

    作用：正则匹配 src=/href= 属性中的 URL，保序去重；忽略相对路径与 data:/blob:。
    场景：试玩前校验、提示词约束、CSP 策略生成前的引用收集。
    参数：html - HTML 源码字符串。
    返回：外链 URL 列表。
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
    """校验外链主机是否均在 CDN 白名单内。

    作用：解析每个 URL 的 hostname，找出不在 allowed 集合中的违规项。
    场景：沙箱试玩 validate_refs、生成后合规检查。
    参数：refs - 待校验 URL 列表；allowed - 允许的主机名集合，默认 ALLOWED_CDN_HOSTS。
    返回：``(是否全部合规, 违规 URL 列表)``；空输入视为合规。
    """
    violations = [url for url in refs if (urlparse(url).hostname or "") not in allowed]
    return (not violations, violations)


# dist 产物内扫描 http(s) URL（§18：html/js/css 全量扫描）
_DIST_URL_RE = re.compile(r"""https?://[^\s"'<>]+""", re.IGNORECASE)


def extract_urls_from_text(text: str) -> list[str]:
    """从 dist 文本产物中提取 http(s) URL。

    作用：正则扫描文本中的绝对 URL，去除尾部标点，保序去重。
    场景：scan_dist_external_refs 读取 html/js/css 文件时复用。
    参数：text - 文件内容字符串。
    返回：URL 列表。
    """
    refs: list[str] = []
    seen: set[str] = set()
    for match in _DIST_URL_RE.finditer(text or ""):
        url = match.group(0).rstrip(".,;)")
        if url not in seen:
            seen.add(url)
            refs.append(url)
    return refs


def scan_dist_external_refs(dist_dir: Path) -> list[str]:
    """扫描 dist 目录下 html/js/css 中的外链 URL。

    作用：递归遍历 dist_dir，读取文本文件并调用 extract_urls_from_text 汇总。
    场景：Vite 构建产物发布前检查是否引入外部依赖。
    参数：dist_dir - 构建输出根目录 Path。
    返回：去重后的外链 URL 列表；目录不存在时返回空列表。
    """
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
    """校验 Vite dist 是否自包含（无 http(s) 外链）。

    作用：多文件 dist 默认不应引用任意外部 URL；有则全部视为违规。
    场景：项目模式产物 promote 前的自包含检查。
    参数：refs - scan_dist_external_refs 收集的 URL 列表。
    返回：``(是否合规, 违规 URL 列表)``。
    """
    return (not refs, refs)


def build_csp_project() -> str:
    """生成多文件 Vite dist 的 Content-Security-Policy 头。

    作用：仅允许 same-origin 资源，connect-src 为 none，收紧脚本与样式来源。
    场景：托管自包含项目产物 iframe 时设置响应头。
    参数：无。
    返回：CSP 策略字符串。
    """
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
    """按 CDN 白名单生成单 HTML 产物的 Content-Security-Policy 头。

    作用：在 default-src 'self' 基础上，将 script/style/font/connect 放宽到白名单域名。
    场景：单页 HTML 游戏 iframe 托管；比放行整个 https: 更安全。
    参数：allowed - 允许引用的 CDN 主机名集合，默认 ALLOWED_CDN_HOSTS。
    返回：CSP 策略字符串。
    """
    hosts = " ".join(sorted(allowed))
    return (
        "default-src 'self'; "
        f"script-src 'self' 'unsafe-inline' {hosts}; "
        f"style-src 'self' 'unsafe-inline' {hosts}; "
        f"font-src 'self' data: {hosts}; "
        "img-src 'self' data: blob:; "
        f"connect-src 'self' {hosts}; "
        "worker-src 'self' blob:"
    )
