"""local_document_search tool - FTS5 search over indexed documents."""
from __future__ import annotations

import json
from typing import Literal, Optional

from pydantic import BaseModel, Field, ConfigDict

from web_agent_mcp.models import LocalSearchOutput, LocalSearchResult
from web_agent_mcp.storage.index import search_fts


class LocalDocumentSearchInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(..., description="Full-text search query", min_length=1, max_length=500)
    source: str = Field(
        "all",
        description="Filter by source type: 'all', 'web', or 'pdf'",
    )
    max_results: int = Field(10, description="Maximum results to return", ge=1, le=50)


async def run_local_document_search(params: LocalDocumentSearchInput) -> str:
    rows = search_fts(params.query, max_results=params.max_results, source=params.source)

    results = []
    for row in rows:
        results.append(
            LocalSearchResult(
                document_id=row["document_id"],
                title=row.get("title"),
                url=row.get("url"),
                source_type=row["source_type"],
                page=row.get("page"),
                chunk_id=row["chunk_id"],
                snippet=row.get("snippet", ""),
                score=row.get("score", 0.0),
            )
        )

    output = LocalSearchOutput(query=params.query, results=results)
    return json.dumps(output.model_dump(), ensure_ascii=False)
