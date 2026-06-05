"""web_search tool - search the web via SearXNG."""
from __future__ import annotations

import json
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict

from web_agent_mcp.models import SearchResult, WebSearchOutput
from web_agent_mcp.search.searxng import searxng_search
from web_agent_mcp.storage.cache import get_search_cache, set_search_cache


class WebSearchInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(..., description="Search query string", min_length=1, max_length=500)
    max_results: int = Field(10, description="Maximum number of results to return", ge=1, le=50)
    language: str = Field("auto", description="Language code (e.g. 'ja', 'en') or 'auto'")
    safe_search: bool = Field(True, description="Enable safe search filtering")
    site: Optional[str] = Field(
        None,
        description="Restrict results to this domain (e.g. 'github.com')",
        max_length=253,
    )


async def run_web_search(params: WebSearchInput) -> str:
    effective_query = params.query
    if params.site:
        effective_query = f"site:{params.site} {params.query}"

    cache_key = f"{effective_query}::{params.language}::{params.max_results}"
    cached = get_search_cache(cache_key)
    if cached:
        cached["metadata"]["cache_hit"] = True
        return json.dumps(cached, ensure_ascii=False)

    raw_results = await searxng_search(
        query=effective_query,
        max_results=params.max_results,
        language=params.language,
        safe_search=params.safe_search,
    )

    results = []
    for i, r in enumerate(raw_results, 1):
        url = r.get("url", "")
        from urllib.parse import urlparse

        source = urlparse(url).netloc if url else ""
        results.append(
            SearchResult(
                rank=i,
                title=r.get("title", ""),
                url=url,
                snippet=r.get("content", r.get("snippet", "")),
                source=source,
                published_at=r.get("publishedDate"),
            )
        )

    output = WebSearchOutput(
        query=params.query,
        results=results,
        metadata={"cache_hit": False},
    )
    data = output.model_dump()
    set_search_cache(cache_key, data)
    return json.dumps(data, ensure_ascii=False)
