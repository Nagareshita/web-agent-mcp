"""SSRF protection: validate URLs before fetching."""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

from web_agent_mcp.config import settings

BLOCKED_SCHEMES = {"file", "ftp", "gopher", "data", "javascript"}

# Private / reserved IPv4 networks
_PRIVATE_NETS_V4 = [
    ipaddress.ip_network(n)
    for n in [
        "0.0.0.0/8",
        "10.0.0.0/8",
        "100.64.0.0/10",
        "127.0.0.0/8",
        "169.254.0.0/16",
        "172.16.0.0/12",
        "192.0.0.0/24",
        "192.168.0.0/16",
        "198.18.0.0/15",
        "198.51.100.0/24",
        "203.0.113.0/24",
        "240.0.0.0/4",
        "255.255.255.255/32",
    ]
]

_PRIVATE_NETS_V6 = [
    ipaddress.ip_network(n)
    for n in [
        "::1/128",
        "fc00::/7",
        "fe80::/10",
        "::ffff:0:0/96",
    ]
]


def _is_private(addr: str) -> bool:
    try:
        ip = ipaddress.ip_address(addr)
        nets = _PRIVATE_NETS_V6 if ip.version == 6 else _PRIVATE_NETS_V4
        return any(ip in net for net in nets)
    except ValueError:
        return False


def validate_url(url: str) -> None:
    """Raise ValueError if the URL should be blocked (SSRF guard)."""
    parsed = urlparse(url)

    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"}:
        if scheme in BLOCKED_SCHEMES:
            raise ValueError(f"Scheme '{scheme}' is not allowed.")
        raise ValueError(f"Unknown or unsupported scheme: '{scheme}'")

    host = parsed.hostname
    if not host:
        raise ValueError("URL has no hostname.")

    # Block metadata endpoint
    if host == "169.254.169.254":
        raise ValueError("Cloud metadata endpoint is blocked.")

    if settings.allow_private_network:
        return  # Skip private-network checks when explicitly enabled

    # Resolve hostname to IP and check
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        # Cannot resolve - block to be safe
        raise ValueError(f"Cannot resolve hostname: '{host}'")

    for info in infos:
        addr = info[4][0]
        if _is_private(addr):
            raise ValueError(
                f"URL resolves to a private/reserved address ({addr}) which is blocked."
            )
