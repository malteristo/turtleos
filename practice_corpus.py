"""Local, derived full-text index for primitive-owned source corpora."""

from __future__ import annotations

import json
import re
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Iterable


INDEX_RELATIVE_PATH = Path("documents") / ".derived" / "corpus.sqlite3"
MAX_QUERY_TERMS = 12
MAX_RESULT_LIMIT = 12


def index_path(practice_dir: str | Path) -> Path:
    return Path(practice_dir) / INDEX_RELATIVE_PATH


def connect(practice_dir: str | Path) -> sqlite3.Connection:
    path = index_path(practice_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.executescript(
        """
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS sources (
            source_id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            mime TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            document_date TEXT,
            manifest_path TEXT NOT NULL
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks USING fts5(
            source_id UNINDEXED,
            page UNINDEXED,
            chunk_no UNINDEXED,
            text,
            tokenize='unicode61 remove_diacritics 2'
        );
        """
    )
    return db


def replace_source(
    practice_dir: str | Path,
    manifest: dict,
    pages: Iterable[tuple[int, str]],
) -> int:
    """Replace one source's derived chunks. Originals and extracts are untouched."""
    source_id = str(manifest["source_id"])
    chunks: list[tuple[str, int, int, str]] = []
    for page, text in pages:
        for chunk_no, chunk in enumerate(_chunks(text)):
            chunks.append((source_id, int(page), chunk_no, chunk))
    with closing(connect(practice_dir)) as db, db:
        db.execute("DELETE FROM chunks WHERE source_id = ?", (source_id,))
        db.execute(
            """
            INSERT OR REPLACE INTO sources
              (source_id, filename, mime, sha256, document_date, manifest_path)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                str(manifest.get("filename") or "source"),
                str(manifest.get("mime") or "application/octet-stream"),
                str(manifest.get("sha256") or ""),
                manifest.get("document_date"),
                str(manifest.get("manifest_path") or ""),
            ),
        )
        db.executemany(
            "INSERT INTO chunks(source_id, page, chunk_no, text) VALUES (?, ?, ?, ?)",
            chunks,
        )
    return len(chunks)


def remove_source(practice_dir: str | Path, source_id: str) -> None:
    with closing(connect(practice_dir)) as db, db:
        db.execute("DELETE FROM chunks WHERE source_id = ?", (source_id,))
        db.execute("DELETE FROM sources WHERE source_id = ?", (source_id,))


def search(
    practice_dir: str | Path,
    query: str,
    *,
    limit: int = 6,
    mime: str | None = None,
    document_date: str | None = None,
) -> list[dict]:
    expression = _fts_expression(query)
    if not expression:
        return []
    limit = max(1, min(MAX_RESULT_LIMIT, int(limit)))
    clauses = ["chunks MATCH ?"]
    params: list[object] = [expression]
    if mime:
        clauses.append("sources.mime = ?")
        params.append(mime)
    if document_date:
        clauses.append("sources.document_date = ?")
        params.append(document_date)
    params.append(limit)
    sql = f"""
        SELECT chunks.source_id, sources.filename, sources.mime,
               sources.document_date, CAST(chunks.page AS INTEGER) AS page,
               snippet(chunks, 3, '[', ']', ' … ', 24) AS excerpt,
               bm25(chunks) AS score
        FROM chunks JOIN sources USING(source_id)
        WHERE {' AND '.join(clauses)}
        ORDER BY score
        LIMIT ?
    """
    with closing(connect(practice_dir)) as db, db:
        rows = db.execute(sql, params).fetchall()
    return [
        {
            **dict(row),
            "citation": citation(row["source_id"], row["page"], row["filename"]),
        }
        for row in rows
    ]


def read_page(practice_dir: str | Path, source_id: str, page: int) -> dict | None:
    with closing(connect(practice_dir)) as db, db:
        source = db.execute(
            "SELECT * FROM sources WHERE source_id = ?", (source_id,)
        ).fetchone()
        chunks = db.execute(
            """
            SELECT text FROM chunks
            WHERE source_id = ? AND page = ?
            ORDER BY CAST(chunk_no AS INTEGER)
            """,
            (source_id, int(page)),
        ).fetchall()
    if source is None or not chunks:
        return None
    return {
        "source_id": source_id,
        "filename": source["filename"],
        "page": int(page),
        "citation": citation(source_id, page, source["filename"]),
        "text": "\n\n".join(row["text"] for row in chunks),
    }


def source_trace(practice_dir: str | Path, source_id: str) -> dict | None:
    with closing(connect(practice_dir)) as db, db:
        row = db.execute(
            """
            SELECT sources.*, COUNT(chunks.rowid) AS chunks,
                   MIN(CAST(chunks.page AS INTEGER)) AS first_page,
                   MAX(CAST(chunks.page AS INTEGER)) AS last_page
            FROM sources LEFT JOIN chunks USING(source_id)
            WHERE sources.source_id = ?
            GROUP BY sources.source_id
            """,
            (source_id,),
        ).fetchone()
    return dict(row) if row else None


def rebuild(practice_dir: str | Path, manifests: Iterable[dict]) -> dict:
    """Delete and recreate only the derived index from supplied manifests."""
    path = index_path(practice_dir)
    for suffix in ("", "-wal", "-shm"):
        candidate = Path(str(path) + suffix)
        if candidate.exists():
            candidate.unlink()
    sources = chunks = 0
    for manifest in manifests:
        pages = []
        for item in manifest.get("extracts") or []:
            extract_path = Path(practice_dir) / str(item["path"])
            if extract_path.is_file():
                pages.append(
                    (int(item.get("page") or 1), extract_path.read_text(encoding="utf-8"))
                )
        if pages:
            chunks += replace_source(practice_dir, manifest, pages)
            sources += 1
    return {"sources": sources, "chunks": chunks, "path": str(path)}


def citation(source_id: str, page: int, filename: str = "") -> str:
    label = filename or source_id
    return f"{label} · p. {int(page)} · source:{source_id}"


def format_results(rows: list[dict]) -> str:
    if not rows:
        return "No matching record evidence."
    return "\n\n".join(
        f"[{row['citation']}]\n{row['excerpt']}" for row in rows
    )


def _chunks(text: str, target: int = 1400, overlap: int = 180) -> list[str]:
    clean = re.sub(r"\r\n?", "\n", text or "").strip()
    if not clean:
        return []
    if len(clean) <= target:
        return [clean]
    result = []
    start = 0
    while start < len(clean):
        end = min(len(clean), start + target)
        if end < len(clean):
            boundary = max(clean.rfind("\n", start + target // 2, end), clean.rfind(" ", start + target // 2, end))
            if boundary > start:
                end = boundary
        result.append(clean[start:end].strip())
        if end >= len(clean):
            break
        start = max(start + 1, end - overlap)
    return [chunk for chunk in result if chunk]


def _fts_expression(query: str) -> str:
    terms = re.findall(r"[\wÀ-ÖØ-öø-ÿ]{2,}", query or "", flags=re.UNICODE)
    return " OR ".join(json.dumps(term) for term in terms[:MAX_QUERY_TERMS])
