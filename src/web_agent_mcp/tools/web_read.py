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
from web_agent_mcp.fetch.browser import fetch_url_browser
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
    return_chunks: bool = Field(
        False,
        description=(
            "Include chunked content in output. Default false to keep response small. "
            "Set true only when you need chunk-level access for local_document_search."
        ),
    )
    return_links: bool = Field(
        False,
        description="Include extracted hyperlinks in output. Default false to keep response small.",
    )
    timeout_seconds: int = Field(30, description="HTTP request timeout in seconds", ge=5, le=120)
    use_browser: bool = Field(
        False,
        description=(
            "Use Playwright headless Chromium to render JavaScript before extraction. "
            "Automatic JS-template detection (${...}) triggers browser fallback automatically. "
            "Set to true to force browser rendering regardless."
        ),
    )
    page: int = Field(
        0,
        description=(
            "0-indexed page number when paginating large content. "
            "When content exceeds 12000 chars, pagination is applied automatically. "
            "Fetch subsequent pages with page=1, page=2, ... up to metadata.total_pages-1."
        ),
        ge=0,
    )
    page_size: Optional[int] = Field(
        None,
        description=(
            "Characters per page. Defaults to 12000 automatically when content is large. "
            "metadata.total_pages and metadata.total_chars show the full document size."
        ),
        ge=500,
    )

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


# When content exceeds this threshold and page_size is not set, apply automatically.
_AUTO_PAGE_SIZE = 12000


def _doc_id(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()[:32]


def _effective_page_size(page_size: int | None, content_len: int) -> int | None:
    """Return the page_size to use: explicit value, auto value, or None."""
    if page_size is not None:
        return page_size
    if content_len > _AUTO_PAGE_SIZE:
        return _AUTO_PAGE_SIZE
    return None


def _apply_pagination(data: dict, full_text: str, page: int, page_size: int | None) -> dict:
    """Slice content to the requested page and populate pagination metadata."""
    import math

    effective = _effective_page_size(page_size, len(full_text))
    if effective is None:
        return data

    total_chars = len(full_text)
    total_pages = math.ceil(total_chars / effective) if total_chars > 0 else 1
    page = min(page, total_pages - 1)  # clamp to valid range

    start = page * effective
    end = start + effective
    sliced = full_text[start:end]

    data["content"] = sliced
    data["metadata"]["total_chars"] = total_chars
    data["metadata"]["total_pages"] = total_pages
    data["metadata"]["current_page"] = page
    data["metadata"]["content_truncated"] = end < total_chars
    return data


def _looks_like_unrendered_spa(text: str) -> bool:
    """Return True when extracted text looks like un-rendered JavaScript template output.

    Matches patterns such as ${abbr}, ${title}, {{variable}} that indicate the JS
    template engine has not been executed (server-side rendering missing).
    """
    # Count ${...} and {{...}} template variable occurrences
    dollar_vars = re.findall(r'\$\{[^}]{1,40}\}', text)
    mustache_vars = re.findall(r'\{\{[^}]{1,40}\}\}', text)
    return len(dollar_vars) + len(mustache_vars) >= 2


def _spa_score(text: str) -> int:
    """Count JS template variables in text (lower = better rendered)."""
    dollar_vars = re.findall(r'\$\{[^}]{1,40}\}', text)
    mustache_vars = re.findall(r'\{\{[^}]{1,40}\}\}', text)
    return len(dollar_vars) + len(mustache_vars)


def _strip_template_vars(text: str) -> str:
    """Remove residual JS template variables like ${title} or {{name}} from text."""
    text = re.sub(r'\$\{[^}]{1,40}\}', '', text)
    text = re.sub(r'\{\{[^}]{1,40}\}\}', '', text)
    # Collapse multiple blank lines that may result
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


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

    # Cache key: use plain URL for both modes; if browser is forced, use a separate key.
    # After auto-detection we may upgrade to browser – cache under the same url: key
    # so subsequent calls benefit from the rendered result.
    cache_key = f"url:{url}"
    if not params.force_refresh:
        cached = get_page_cache(cache_key)
        if cached:
            cached["metadata"]["cache_hit"] = True
            full_cached = cached["content"]
            # Apply max_chars
            if params.max_chars is not None and len(full_cached) > params.max_chars:
                cached["content"] = full_cached[: params.max_chars]
                cached["metadata"]["content_truncated"] = True
            # Apply pagination (auto or explicit)
            cached = _apply_pagination(cached, full_cached, params.page, params.page_size)
            # Remove chunks/links from cached response unless explicitly requested
            if not params.return_chunks:
                cached["chunks"] = []
            if not params.return_links:
                cached["links"] = []
            return json.dumps(cached, ensure_ascii=False)

    # ── Step 1: Plain HTTP fetch ──────────────────────────────────────────────
    used_browser = params.use_browser
    if params.use_browser:
        fetch_result = await fetch_url_browser(url, timeout_seconds=params.timeout_seconds)
    else:
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

    # ── Step 2: SPA auto-detection – retry with Playwright if needed ──────────
    if not params.use_browser and not is_pdf and _looks_like_unrendered_spa(full_text):
        try:
            fetch_result2 = await fetch_url_browser(url, timeout_seconds=params.timeout_seconds)
            title2, full_text2, extraction_method2 = extract_html(
                fetch_result2.content, url=fetch_result2.final_url, content_type=fetch_result2.content_type
            )
            # Use the browser result when it provides more content or fewer template vars
            spa_before = _spa_score(full_text)
            spa_after = _spa_score(full_text2)
            if spa_after < spa_before or len(full_text2.strip()) > len(full_text.strip()):
                fetch_result = fetch_result2
                final_url = fetch_result2.final_url
                content_type = fetch_result2.content_type
                title = title2
                full_text = full_text2
                extraction_method = extraction_method2
                links = extract_links(fetch_result2.content, base_url=final_url) if params.return_links else []
                all_chunks = chunk_text(full_text, id_prefix=_doc_id(cache_key))
                used_browser = True
        except Exception:
            pass  # Keep the HTTP result on browser failure

    # Strip any residual JS template variables from the final text
    if used_browser and _spa_score(full_text) > 0:
        full_text = _strip_template_vars(full_text)
        all_chunks = chunk_text(full_text, id_prefix=_doc_id(cache_key))

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

    # Build the output object; store full content and full chunks/links in cache,
    # then strip them from the returned response if not requested.
    output = WebReadOutput(
        input_url=url,
        final_url=final_url,
        title=title,
        fetched_at=fetched_at,
        source_type=source_type,
        extraction_method=extraction_method,
        content_format=params.content_format,
        content=full_text,  # フルコンテンツをキャッシュに保存
        chunks=[
            Chunk(
                chunk_id=c.chunk_id,
                text=c.text,
                page=c.page,
                char_start=c.char_start,
                char_end=c.char_end,
            )
            for c in all_chunks
        ],
        links=links[:200],
        metadata=WebReadMetadata(
            status_code=fetch_result.status_code,
            content_type=content_type,
            cache_hit=False,
            content_truncated=False,
            used_browser=used_browser,
        ),
    )
    data = output.model_dump()
    set_page_cache(cache_key, data)

    # Strip chunks/links from response unless caller asked for them
    if not params.return_chunks:
        data["chunks"] = []
    if not params.return_links:
        data["links"] = []

    # Apply max_chars and auto-pagination on the return value (cache keeps full content)
    if params.max_chars is not None and len(full_text) > params.max_chars:
        data["content"] = full_text[: params.max_chars]
        data["metadata"]["content_truncated"] = True
    data = _apply_pagination(data, full_text, params.page, params.page_size)
    return json.dumps(data, ensure_ascii=False)

