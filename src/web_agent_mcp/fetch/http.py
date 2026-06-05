"""HTTP fetch with retry, redirect tracking and cache integration."""
from __future__ import annotations

import time
from typing import Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from web_agent_mcp.fetch.safety import validate_url

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; web-agent-mcp/0.1; +https://github.com/local/web-agent-mcp)"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en;q=0.9",
}

_MAX_RESPONSE_BYTES = 10 * 1024 * 1024  # 10 MB safety cap


class FetchResult:
    def __init__(
        self,
        content: bytes,
        content_type: str,
        status_code: int,
        final_url: str,
    ) -> None:
        self.content = content
        self.content_type = content_type
        self.status_code = status_code
        self.final_url = final_url


@retry(
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    reraise=True,
)
async def fetch_url(
    url: str,
    timeout_seconds: int = 30,
    extra_headers: Optional[dict[str, str]] = None,
) -> FetchResult:
    """Fetch a URL safely. Raises ValueError for SSRF violations."""
    validate_url(url)

    headers = dict(_DEFAULT_HEADERS)
    if extra_headers:
        headers.update(extra_headers)

    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=httpx.Timeout(timeout_seconds),
        headers=headers,
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
    ) as client:
        response = await client.get(url)
        response.raise_for_status()

        content = response.content[:_MAX_RESPONSE_BYTES]
        content_type = response.headers.get("content-type", "")
        return FetchResult(
            content=content,
            content_type=content_type,
            status_code=response.status_code,
            final_url=str(response.url),
        )
