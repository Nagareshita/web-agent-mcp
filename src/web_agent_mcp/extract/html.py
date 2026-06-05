"""HTML content extraction with fallback chain."""
from __future__ import annotations

import re
from typing import Optional


def extract_html(raw_bytes: bytes, url: str = "", content_type: str = "") -> tuple[str, str, str]:
    """Return (title, text, extraction_method).

    Tries trafilatura → readability-lxml → html2text in order.
    """
    encoding = _detect_encoding(content_type)
    html_str: Optional[str] = None

    try:
        html_str = raw_bytes.decode(encoding or "utf-8", errors="replace")
    except Exception:
        html_str = raw_bytes.decode("latin-1", errors="replace")

    title = _extract_title(html_str)

    # 1. trafilatura
    try:
        import trafilatura

        # Extract metadata separately for title
        meta = trafilatura.extract_metadata(html_str, default_url=url or None)
        if meta and meta.title:
            title = meta.title

        # Extract content as plain string (no with_metadata to avoid Metadata object)
        result = trafilatura.extract(
            html_str,
            url=url or None,
            include_links=False,
            include_tables=True,
            output_format="markdown",
            deduplicate=True,
        )
        if result and isinstance(result, str) and len(result.strip()) > 100:
            return title, _remove_duplicate_blocks(result), "trafilatura"
    except Exception:
        pass

    # 2. readability-lxml
    try:
        from readability import Document  # type: ignore

        doc = Document(html_str)
        if not title:
            title = doc.title()
        summary_html = doc.summary()

        import html2text as h2t

        h = h2t.HTML2Text()
        h.ignore_links = False
        h.body_width = 0
        text = h.handle(summary_html).strip()
        if text and len(text) > 50:
            return title, text, "readability"
    except Exception:
        pass

    # 3. html2text fallback
    try:
        import html2text as h2t

        h = h2t.HTML2Text()
        h.ignore_links = False
        h.body_width = 0
        text = h.handle(html_str).strip()
        return title, text, "html2text"
    except Exception:
        pass

    return title, html_str, "raw"


def extract_links(raw_bytes: bytes, base_url: str = "") -> list[str]:
    """Extract all href links from HTML."""
    try:
        from html.parser import HTMLParser
        from urllib.parse import urljoin

        class _LinkParser(HTMLParser):
            links: list[str] = []

            def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
                if tag == "a":
                    for name, val in attrs:
                        if name == "href" and val:
                            self.links.append(val)

        parser = _LinkParser()
        parser.links = []
        text = raw_bytes.decode("utf-8", errors="replace")
        parser.feed(text)
        return [urljoin(base_url, lnk) for lnk in parser.links if lnk.startswith(("http", "/"))]
    except Exception:
        return []


def _extract_title(html: str) -> str:
    match = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return ""


def _detect_encoding(content_type: str) -> Optional[str]:
    match = re.search(r"charset=([^\s;]+)", content_type, re.IGNORECASE)
    if match:
        return match.group(1).strip('"\'')
    return None


def _remove_duplicate_blocks(text: str) -> str:
    """Remove duplicate paragraphs/blocks within extracted text.

    Splits text on blank lines, hashes each block, and keeps only the first
    occurrence. This addresses within-document duplication that trafilatura
    occasionally produces when the same content appears in multiple DOM regions.
    """
    blocks = re.split(r"\n{2,}", text)
    seen: set[str] = set()
    unique: list[str] = []
    for block in blocks:
        normalized = re.sub(r"\s+", " ", block).strip()
        if not normalized:
            continue
        if normalized not in seen:
            seen.add(normalized)
            unique.append(block.strip())
    return "\n\n".join(unique)
