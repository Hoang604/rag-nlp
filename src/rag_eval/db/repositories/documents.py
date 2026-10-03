from __future__ import annotations

import json
import logging
import uuid

import asyncpg

from rag_eval.db.repositories.base import BaseRepository
from rag_eval.schemas import (
    DocumentEntity,
    DocumentStatsDTO,
)

logger = logging.getLogger(__name__)


class DocumentRepository(BaseRepository):
    """Repository managing domain persistence for the 'documents' table."""

    async def upsert(
        self, doc: DocumentEntity, conn: asyncpg.Connection | None = None
    ) -> uuid.UUID:
        """Upserts a document record, returning its authoritative UUID."""
        query = """
        INSERT INTO documents (
            id, doc_slug, title, raw_text, metadata
        ) VALUES (
            $1, $2, $3, $4, $5
        )
        ON CONFLICT (doc_slug) DO UPDATE SET
            title = EXCLUDED.title,
            raw_text = EXCLUDED.raw_text,
            metadata = EXCLUDED.metadata,
            updated_at = CURRENT_TIMESTAMP
        RETURNING id;
        """
        meta_payload = (
            doc.metadata
            if isinstance(doc.metadata, dict)
            else dict(doc.metadata or {})
        )
        try:
            async with self._connection_scope(conn) as c:
                doc_id = await c.fetchval(
                    query,
                    doc.id,
                    doc.doc_slug,
                    doc.title,
                    doc.raw_text,
                    json.dumps(meta_payload),
                )
                return uuid.UUID(str(doc_id))
        except (asyncpg.PostgresError, OSError, RuntimeError) as exc:
            raise self._translate_error(f"upsert_document({doc.doc_slug})", exc) from exc

    async def get_by_slug(
        self, slug: str, conn: asyncpg.Connection | None = None
    ) -> DocumentEntity | None:
        """Retrieves a document entity by unique slug."""
        query = """
        SELECT id, doc_slug, title, raw_text, metadata, created_at, updated_at
        FROM documents
        WHERE doc_slug = $1;
        """
        try:
            async with self._connection_scope(conn) as c:
                row = await c.fetchrow(query, slug)
                if not row:
                    return None
                return self._row_to_entity(row)
        except (asyncpg.PostgresError, OSError, RuntimeError) as exc:
            raise self._translate_error(f"get_document_by_slug({slug})", exc) from exc


    async def list_active(
        self,
        conn: asyncpg.Connection | None = None,
    ) -> list[DocumentEntity]:
        """Lists all active documents."""
        query = """
        SELECT id, doc_slug, title, raw_text, metadata, created_at, updated_at
        FROM documents
        ORDER BY doc_slug ASC;
        """
        try:
            async with self._connection_scope(conn) as c:
                rows = await c.fetch(query)
                return [self._row_to_entity(r) for r in rows]
        except (asyncpg.PostgresError, OSError, RuntimeError) as exc:
            raise self._translate_error("list_active_documents", exc) from exc

    async def list_with_stats(
        self, conn: asyncpg.Connection | None = None
    ) -> list[DocumentStatsDTO]:
        """Lists all documents along with their chunk counts using DocumentStatsDTO."""
        query = """
        SELECT d.id, d.doc_slug, d.title, d.metadata,
               count(c.id) AS chunk_count
        FROM documents d
        LEFT JOIN chunks c ON c.document_id = d.id
        GROUP BY d.id, d.doc_slug, d.title, d.metadata
        ORDER BY d.doc_slug ASC;
        """
        try:
            async with self._connection_scope(conn) as c:
                rows = await c.fetch(query)
                return [
                    DocumentStatsDTO(
                        id=uuid.UUID(str(r["id"])),
                        doc_slug=str(r["doc_slug"]),
                        title=str(r["title"]),
                        metadata=self._parse_metadata(r["metadata"]),
                        chunk_count=int(r["chunk_count"]),
                    )
                    for r in rows
                ]
        except (asyncpg.PostgresError, OSError, RuntimeError) as exc:
            raise self._translate_error("list_documents_with_stats", exc) from exc


    def _row_to_entity(self, r: asyncpg.Record) -> DocumentEntity:
        return DocumentEntity(
            id=uuid.UUID(str(r["id"])),
            doc_slug=str(r["doc_slug"]),
            title=str(r["title"]),
            raw_text=r["raw_text"] if "raw_text" in r and r["raw_text"] is not None else None,
            metadata=self._parse_metadata(r["metadata"]),
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )

