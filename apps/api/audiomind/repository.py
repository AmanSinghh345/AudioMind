from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import DocumentChunk


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Repository:
    def __init__(self, database_path: Path | str):
        self.database_path = str(database_path)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS collections (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    collection_id TEXT NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
                    filename TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    stored_path TEXT NOT NULL,
                    status TEXT NOT NULL,
                    page_count INTEGER NOT NULL DEFAULT 0,
                    chunk_count INTEGER NOT NULL DEFAULT 0,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(collection_id, filename)
                );
                CREATE TABLE IF NOT EXISTS chunks (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                    collection_id TEXT NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
                    filename TEXT NOT NULL,
                    page_number INTEGER NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    chapter TEXT NOT NULL,
                    text TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS qa_history (
                    id TEXT PRIMARY KEY,
                    collection_id TEXT NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    sources_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audiobooks (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                    title TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    voice TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audio_chapters (
                    id TEXT PRIMARY KEY,
                    audiobook_id TEXT NOT NULL REFERENCES audiobooks(id) ON DELETE CASCADE,
                    chapter_number INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    script TEXT NOT NULL,
                    audio_path TEXT,
                    duration REAL,
                    status TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    status TEXT NOT NULL,
                    progress INTEGER NOT NULL DEFAULT 0,
                    payload_json TEXT NOT NULL,
                    result_json TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_documents_collection ON documents(collection_id);
                CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id);
                CREATE INDEX IF NOT EXISTS idx_qa_collection ON qa_history(collection_id);
                """
            )

    def ensure_default_collection(self) -> str:
        existing = self.get_collection_by_name("My Study Library")
        if existing:
            return existing["id"]
        return self.create_collection("My Study Library", "Default AudioMind collection")

    def create_collection(self, name: str, description: str = "") -> str:
        collection_id = str(uuid.uuid4())
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO collections(id, name, description, created_at) VALUES (?, ?, ?, ?)",
                (collection_id, name.strip(), description.strip(), utc_now()),
            )
        return collection_id

    def list_collections(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT c.*, COUNT(d.id) AS document_count
                   FROM collections c LEFT JOIN documents d ON d.collection_id = c.id
                   GROUP BY c.id ORDER BY c.created_at"""
            ).fetchall()
        return [dict(row) for row in rows]

    def get_collection_by_name(self, name: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM collections WHERE name = ?", (name,)
            ).fetchone()
        return dict(row) if row else None

    def create_document(
        self, document_id: str, collection_id: str, filename: str,
        file_type: str, content_hash: str, stored_path: str,
    ) -> None:
        now = utc_now()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO documents(
                    id, collection_id, filename, file_type, content_hash, stored_path,
                    status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'processing', ?, ?)""",
                (document_id, collection_id, filename, file_type, content_hash, stored_path, now, now),
            )

    def finish_document(self, document_id: str, pages: int, chunks: list[DocumentChunk]) -> None:
        with self._connect() as connection:
            connection.executemany(
                """INSERT INTO chunks(
                    id, document_id, collection_id, filename, page_number,
                    chunk_index, chapter, text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        chunk.id, chunk.document_id, chunk.collection_id, chunk.filename,
                        chunk.page_number, chunk.chunk_index, chunk.chapter, chunk.text,
                    )
                    for chunk in chunks
                ],
            )
            connection.execute(
                """UPDATE documents SET status='ready', page_count=?, chunk_count=?,
                   updated_at=? WHERE id=?""",
                (pages, len(chunks), utc_now(), document_id),
            )

    def fail_document(self, document_id: str, error: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE documents SET status='failed', error=?, updated_at=? WHERE id=?",
                (error[:2000], utc_now(), document_id),
            )

    def get_document(self, document_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
        return dict(row) if row else None

    def find_document(self, collection_id: str, filename: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM documents WHERE collection_id=? AND filename=?",
                (collection_id, filename),
            ).fetchone()
        return dict(row) if row else None

    def list_documents(self, collection_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM documents WHERE collection_id=? ORDER BY created_at DESC",
                (collection_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_document(self, document_id: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM documents WHERE id=?", (document_id,))

    def get_document_chunks(self, document_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM chunks WHERE document_id=? ORDER BY chunk_index", (document_id,)
            ).fetchall()
        return [dict(row) for row in rows]

    def list_collection_chunks(self, collection_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM chunks WHERE collection_id=? ORDER BY filename, chunk_index",
                (collection_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def create_audiobook(
        self, document_id: str, title: str, mode: str, voice: str,
        chapters: list[dict[str, Any]],
    ) -> str:
        audiobook_id = str(uuid.uuid4())
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO audiobooks VALUES (?, ?, ?, ?, ?, 'draft', ?)",
                (audiobook_id, document_id, title, mode, voice, utc_now()),
            )
            connection.executemany(
                "INSERT INTO audio_chapters VALUES (?, ?, ?, ?, ?, NULL, NULL, 'script_ready')",
                [
                    (
                        str(uuid.uuid4()), audiobook_id, chapter["number"],
                        chapter["title"], chapter["script"],
                    )
                    for chapter in chapters
                ],
            )
        return audiobook_id

    def get_audiobook(self, audiobook_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            book = connection.execute(
                "SELECT * FROM audiobooks WHERE id=?", (audiobook_id,)
            ).fetchone()
            chapters = connection.execute(
                "SELECT * FROM audio_chapters WHERE audiobook_id=? ORDER BY chapter_number",
                (audiobook_id,),
            ).fetchall()
        if not book:
            return None
        result = dict(book)
        result["chapters"] = [dict(chapter) for chapter in chapters]
        return result

    def list_audiobooks(self, document_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM audiobooks WHERE document_id=? ORDER BY created_at DESC",
                (document_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def update_chapter_script(self, chapter_id: str, script: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE audio_chapters SET script=?, status='script_ready' WHERE id=?",
                (script, chapter_id),
            )

    def get_chapter(self, chapter_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM audio_chapters WHERE id=?", (chapter_id,)
            ).fetchone()
        return dict(row) if row else None

    def update_chapter_audio(
        self, chapter_id: str, audio_path: str, duration: float | None = None,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """UPDATE audio_chapters SET audio_path=?, duration=?, status='ready'
                   WHERE id=?""",
                (audio_path, duration, chapter_id),
            )

    def add_qa(self, collection_id: str, question: str, answer: str, sources: list[dict]) -> str:
        qa_id = str(uuid.uuid4())
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO qa_history VALUES (?, ?, ?, ?, ?, ?)",
                (qa_id, collection_id, question, answer, json.dumps(sources), utc_now()),
            )
        return qa_id

    def list_qa(self, collection_id: str, limit: int = 30) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM qa_history WHERE collection_id=? ORDER BY created_at DESC LIMIT ?",
                (collection_id, limit),
            ).fetchall()
        output = []
        for row in rows:
            item = dict(row)
            item["sources"] = json.loads(item.pop("sources_json"))
            output.append(item)
        return output

    def create_job(self, kind: str, payload: dict[str, Any]) -> str:
        job_id = str(uuid.uuid4())
        now = utc_now()
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO jobs VALUES (?, ?, 'queued', 0, ?, NULL, NULL, ?, ?)",
                (job_id, kind, json.dumps(payload), now, now),
            )
        return job_id

    def update_job(
        self, job_id: str, status: str, progress: int,
        result: dict[str, Any] | None = None, error: str | None = None,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """UPDATE jobs SET status=?, progress=?, result_json=?, error=?, updated_at=?
                   WHERE id=?""",
                (status, max(0, min(progress, 100)), json.dumps(result) if result else None,
                 error, utc_now(), job_id),
            )

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            return None
        item = dict(row)
        item["payload"] = json.loads(item.pop("payload_json"))
        raw_result = item.pop("result_json")
        item["result"] = json.loads(raw_result) if raw_result else None
        return item
