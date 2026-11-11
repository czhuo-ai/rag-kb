"""索引存储：SQLite 存文档与切片，向量以 float32 二进制落在同一张表里。

小规模（万级切片）够用；换成 pgvector 时把 retrieve 里的向量检索替换掉即可。
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np

from .config import INDEX
from .chunk import Chunk


SCHEMA = """
CREATE TABLE IF NOT EXISTS docs (
  id INTEGER PRIMARY KEY,
  name TEXT UNIQUE,
  kind TEXT,
  chars INTEGER,
  chunks INTEGER,
  strategy TEXT
);
CREATE TABLE IF NOT EXISTS chunks (
  id INTEGER PRIMARY KEY,
  doc_id INTEGER,
  ord INTEGER,
  heading TEXT,
  text TEXT
);
CREATE TABLE IF NOT EXISTS embeddings (
  chunk_id INTEGER PRIMARY KEY,
  dim INTEGER,
  vec BLOB
);
CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_id);
"""


def connect(path: Path | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path or INDEX))
    conn.executescript(SCHEMA)
    return conn


def reset(conn: sqlite3.Connection) -> None:
    conn.executescript("DELETE FROM embeddings; DELETE FROM chunks; DELETE FROM docs;")
    conn.commit()


def add_doc(conn: sqlite3.Connection, name: str, kind: str, chars: int,
            chunks: list[Chunk], vectors: list[list[float]], strategy: str) -> int:
    cur = conn.execute(
        "INSERT OR REPLACE INTO docs(name, kind, chars, chunks, strategy) VALUES (?,?,?,?,?)",
        (name, kind, chars, len(chunks), strategy),
    )
    doc_id = int(cur.lastrowid)
    for chunk, vec in zip(chunks, vectors):
        c = conn.execute(
            "INSERT INTO chunks(doc_id, ord, heading, text) VALUES (?,?,?,?)",
            (doc_id, chunk.ord, chunk.heading, chunk.text),
        )
        arr = np.asarray(vec, dtype="float32")
        conn.execute(
            "INSERT OR REPLACE INTO embeddings(chunk_id, dim, vec) VALUES (?,?,?)",
            (int(c.lastrowid), len(arr), arr.tobytes()),
        )
    conn.commit()
    return doc_id


def load_all(conn: sqlite3.Connection) -> tuple[list[dict], np.ndarray]:
    rows = conn.execute(
        "SELECT c.id, c.doc_id, c.ord, c.heading, c.text, d.name "
        "FROM chunks c JOIN docs d ON d.id = c.doc_id ORDER BY c.id"
    ).fetchall()
    metas = [
        {"id": r[0], "doc_id": r[1], "ord": r[2], "heading": r[3], "text": r[4], "doc": r[5]}
        for r in rows
    ]
    vecs = conn.execute("SELECT chunk_id, vec FROM embeddings ORDER BY chunk_id").fetchall()
    if not vecs:
        return metas, np.zeros((0, 1), dtype="float32")
    mat = np.vstack([np.frombuffer(v, dtype="float32") for _, v in vecs])
    # 归一化，查询时只做点积
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return metas, (mat / norms).astype("float32")


def stats(conn: sqlite3.Connection) -> dict:
    docs = conn.execute("SELECT COUNT(*), COALESCE(SUM(chars),0) FROM docs").fetchone()
    chunks = conn.execute("SELECT COUNT(*), COALESCE(SUM(LENGTH(text)),0) FROM chunks").fetchone()
    return {
        "docs": docs[0],
        "chars": docs[1],
        "chunks": chunks[0],
        "chunk_chars": chunks[1],
        "avg_chunk_chars": round(chunks[1] / chunks[0], 1) if chunks[0] else 0,
    }
