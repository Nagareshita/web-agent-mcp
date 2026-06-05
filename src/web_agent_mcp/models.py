"""Shared Pydantic models for request/response types."""
from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field, ConfigDict


# ─── web_search ───────────────────────────────────────────────────────────────

class SearchResult(BaseModel):
    rank: int
    title: str
    url: str
    snippet: str
    source: str
    published_at: Optional[str] = None


class WebSearchOutput(BaseModel):
    query: str
    provider: str = "searxng"
    results: list[SearchResult]
    metadata: dict[str, Any]


# ─── web_read ─────────────────────────────────────────────────────────────────

class Chunk(BaseModel):
    chunk_id: str
    text: str
    page: Optional[int] = None
    char_start: int
    char_end: int


class WebReadMetadata(BaseModel):
    status_code: Optional[int] = None
    content_type: Optional[str] = None
    cache_hit: bool = False
    content_truncated: bool = False
    # pagination / large-content info
    total_chars: Optional[int] = None
    total_pages: Optional[int] = None
    current_page: Optional[int] = None
    used_browser: bool = False


class WebReadOutput(BaseModel):
    input_url: Optional[str] = None
    local_path: Optional[str] = None
    final_url: Optional[str] = None
    title: Optional[str] = None
    fetched_at: str
    source_type: str  # "html" | "pdf" | "text"
    extraction_method: str
    content_format: str
    content: str
    chunks: list[Chunk] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)
    metadata: WebReadMetadata = Field(default_factory=WebReadMetadata)


# ─── web_read_many ────────────────────────────────────────────────────────────

class WebReadError(BaseModel):
    url: str
    error: str


class WebReadManyOutput(BaseModel):
    results: list[WebReadOutput]
    errors: list[WebReadError]


# ─── local_document_search ────────────────────────────────────────────────────

class LocalSearchResult(BaseModel):
    document_id: str
    title: Optional[str]
    url: Optional[str]
    source_type: str
    page: Optional[int] = None
    chunk_id: str
    snippet: str
    score: float


class LocalSearchOutput(BaseModel):
    query: str
    results: list[LocalSearchResult]


# ─── cache_status ─────────────────────────────────────────────────────────────

class CacheStatusOutput(BaseModel):
    cache_dir: str
    index_dir: str
    document_count: int
    search_cache_count: int
    size_bytes: int
