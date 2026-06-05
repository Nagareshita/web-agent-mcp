"""SearXNG JSON search API client."""
from __future__ import annotations

from typing import Any, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from web_agent_mcp.config import settings


@retry(
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=5),
    reraise=True,
)
async def searxng_search(
    query: str,
    max_results: int = 10,
    language: str = "auto",
    safe_search: bool = True,
    categories: Optional[list[str]] = None,
) -> list[dict[str, Any]]:
    """Call SearXNG JSON API and return raw results list."""
    params: dict[str, Any] = {
        "q": query,
        "format": "json",
        "results_on_new_tab": 0,
    }

    if language and language != "auto":
        params["language"] = language

    if safe_search:
        params["safesearch"] = 1
    else:
        params["safesearch"] = 0

    if categories:
        params["categories"] = ",".join(categories)

    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        resp = await client.get(
            f"{settings.searxng_base_url}/search",
            params=params,
        )
        resp.raise_for_status()
        data = resp.json()

    raw_results = data.get("results", [])
    return raw_results[:max_results]
