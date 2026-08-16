"""Validate user-supplied LLM base_url against SSRF (ADR-07 P1-19)."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

from app.core.config import settings
from app.core.errors import AppError, ErrorCode


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _host_allowed_in_development(host: str) -> bool:
    return host in {"localhost", "127.0.0.1", "::1"}


def validate_llm_base_url(base_url: str | None, *, env: str | None = None) -> None:
    """Raise AppError if base_url is missing scheme/host or targets private/metadata nets.

    Empty base_url is allowed (provider defaults). Development may use http://localhost.
    """
    if base_url is None or not str(base_url).strip():
        return
    raw = str(base_url).strip()
    parsed = urlparse(raw)
    scheme = (parsed.scheme or "").lower()
    host = (parsed.hostname or "").lower()
    current_env = env if env is not None else settings.env

    if not host:
        raise AppError(ErrorCode.LLM_CONFIG_INVALID, "base_url 缺少主机名")

    if scheme == "https":
        pass
    elif scheme == "http" and current_env == "development" and _host_allowed_in_development(
        host
    ):
        pass
    else:
        raise AppError(
            ErrorCode.LLM_CONFIG_INVALID,
            "base_url 仅允许 https（development 可对本机使用 http）",
        )

    if host in {"metadata.google.internal", "metadata"}:
        raise AppError(ErrorCode.LLM_CONFIG_INVALID, "base_url 主机不允许")

    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        addr = None

    if addr is not None:
        if _is_blocked_ip(addr) and not (
            current_env == "development" and _host_allowed_in_development(host)
        ):
            raise AppError(ErrorCode.LLM_CONFIG_INVALID, "base_url 禁止指向内网或保留地址")
        return

    # Hostname: resolve and reject if any A/AAAA is blocked (best-effort).
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return
    for info in infos:
        sockaddr = info[4]
        try:
            resolved = ipaddress.ip_address(sockaddr[0])
        except ValueError:
            continue
        if _is_blocked_ip(resolved) and not (
            current_env == "development" and _host_allowed_in_development(host)
        ):
            raise AppError(
                ErrorCode.LLM_CONFIG_INVALID,
                "base_url 解析到内网或保留地址，已拒绝",
            )
