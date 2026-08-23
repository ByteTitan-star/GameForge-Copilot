"""Validate user-supplied LLM base_url against SSRF (ADR-07 P1-19)."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

from app.core.config import settings
from app.core.errors import AppError, ErrorCode


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """判断 IP 是否为内网/保留/环回等应拒绝的地址。

    作用：SSRF 防护辅助判断。
    场景：validate_llm_base_url 解析主机名或字面 IP 时。
    参数：ip IPv4/IPv6 地址对象。
    返回：应拒绝为 True。
    """
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _host_allowed_in_development(host: str) -> bool:
    """development 环境是否允许本机 HTTP 主机名。

    作用：放行 localhost / 127.0.0.1 / ::1。
    场景：dev 下 base_url 使用 http://localhost。
    参数：host 主机名（小写）。
    返回：允许为 True。
    """
    return host in {"localhost", "127.0.0.1", "::1"}


def validate_llm_base_url(base_url: str | None, *, env: str | None = None) -> None:
    """校验用户填写的 LLM base_url，防 SSRF。

    作用：检查 scheme、主机、内网/元数据地址；空 base_url 允许。
    场景：创建/测试 LLM 配置前。
    参数：base_url、可选 env（默认 settings.env）。
    返回：None；非法时抛 LLM_CONFIG_INVALID。
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

    if scheme == "https" or (
        scheme == "http" and current_env == "development" and _host_allowed_in_development(host)
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
