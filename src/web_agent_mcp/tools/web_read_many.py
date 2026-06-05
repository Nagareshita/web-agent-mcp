"""web_read_many tool - fetch multiple URLs concurrently."""
from __future__ import annotations

import asyncio
import json
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict

from web_agent_mcp.models import WebReadError, WebReadManyOutput
from web_agent_mcp.tools.web_read import WebReadInput, run_web_read


class WebReadManyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    urls: list[str] = Field(..., description="List of URLs to fetch", min_length=1, max_length=20)
    max_concurrency: int = Field(3, description="Maximum concurrent requests", ge=1, le=10)
    max_chars_per_url: Optional[int] = Field(
        None,
        description=(
            "Maximum characters per URL result. "
            "Default: None (no truncation). "
            "Set to an integer (e.g. 5000) to limit output when fetching many URLs."
        ),
        ge=100,
    )


async def run_web_read_many(params: WebReadManyInput) -> str:
    semaphore = asyncio.Semaphore(params.max_concurrency)
    results = []
    errors = []

    async def fetch_one(url: str) -> None:
        async with semaphore:
            try:
                result_json = await run_web_read(
                    WebReadInput(
                        url=url,
                        max_chars=params.max_chars_per_url,
                        return_chunks=True,
                        return_links=False,
                    )
                )
                result = json.loads(result_json)
                results.append(result)
            except Exception as exc:
                errors.append(WebReadError(url=url, error=str(exc)).model_dump())

    await asyncio.gather(*[fetch_one(u) for u in params.urls])

    output = WebReadManyOutput(results=results, errors=errors)
    return json.dumps(output.model_dump(), ensure_ascii=False)
