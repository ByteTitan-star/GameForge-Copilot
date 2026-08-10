"""CDN 资源策略：用一份白名单统一管控 LLM 生成游戏可引用的外链域名。

独立原型模块，不依赖 app.*；目的是为 hosting 的 iframe CSP、forge 代码
生成提示词、QA 自动试玩提供同一份"可信 CDN"来源，收敛当前 hosting/routes.py
里放行整个 https:// 的宽松策略——任意 https CDN 都能被加载，存在 XSS 与
稳定性风险。集中到白名单后：CSP、提示词、试玩校验三方共用同一来源。

设计取舍：仅提取 HTML 属性（src/href）中的 http(s) 绝对外链；不解析 CSS
url()、不处理 importmap（YAGNI，当前生成产物是单 HTML 内联结构）。
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

# 内置可信 CDN 白名单：主流公共库镜像 + 字体服务。新增域名在此一处维护。
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


def build_csp(allowed: frozenset[str] = ALLOWED_CDN_HOSTS) -> str:
    """按白名单生成产物 iframe 的 Content-Security-Policy 头。

    相比放行整个 https:，仅允许 'self' + 白名单域名，收紧脚本/样式/字体/连接来源。
    """
    hosts = " ".join(sorted(allowed))
    return (
        "default-src 'self'; "
        f"script-src 'self' 'unsafe-inline' {hosts}; "
        f"style-src 'self' 'unsafe-inline' {hosts}; "
        f"font-src 'self' data: {hosts}; "
        "img-src 'self' data:; "
        f"connect-src 'self' {hosts}"
    )
