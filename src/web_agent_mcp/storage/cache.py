"""Disk cache using diskcache for HTTP responses and search results."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Optional

import diskcache  # type: ignore

from web_agent_mcp.config import settings

_SEARCH_CACHE_TTL = 3600  # 1 hour
_PAGE_CACHE_TTL = 86400  # 24 hours

_cache: Optional[diskcache.Cache] = None


def _get_cache() -> diskcache.Cache:
    global _cache
    if _cache is None:
        Path(settings.cache_dir).mkdir(parents=True, exist_ok=True)
        _cache = diskcache.Cache(settings.cache_dir)
    return _cache


def cache_key(namespace: str, value: str) -> str:
    digest = hashlib.sha256(value.encode()).hexdigest()
    return f"{namespace}:{digest}"


def get_search_cache(query: str) -> Optional[dict[str, Any]]:
    key = cache_key("search", query)
    result = _get_cache().get(key)
    return result  # type: ignore[return-value]


def set_search_cache(query: str, data: dict[str, Any]) -> None:
    key = cache_key("search", query)
    _get_cache().set(key, data, expire=_SEARCH_CACHE_TTL)


def get_page_cache(url: str) -> Optional[dict[str, Any]]:
    key = cache_key("page", url)
    result = _get_cache().get(key)
    return result  # type: ignore[return-value]


def set_page_cache(url: str, data: dict[str, Any]) -> None:
    key = cache_key("page", url)
    _get_cache().set(key, data, expire=_PAGE_CACHE_TTL)


def cache_stats() -> dict[str, int]:
    c = _get_cache()
    search_count = 0
    page_count = 0
    for k in c.iterkeys():
        if isinstance(k, str):
            if k.startswith("search:"):
                search_count += 1
            elif k.startswith("page:"):
                page_count += 1
    size_bytes = c.volume()
    return {
        "search_cache_count": search_count,
        "page_cache_count": page_count,
        "size_bytes": size_bytes,
    }
