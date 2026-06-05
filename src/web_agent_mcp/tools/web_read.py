"""web_read tool - fetch and extract content from a URL or local PDF."""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict, model_validator

from web_agent_mcp.config import settings
from web_agent_mcp.extract.chunks import chunk_text
from web_agent_mcp.extract.html import extract_html, extract_links
from web_agent_mcp.extract.pdf import extract_pdf
from web_agent_mcp.fetch.http import fetch_url
from web_agent_mcp.fetch.safety import validate_url
from web_agent_mcp.models import Chunk, WebReadMetadata, WebReadOutput
from web_agent_mcp.storage.cache import get_page_cache, set_page_cache
from web_agent_mcp.storage.index import upsert_document


class WebReadInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: Optional[str] = Field(None, description="HTTP/HTTPS URL to fetch")
    local_path: Optional[str] = Field(
        None,
        description="Absolute path to a local PDF file (must be under allowed roots)",
    )
    force_refresh: bool = Field(False, description="Bypass cache and re-fetch")
    content_format: str = Field("markdown", description="Output format: 'markdown' or 'text'")
    max_chars: Optional[int] = Field(
        None,
        description=(
            "Maximum characters to return. "
            "Default: None (no truncation, full content returned). "
            "Set to an integer (e.g. 5000) to limit output length when you only need a summary."
        ),
        ge=100,
    )
    return_chunks: bool = Field(True, description="Include chunked content in output")
    return_links: bool = Field(True, description="Include extracted hyperlinks in output")
    timeout_seconds: int = Field(30, description="HTTP request timeout in seconds", ge=5, le=120)

    @model_validator(mode="after")
    def check_url_or_local(self) -> "WebReadInput":
        if not self.url and not self.local_path:
            raise ValueError("Either 'url' or 'local_path' must be provided.")
        if self.url and self.local_path:
            raise ValueError("Provide either 'url' or 'local_path', not both.")
        return self


def _validate_local_path(local_path: str) -> Path:
    """Ensure local_path is under an allowed root. Raises ValueError otherwise."""
    allowed_roots = settings.allowed_local_roots_list
    resolved = Path(local_path).resolve()
    for root in allowed_roots:
        if resolved.is_relative_to(Path(root).resolve()):
            return resolved
    raise ValueError(
        f"Access denied: '{local_path}' is not under any allowed root "
        f"({', '.join(allowed_roots)})."
    )


def _doc_id(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()[:32]


async def run_web_read(params: WebReadInput) -> str:
    fetched_at = datetime.now(timezone.utc).isoformat()

    # ── Local PDF ─────────────────────────────────────────────────────────────
    if params.local_path:
        resolved = _validate_local_path(params.local_path)
        if not resolved.exists():
            raise FileNotFoundError(f"File not found: {resolved}")

        cache_key = f"local:{resolved}"
        if not params.force_refresh:
            cached = get_page_cache(cache_key)
            if cached:
                cached["metadata"]["cache_hit"] = True
                # キャッシュにはフルコンテンツを保存 → ここで max_chars を適用
                if params.max_chars is not None and len(cached["content"]) > params.max_chars:
                    cached["content"] = cached["content"][: params.max_chars]
                    cached["metadata"]["content_truncated"] = True
                return json.dumps(cached, ensure_ascii=False)

        title, pages = extract_pdf(resolved)
        full_text = "\n\n".join(f"[Page {p}]\n{t}" for p, t in pages)
        # キャッシュにはフルコンテンツを保存（max_chars はキャッシュ後に適用）
        content = full_text if params.max_chars is None else full_text[: params.max_chars]
        truncated = False if params.max_chars is None else len(full_text) > params.max_chars

        all_chunks = []
        for page_num, page_text in pages:
            all_chunks.extend(
                chunk_text(page_text, page=page_num, id_prefix=_doc_id(cache_key))
            )

        doc_id = _doc_id(cache_key)
        upsert_document(
            doc_id=doc_id,
            input_url=None,
            final_url=None,
            local_path=str(resolved),
            title=title or resolved.name,
            source_type="pdf",
            fetched_at=fetched_at,
            extraction_method="pymupdf",
            content=full_text,
            chunks=[c.__dict__ for c in all_chunks],
        )

        # キャッシュにはフルコンテンツを保存する
        output_for_cache = WebReadOutput(
            local_path=str(resolved),
            title=title or resolved.name,
            fetched_at=fetched_at,
            source_type="pdf",
            extraction_method="pymupdf",
            content_format=params.content_format,
            content=full_text,  # フルコンテンツをキャッシュ
            chunks=(
                [
                    Chunk(
                        chunk_id=c.chunk_id,
                        text=c.text,
                        page=c.page,
                        char_start=c.char_start,
                        char_end=c.char_end,
                    )
                    for c in all_chunks
                ]
                if params.return_chunks
                else []
            ),
            links=[],
            metadata=WebReadMetadata(
                cache_hit=False,
                content_truncated=False,
            ),
        )
        data = output_for_cache.model_dump()
        set_page_cache(cache_key, data)
        # 返却用: max_chars を適用
        if params.max_chars is not None and len(full_text) > params.max_chars:
            data["content"] = full_text[: params.max_chars]
            data["metadata"]["content_truncated"] = True
        return json.dumps(data, ensure_ascii=False)

    # ── Remote URL ────────────────────────────────────────────────────────────
    url = params.url  # type: ignore[assignment]
    validate_url(url)

    cache_key = f"url:{url}"
    if not params.force_refresh:
        cached = get_page_cache(cache_key)
        if cached:
            cached["metadata"]["cache_hit"] = True
            # キャッシュにはフルコンテンツを保存 → ここで max_chars を適用
            if params.max_chars is not None and len(cached["content"]) > params.max_chars:
                cached["content"] = cached["content"][: params.max_chars]
                cached["metadata"]["content_truncated"] = True
            return json.dumps(cached, ensure_ascii=False)

    fetch_result = await fetch_url(url, timeout_seconds=params.timeout_seconds)
    final_url = fetch_result.final_url
    content_type = fetch_result.content_type

    # Determine source type
    is_pdf = "pdf" in content_type.lower() or url.lower().endswith(".pdf")

    if is_pdf:
        title, pages = extract_pdf(fetch_result.content)
        full_text = "\n\n".join(f"[Page {p}]\n{t}" for p, t in pages)
        extraction_method = "pymupdf"
        source_type = "pdf"
        links: list[str] = []

        all_chunks = []
        for page_num, page_text in pages:
            all_chunks.extend(
                chunk_text(page_text, page=page_num, id_prefix=_doc_id(cache_key))
            )
    else:
        title, full_text, extraction_method = extract_html(
            fetch_result.content, url=final_url, content_type=content_type
        )
        source_type = "html"
        links = extract_links(fetch_result.content, base_url=final_url) if params.return_links else []

        all_chunks = chunk_text(full_text, id_prefix=_doc_id(cache_key))

    content = full_text if params.max_chars is None else full_text[: params.max_chars]
    truncated = False if params.max_chars is None else len(full_text) > params.max_chars

    doc_id = _doc_id(cache_key)
    upsert_document(
        doc_id=doc_id,
        input_url=url,
        final_url=final_url,
        local_path=None,
        title=title,
        source_type=source_type,
        fetched_at=fetched_at,
        extraction_method=extraction_method,
        content=full_text,
        chunks=[c.__dict__ for c in all_chunks],
    )

    output = WebReadOutput(
        input_url=url,
        final_url=final_url,
        title=title,
        fetched_at=fetched_at,
        source_type=source_type,
        extraction_method=extraction_method,
        content_format=params.content_format,
        content=full_text,  # フルコンテンツをキャッシュ
        chunks=(
            [
                Chunk(
                    chunk_id=c.chunk_id,
                    text=c.text,
                    page=c.page,
                    char_start=c.char_start,
                    char_end=c.char_end,
                )
                for c in all_chunks
            ]
            if params.return_chunks
            else []
        ),
        links=links[:200] if params.return_links else [],
        metadata=WebReadMetadata(
            status_code=fetch_result.status_code,
            content_type=content_type,
            cache_hit=False,
            content_truncated=False,
        ),
    )
    data = output.model_dump()
    set_page_cache(cache_key, data)
    # 返却用: max_chars を適用
    if params.max_chars is not None and len(full_text) > params.max_chars:
        data["content"] = full_text[: params.max_chars]
        data["metadata"]["content_truncated"] = True
    return json.dumps(data, ensure_ascii=False)
