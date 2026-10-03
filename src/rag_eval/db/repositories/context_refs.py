from __future__ import annotations

import logging
import uuid

import asyncpg

from rag_eval.db.repositories.base import BaseRepository
from rag_eval.schemas import ChunkContextRefEntity, UnresolvedRefBacklogDTO

logger = logging.getLogger(__name__)

ContextRefInsertTuple = tuple[
    uuid.UUID,
    uuid.UUID,
    int | None,
    int | None,
    uuid.UUID | None,
    uuid.UUID | None,
    str | None,
]


class ChunkContextRefRepository(BaseRepository):
    """Repository managing domain persistence for chunk_context_refs."""

    async def batch_create_refs(
        self,
        refs: list[ChunkContextRefEntity],
        conn: asyncpg.Connection | None = None,
    ) -> int:
        """Batch inserts chunk context references."""
        if not refs:
            return 0

        query = """
        INSERT INTO chunk_context_refs (
            id, chunk_id, char_start, char_end, target_chunk_id, edge_id, target_path
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7
        );
        """
        records: list[ContextRefInsertTuple] = [
            (
                r.id,
                r.chunk_id,
                r.char_start,
                r.char_end,
                r.target_chunk_id,
                r.edge_id,
                r.target_path,
            )
            for r in refs
        ]
        try:
            async with self._connection_scope(conn) as c:
                await c.executemany(query, records)
                return len(records)
        except (asyncpg.PostgresError, OSError, RuntimeError) as exc:
            raise self._translate_error("batch_create_refs", exc) from exc

    async def get_unresolved_backlog(
        self,
        doc_slug: str | None = None,
        limit: int = 50,
        conn: asyncpg.Connection | None = None,
    ) -> list[UnresolvedRefBacklogDTO]:
        """Queries chunks with unresolved external dependencies."""
        query = """
        SELECT
            c.id AS chunk_id,
            d.doc_slug,
            c.path::text AS path,
            c.context_type,
            c.is_all_refs_resolved,
            c.verbatim_text,
            c.contextualized_text,
            cr.id AS ref_id,
            cr.char_start,
            cr.char_end,
            cr.target_chunk_id,
            cr.edge_id,
            cr.target_path,
            c.metadata
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        LEFT JOIN chunk_context_refs cr ON cr.chunk_id = c.id AND cr.target_chunk_id IS NULL
        WHERE c.context_type = 'REQUIRES_EXTERNAL_CONTEXT'
          AND c.is_all_refs_resolved = FALSE
          AND ($1::text IS NULL OR d.doc_slug = $1)
        ORDER BY c.path ASC
        LIMIT $2;
        """
        try:
            async with self._connection_scope(conn) as c:
                rows = await c.fetch(query, doc_slug, limit)
                return [
                    UnresolvedRefBacklogDTO(
                        chunk_id=r["chunk_id"],
                        doc_slug=r["doc_slug"],
                        path=r["path"],
                        context_type=r["context_type"],
                        is_all_refs_resolved=r["is_all_refs_resolved"],
                        verbatim_text=r["verbatim_text"],
                        contextualized_text=r["contextualized_text"] or "",
                        ref_id=r["ref_id"],
                        char_start=r["char_start"],
                        char_end=r["char_end"],
                        target_chunk_id=r["target_chunk_id"],
                        edge_id=r["edge_id"],
                        target_path=r["target_path"],
                        metadata=self._parse_metadata(r["metadata"]),
                    )
                    for r in rows
                ]
        except (asyncpg.PostgresError, OSError, RuntimeError) as exc:
            raise self._translate_error("get_unresolved_backlog", exc) from exc



