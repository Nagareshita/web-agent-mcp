"""Text chunking utilities."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Optional


@dataclass
class TextChunk:
    chunk_id: str
    text: str
    page: Optional[int]
    char_start: int
    char_end: int


def chunk_text(
    text: str,
    chunk_size: int = 1200,
    overlap: int = 100,
    page: Optional[int] = None,
    id_prefix: str = "",
) -> list[TextChunk]:
    """Split text into overlapping chunks."""
    chunks: list[TextChunk] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk_text_str = text[start:end]
        chunk_id = _make_chunk_id(id_prefix, start, chunk_text_str)
        chunks.append(
            TextChunk(
                chunk_id=chunk_id,
                text=chunk_text_str,
                page=page,
                char_start=start,
                char_end=end,
            )
        )
        if end == len(text):
            break
        start = end - overlap
    return chunks


def _make_chunk_id(prefix: str, start: int, text: str) -> str:
    digest = hashlib.sha256(f"{prefix}:{start}:{text[:64]}".encode()).hexdigest()[:16]
    return f"{prefix[:16]}_{digest}" if prefix else digest
