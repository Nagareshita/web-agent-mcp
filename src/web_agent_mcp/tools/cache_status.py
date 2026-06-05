"""cache_status tool - report cache and index statistics."""
from __future__ import annotations

import json

from pydantic import BaseModel, Field, ConfigDict

from web_agent_mcp.config import settings
from web_agent_mcp.models import CacheStatusOutput
from web_agent_mcp.storage.cache import cache_stats
from web_agent_mcp.storage.index import document_count


class CacheStatusInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    include_entries: bool = Field(False, description="Reserved for future use")


async def run_cache_status(params: CacheStatusInput) -> str:
    stats = cache_stats()
    doc_count = document_count()

    output = CacheStatusOutput(
        cache_dir=settings.cache_dir,
        index_dir=settings.index_dir,
        document_count=doc_count,
        search_cache_count=stats["search_cache_count"],
        size_bytes=stats["size_bytes"],
    )
    return json.dumps(output.model_dump(), ensure_ascii=False)
