"""web_agent_mcp server - Streamable HTTP MCP server entry point."""
from __future__ import annotations

import json
import logging

from mcp.server.fastmcp import FastMCP

from web_agent_mcp.config import settings
from web_agent_mcp.tools.cache_status import CacheStatusInput, run_cache_status
from web_agent_mcp.tools.local_document_search import (
    LocalDocumentSearchInput,
    run_local_document_search,
)
from web_agent_mcp.tools.web_read import WebReadInput, run_web_read
from web_agent_mcp.tools.web_read_many import WebReadManyInput, run_web_read_many
from web_agent_mcp.tools.web_search import WebSearchInput, run_web_search

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("web_agent_mcp")

mcp = FastMCP(
    "web_agent_mcp",
    host=settings.host,
    port=settings.port,
    streamable_http_path=settings.mcp_path.rstrip("/") or "/mcp",
    stateless_http=True,
)


# ─── Tool registrations ───────────────────────────────────────────────────────


@mcp.tool(
    name="web_search",
    annotations={
        "title": "Web Search",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def web_search(params: WebSearchInput) -> str:
    """Search the web using SearXNG.

    Returns ranked search results including title, URL, snippet, and source domain.
    Results are cached for 1 hour. Use 'site' to restrict results to a specific domain.

    Args:
        params: WebSearchInput containing query, max_results, language, safe_search, site.

    Returns:
        JSON string with query, provider, results list, and metadata.
    """
    return await run_web_search(params)


@mcp.tool(
    name="web_read",
    annotations={
        "title": "Read Web Page or Local PDF",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def web_read(params: WebReadInput) -> str:
    """Fetch and extract content from a URL or a local PDF file.

    For URLs: validates against SSRF threats, fetches the page, extracts main content
    using trafilatura → readability → html2text fallback chain, and stores in FTS index.

    For local files: only paths under WEB_AGENT_ALLOWED_LOCAL_ROOTS (/app/docs) are accessible.
    PDFs are extracted page by page using PyMuPDF.

    Content is cached for 24 hours. Use force_refresh=true to bypass the cache.

    max_chars defaults to None (no truncation — full content is returned).
    Set max_chars to an integer only when you intentionally want a summary or shorter excerpt.

    Args:
        params: WebReadInput with url or local_path and extraction options.

    Returns:
        JSON string with title, content, chunks, links, and metadata.
    """
    return await run_web_read(params)


@mcp.tool(
    name="web_read_many",
    annotations={
        "title": "Read Multiple Web Pages",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def web_read_many(params: WebReadManyInput) -> str:
    """Fetch and extract content from multiple URLs concurrently.

    Processes up to max_concurrency URLs in parallel. Failed URLs are returned
    in the errors list rather than raising an exception.

    max_chars_per_url defaults to None (no truncation per URL).
    Set it to an integer when you need to limit output size for many-URL requests.

    Args:
        params: WebReadManyInput with urls list, max_concurrency, max_chars_per_url.

    Returns:
        JSON string with results list and errors list.
    """
    return await run_web_read_many(params)


@mcp.tool(
    name="local_document_search",
    annotations={
        "title": "Search Indexed Documents (FTS5)",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def local_document_search(params: LocalDocumentSearchInput) -> str:
    """Full-text search over previously fetched web pages and PDFs.

    Uses SQLite FTS5 to search the local index built by web_read/web_read_many.
    Filter by source type ('web', 'pdf', or 'all').

    Args:
        params: LocalDocumentSearchInput with query, source, max_results.

    Returns:
        JSON string with matched documents, snippets, and BM25 scores.
    """
    return await run_local_document_search(params)


@mcp.tool(
    name="cache_status",
    annotations={
        "title": "Cache and Index Status",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def cache_status(params: CacheStatusInput) -> str:
    """Return statistics about the disk cache and FTS5 index.

    Reports document count, search cache entry count, and total cache size in bytes.

    Args:
        params: CacheStatusInput.

    Returns:
        JSON string with cache_dir, index_dir, document_count, search_cache_count, size_bytes.
    """
    return await run_cache_status(params)


# ─── Entry point ──────────────────────────────────────────────────────────────


def main() -> None:
    logger.info(
        "Starting web_agent_mcp on %s:%d%s",
        settings.host,
        settings.port,
        settings.mcp_path,
    )
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
