"""SQLite FTS5 full-text index for documents and chunks."""
from __future__ import annotations

import hashlib
import sqlite3
import threading
from pathlib import Path
from typing import Optional

from web_agent_mcp.config import settings

_local = threading.local()


def _get_conn() -> sqlite3.Connection:
    if not hasattr(_local, "conn"):
        Path(settings.index_dir).mkdir(parents=True, exist_ok=True)
        db_path = Path(settings.index_dir) / "index.db"
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        _init_schema(conn)
        _local.conn = conn
    return _local.conn


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS documents (
          id TEXT PRIMARY KEY,
          input_url TEXT,
          final_url TEXT,
          local_path TEXT,
          title TEXT,
          source_type TEXT,
          fetched_at TEXT,
          extraction_method TEXT,
          content_hash TEXT
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS chunks (
          id TEXT PRIMARY KEY,
          document_id TEXT NOT NULL,
          page INTEGER,
          chunk_index INTEGER NOT NULL,
          text TEXT NOT NULL,
          char_start INTEGER,
          char_end INTEGER,
          FOREIGN KEY(document_id) REFERENCES documents(id)
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS fts_meta (
          fts_rowid INTEGER PRIMARY KEY,
          chunk_id  TEXT NOT NULL,
          document_id TEXT NOT NULL
        )"""
    )
    conn.execute(
        """CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts
           USING fts5(title, text, tokenize='unicode61')"""
    )
    conn.commit()


def upsert_document(
    doc_id: str,
    input_url: Optional[str],
    final_url: Optional[str],
    local_path: Optional[str],
    title: Optional[str],
    source_type: str,
    fetched_at: str,
    extraction_method: str,
    content: str,
    chunks: list[dict],
) -> None:
    conn = _get_conn()
    content_hash = hashlib.sha256(content.encode()).hexdigest()

    conn.execute(
        """INSERT OR REPLACE INTO documents
           (id, input_url, final_url, local_path, title, source_type, fetched_at,
            extraction_method, content_hash)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (doc_id, input_url, final_url, local_path, title, source_type,
         fetched_at, extraction_method, content_hash),
    )

    # Delete old FTS entries and chunks for this document
    old_meta = conn.execute(
        "SELECT fts_rowid FROM fts_meta WHERE document_id=?", (doc_id,)
    ).fetchall()
    for row in old_meta:
        conn.execute("DELETE FROM chunks_fts WHERE rowid=?", (row["fts_rowid"],))
    conn.execute("DELETE FROM fts_meta WHERE document_id=?", (doc_id,))
    conn.execute("DELETE FROM chunks WHERE document_id=?", (doc_id,))

    # Insert new chunks + FTS entries
    for i, chunk in enumerate(chunks):
        conn.execute(
            """INSERT OR IGNORE INTO chunks
               (id, document_id, page, chunk_index, text, char_start, char_end)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (chunk["chunk_id"], doc_id, chunk.get("page"), i,
             chunk["text"], chunk.get("char_start", 0), chunk.get("char_end", 0)),
        )
        conn.execute(
            "INSERT INTO chunks_fts(title, text) VALUES(?, ?)",
            (title or "", chunk["text"]),
        )
        fts_rowid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            "INSERT INTO fts_meta(fts_rowid, chunk_id, document_id) VALUES(?,?,?)",
            (fts_rowid, chunk["chunk_id"], doc_id),
        )

    conn.commit()


def search_fts(query: str, max_results: int = 10, source: str = "all") -> list[dict]:
    conn = _get_conn()
    fts_query = " ".join(
        f'"{w.replace(chr(34), "")}"' for w in query.split() if w
    )
    if not fts_query:
        return []

    sql = """
        SELECT
          d.id          AS document_id,
          d.title       AS title,
          d.input_url   AS url,
          d.source_type AS source_type,
          ch.page       AS page,
          meta.chunk_id AS chunk_id,
          snippet(chunks_fts, 1, '<b>', '</b>', '...', 32) AS snippet,
          bm25(chunks_fts) AS score
        FROM chunks_fts
        JOIN fts_meta meta ON meta.fts_rowid  = chunks_fts.rowid
        JOIN chunks   ch   ON ch.id           = meta.chunk_id
        JOIN documents d   ON d.id            = meta.document_id
        WHERE chunks_fts MATCH ?
    """
    params: list = [fts_query]

    if source == "web":
        sql += " AND d.source_type = 'html'"
    elif source == "pdf":
        sql += " AND d.source_type = 'pdf'"

    sql += " ORDER BY score LIMIT ?"
    params.append(max_results)

    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def document_count() -> int:
    conn = _get_conn()
    row = conn.execute("SELECT COUNT(*) AS c FROM documents").fetchone()
    return row["c"] if row else 0
