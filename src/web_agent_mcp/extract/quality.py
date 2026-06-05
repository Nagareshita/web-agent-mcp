"""Content quality check helpers."""
from __future__ import annotations


def is_meaningful(text: str, min_chars: int = 50) -> bool:
    """Return True if extracted text is likely meaningful content."""
    stripped = text.strip()
    return len(stripped) >= min_chars
