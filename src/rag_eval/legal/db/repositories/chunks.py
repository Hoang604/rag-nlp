from __future__ import annotations

import json
import logging
import uuid

import asyncpg

from rag_eval.legal.db.repositories.base import BaseRepository
from rag_eval.legal.schemas import (
    ChunkEntity,
    HierarchyNodeDTO,
    HybridSearchQuery,
    SearchHitDTO,
    VerbatimGrepQuery,
)

logger = logging.getLogger(__name__)


ChunkInsertTuple = tuple[
    uuid.UUID,
    uuid.UUID,
    str,
    str,
    str,
    int,
    int,
    str,
    bool,
    list[float] | None,
    str,
]


class ChunkRepository(BaseRepository):
    """Repository managing domain persistence, indexing, and search for the 'chunks' table."""

    async def upsert_batch(
        self, chunks: list[ChunkEntity], conn: asyncpg.Connection | None = None
    ) -> dict[str, uuid.UUID]:
        """Batch upserts chunk entities, returning a mapping of path to UUID."""
        if not chunks:
            return {}

        query = """
        INSERT INTO chunks (
            id, document_id, path, verbatim_text, contextualized_text,
            start_line, end_line, context_type, is_all_refs_resolved,
            embedding, metadata
        ) VALUES (
            $1, $2, $3::ltree, $4, $5,
            $6, $7, $8, $9,
            $10, $11
        )
        ON CONFLICT (path) DO UPDATE SET
            verbatim_text = EXCLUDED.verbatim_text,
            contextualized_text = EXCLUDED.contextualized_text,
            start_line = EXCLUDED.start_line,
            end_line = EXCLUDED.end_line,
            context_type = EXCLUDED.context_type,
            is_all_refs_resolved = EXCLUDED.is_all_refs_resolved,
            embedding = COALESCE(EXCLUDED.embedding, chunks.embedding),
            metadata = EXCLUDED.metadata,
            updated_at = CURRENT_TIMESTAMP;
        """
        records: list[ChunkInsertTuple] = []
        for c in chunks:
            meta = c.metadata if isinstance(c.metadata, dict) else dict(c.metadata or {})
            records.append(
                (
                    c.id,
                    c.document_id,
                    c.path,
                    c.verbatim_text,
                    c.contextualized_text,
                    c.start_line,
                    c.end_line,
                    c.context_type,
                    c.is_all_refs_resolved,
                    c.embedding,
                    json.dumps(meta),
                )
            )

        all_paths = [c.path for c in chunks]
        try:
            async with self._connection_scope(conn) as c:
                await c.executemany(query, records)
                rows = await c.fetch(
                    "SELECT id, path::text FROM chunks WHERE path = ANY($1::ltree[]);",
                    all_paths,
                )
                return {str(r["path"]): uuid.UUID(str(r["id"])) for r in rows}
        except (asyncpg.PostgresError, OSError, RuntimeError) as exc:
            raise self._translate_error("upsert_chunks_batch", exc) from exc

    async def get_by_id(
        self, chunk_id: uuid.UUID, conn: asyncpg.Connection | None = None
    ) -> ChunkEntity | None:
        """Retrieves a chunk by its primary key UUID."""
        query = """
        SELECT id, document_id, path::text, verbatim_text, contextualized_text,
               start_line, end_line, context_type, is_all_refs_resolved,
               embedding, tsv_content, metadata, created_at, updated_at
        FROM chunks WHERE id = $1;
        """
        try:
            async with self._connection_scope(conn) as c:
                row = await c.fetchrow(query, chunk_id)
                return self._row_to_entity(row) if row else None
        except (asyncpg.PostgresError, OSError, RuntimeError) as exc:
            raise self._translate_error(f"get_chunk_by_id({chunk_id})", exc) from exc

    async def get_by_path(
        self, path: str, conn: asyncpg.Connection | None = None
    ) -> ChunkEntity | None:
        """Retrieves a chunk by its unique ltree path."""
        query = """
        SELECT id, document_id, path::text, verbatim_text, contextualized_text,
               start_line, end_line, context_type, is_all_refs_resolved,
               embedding, tsv_content, metadata, created_at, updated_at
        FROM chunks WHERE path = $1::ltree;
        """
        try:
            async with self._connection_scope(conn) as c:
                row = await c.fetchrow(query, path)
                return self._row_to_entity(row) if row else None
        except (asyncpg.PostgresError, OSError, RuntimeError) as exc:
            raise self._translate_error(f"get_chunk_by_path({path})", exc) from exc

    async def list_by_document(
        self, document_id: uuid.UUID, conn: asyncpg.Connection | None = None
    ) -> list[ChunkEntity]:
        """Lists all chunks belonging to a document ordered hierarchically by path."""
        query = """
        SELECT id, document_id, path::text, verbatim_text, contextualized_text,
               start_line, end_line, context_type, is_all_refs_resolved,
               embedding, tsv_content, metadata, created_at, updated_at
        FROM chunks WHERE document_id = $1 ORDER BY path ASC;
        """
        try:
            async with self._connection_scope(conn) as c:
                rows = await c.fetch(query, document_id)
                return [self._row_to_entity(r) for r in rows]
        except (asyncpg.PostgresError, OSError, RuntimeError) as exc:
            raise self._translate_error(f"list_chunks_by_document({document_id})", exc) from exc

    async def delete_stale_by_paths(
        self,
        document_id: uuid.UUID,
        stale_paths: list[str],
        conn: asyncpg.Connection | None = None,
    ) -> int:
        """Deletes chunks matching stale paths for a document."""
        if not stale_paths:
            return 0
        query = "DELETE FROM chunks WHERE document_id = $1 AND path = ANY($2::ltree[]);"
        try:
            async with self._connection_scope(conn) as c:
                status = await c.execute(query, document_id, stale_paths)
                return int(status.rsplit(" ", 1)[-1] or 0)
        except (asyncpg.PostgresError, OSError, RuntimeError) as exc:
            raise self._translate_error("delete_stale_chunks", exc) from exc

    async def hybrid_search(
        self, query: HybridSearchQuery, conn: asyncpg.Connection | None = None
    ) -> list[SearchHitDTO]:
        """Executes generalized dense+sparse hybrid search via the hybrid_search stored proc."""
        sql = """
        SELECT 
            chunk_id, doc_slug, doc_title, path, start_line, end_line,
            verbatim_text, contextualized_text, context_type, is_all_refs_resolved,
            metadata, rrf_score, dense_rank, sparse_rank, dense_similarity
        FROM hybrid_search(
            $1, $2::vector, $3::int, $4::int, $5::text[], $6::ltree, $7::boolean, $8::text
        );
        """
        try:
            async with self._connection_scope(conn) as c:
                rows = await c.fetch(
                    sql,
                    query.query_text,
                    query.query_vector,
                    query.match_limit,
                    query.rrf_k,
                    query.target_documents or None,
                    query.path_prefix or None,
                    query.only_resolved,
                    query.ts_config,
                )
                return [
                    SearchHitDTO(
                        chunk_id=uuid.UUID(str(r["chunk_id"])),
                        doc_slug=str(r["doc_slug"]),
                        doc_title=str(r["doc_title"]),
                        path=str(r["path"]),
                        start_line=int(r["start_line"]),
                        end_line=int(r["end_line"]),
                        verbatim_text=str(r["verbatim_text"]),
                        contextualized_text=str(r["contextualized_text"]),
                        context_type=str(r["context_type"]),
                        is_all_refs_resolved=bool(r["is_all_refs_resolved"]),
                        metadata=self._parse_metadata(r["metadata"]),
                        score=float(r["rrf_score"]),
                        dense_rank=int(r["dense_rank"]) if r["dense_rank"] is not None else None,
                        sparse_rank=int(r["sparse_rank"]) if r["sparse_rank"] is not None else None,
                        dense_similarity=float(r["dense_similarity"]),
                    )
                    for r in rows
                ]
        except (asyncpg.PostgresError, OSError, RuntimeError) as exc:
            raise self._translate_error("hybrid_search", exc) from exc

    async def verbatim_grep(
        self, query: VerbatimGrepQuery, conn: asyncpg.Connection | None = None
    ) -> list[SearchHitDTO]:
        """Executes exact / trigram grep search via verbatim_grep stored proc."""
        sql = """
        SELECT 
            chunk_id, doc_slug, doc_title, path, start_line, end_line,
            verbatim_text, contextualized_text, context_type, is_all_refs_resolved,
            metadata, similarity_score
        FROM verbatim_grep(
            $1, $2::text[], $3::ltree, $4::boolean, $5::boolean, $6::boolean, $7::int
        );
        """
        try:
            async with self._connection_scope(conn) as c:
                rows = await c.fetch(
                    sql,
                    query.query_pattern,
                    query.target_documents or None,
                    query.path_prefix or None,
                    query.only_resolved,
                    query.is_regex,
                    query.case_sensitive,
                    query.match_limit,
                )
                return [
                    SearchHitDTO(
                        chunk_id=uuid.UUID(str(r["chunk_id"])),
                        doc_slug=str(r["doc_slug"]),
                        doc_title=str(r["doc_title"]),
                        path=str(r["path"]),
                        start_line=int(r["start_line"]),
                        end_line=int(r["end_line"]),
                        verbatim_text=str(r["verbatim_text"]),
                        contextualized_text=str(r["contextualized_text"]),
                        context_type=str(r["context_type"]),
                        is_all_refs_resolved=bool(r["is_all_refs_resolved"]),
                        metadata=self._parse_metadata(r["metadata"]),
                        score=float(r["similarity_score"]),
                        dense_rank=None,
                        sparse_rank=None,
                        dense_similarity=0.0,
                    )
                    for r in rows
                ]
        except (asyncpg.PostgresError, OSError, RuntimeError) as exc:
            raise self._translate_error("verbatim_grep", exc) from exc

    async def verbatim_grep_count(
        self, query: VerbatimGrepQuery, conn: asyncpg.Connection | None = None
    ) -> int:
        """Executes count for verbatim grep search."""
        sql = """
        SELECT verbatim_grep_count(
            $1, $2::text[], $3::ltree, $4::boolean, $5::boolean, $6::boolean
        );
        """
        try:
            async with self._connection_scope(conn) as c:
                val = await c.fetchval(
                    sql,
                    query.query_pattern,
                    query.target_documents or None,
                    query.path_prefix or None,
                    query.only_resolved,
                    query.is_regex,
                    query.case_sensitive,
                )
                return int(val or 0)
        except (asyncpg.PostgresError, OSError, RuntimeError) as exc:
            raise self._translate_error("verbatim_grep_count", exc) from exc

    async def navigate_hierarchy(
        self,
        document_id: uuid.UUID,
        anchor_path: str,
        direction: str,
        conn: asyncpg.Connection | None = None,
    ) -> list[HierarchyNodeDTO]:
        """Navigates hierarchy tree relative to an anchor path using ltree operations."""
        dir_val = direction.upper()
        if dir_val == "CHILDREN":
            query = """
            SELECT c.id, c.path::text, d.doc_slug, c.start_line, c.end_line,
                   c.verbatim_text, c.contextualized_text, c.metadata
            FROM chunks c
            JOIN documents d ON c.document_id = d.id
            WHERE c.document_id = $1
              AND c.path <@ $2::ltree
              AND c.path != $2::ltree
              AND nlevel(c.path) = nlevel($2::ltree) + 1
            ORDER BY c.path ASC;
            """
        elif dir_val == "PARENT_CHAIN":
            query = """
            SELECT c.id, c.path::text, d.doc_slug, c.start_line, c.end_line,
                   c.verbatim_text, c.contextualized_text, c.metadata
            FROM chunks c
            JOIN documents d ON c.document_id = d.id
            WHERE c.document_id = $1
              AND c.path @> $2::ltree
              AND c.path != $2::ltree
            ORDER BY nlevel(c.path) ASC;
            """
        elif dir_val == "SIBLINGS":
            query = """
            SELECT c.id, c.path::text, d.doc_slug, c.start_line, c.end_line,
                   c.verbatim_text, c.contextualized_text, c.metadata
            FROM chunks c
            JOIN documents d ON c.document_id = d.id
            WHERE c.document_id = $1
              AND subpath(c.path, 0, nlevel(c.path) - 1) = subpath($2::ltree, 0, nlevel($2::ltree) - 1)
              AND nlevel(c.path) = nlevel($2::ltree)
              AND c.path != $2::ltree
            ORDER BY c.path ASC;
            """
        else:
            raise ValueError(f"Unsupported navigation direction: '{direction}'")

        try:
            async with self._connection_scope(conn) as c:
                rows = await c.fetch(query, document_id, anchor_path)
                anchor_level = len(anchor_path.split("."))
                return [
                    HierarchyNodeDTO(
                        chunk_id=uuid.UUID(str(r["id"])),
                        path=str(r["path"]),
                        doc_slug=str(r["doc_slug"]),
                        start_line=int(r["start_line"]),
                        end_line=int(r["end_line"]),
                        verbatim_text=str(r["verbatim_text"]),
                        contextualized_text=str(r["contextualized_text"]),
                        metadata=self._parse_metadata(r["metadata"]),
                        relative_depth=len(str(r["path"]).split(".")) - anchor_level,
                    )
                    for r in rows
                ]
        except (asyncpg.PostgresError, OSError, RuntimeError) as exc:
            raise self._translate_error("navigate_hierarchy", exc) from exc


    async def reindex_and_vacuum(
        self, conn: asyncpg.Connection | None = None
    ) -> None:
        """Executes maintenance reindex and vacuum commands."""
        try:
            async with self._connection_scope(conn) as c:
                await c.execute("SET max_parallel_maintenance_workers = 0;")
                await c.execute("REINDEX INDEX idx_chunks_embedding;")
                await c.execute("REINDEX INDEX idx_chunks_tsv;")
                await c.execute("VACUUM ANALYZE chunks;")
        except (asyncpg.PostgresError, OSError, RuntimeError) as exc:
            raise self._translate_error("reindex_and_vacuum", exc) from exc

    def _row_to_entity(self, r: asyncpg.Record) -> ChunkEntity:
        return ChunkEntity(
            id=uuid.UUID(str(r["id"])),
            document_id=uuid.UUID(str(r["document_id"])),
            path=str(r["path"]),
            verbatim_text=str(r["verbatim_text"]),
            contextualized_text=str(r["contextualized_text"]),
            start_line=int(r["start_line"]),
            end_line=int(r["end_line"]),
            context_type="SELF_CONTAINED" if r["context_type"] == "SELF_CONTAINED" else "REQUIRES_EXTERNAL_CONTEXT",
            is_all_refs_resolved=bool(r["is_all_refs_resolved"]),
            embedding=list(r["embedding"]) if r["embedding"] is not None else None,
            metadata=self._parse_metadata(r["metadata"]),
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )

