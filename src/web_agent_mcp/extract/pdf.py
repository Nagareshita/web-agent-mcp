"""PDF content extraction using PyMuPDF."""
from __future__ import annotations

from pathlib import Path
from typing import Union


def extract_pdf(source: Union[bytes, Path, str]) -> tuple[str, list[tuple[int, str]]]:
    """Return (title, [(page_number, text), ...]).

    source can be raw bytes, a file path (str/Path).
    """
    import fitz  # PyMuPDF

    if isinstance(source, (str, Path)):
        doc = fitz.open(str(source))
    else:
        doc = fitz.open(stream=source, filetype="pdf")

    title = doc.metadata.get("title", "") or ""
    pages: list[tuple[int, str]] = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")
        if text.strip():
            pages.append((page_num + 1, text))

    doc.close()
    return title, pages
