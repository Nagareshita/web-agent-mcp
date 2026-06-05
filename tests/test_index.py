"""Tests for SQLite FTS5 index."""
import pytest
import tempfile
import os


def test_index_upsert_and_search(tmp_path, monkeypatch):
    monkeypatch.setenv("WEB_AGENT_INDEX_DIR", str(tmp_path))
    # Reload settings and index module
    import importlib
    import web_agent_mcp.config as cfg
    importlib.reload(cfg)
    import web_agent_mcp.storage.index as idx
    importlib.reload(idx)

    idx.upsert_document(
        doc_id="doc1",
        input_url="https://example.com",
        final_url="https://example.com",
        local_path=None,
        title="Test Document",
        source_type="html",
        fetched_at="2026-01-01T00:00:00Z",
        extraction_method="trafilatura",
        content="Hello FTS5 world test",
        chunks=[
            {
                "chunk_id": "c1",
                "text": "Hello FTS5 world test",
                "page": None,
                "char_start": 0,
                "char_end": 21,
            }
        ],
    )

    results = idx.search_fts("FTS5", max_results=5)
    assert len(results) >= 1
    assert results[0]["document_id"] == "doc1"
