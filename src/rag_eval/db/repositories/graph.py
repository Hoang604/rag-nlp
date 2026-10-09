from __future__ import annotations

import logging
import uuid

import asyncpg

from rag_eval.db.repositories.base import BaseRepository
from rag_eval.schemas import (
    GraphEdgeEntity,
    GraphTraversalStepDTO,
    RelationTypeCatalogDTO,
)

logger = logging.getLogger(__name__)

GraphEdgeInsertTuple = tuple[uuid.UUID, uuid.UUID, uuid.UUID, str]


class GraphRepository(BaseRepository):
    """Repository managing domain persistence, relation types catalog, and graph traversal."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        super().__init__(pool)
        self._cached_valid_relations: set[str] | None = None

    async def get_relation_catalog(
        self, conn: asyncpg.Connection | None = None
    ) -> list[RelationTypeCatalogDTO]:
        """Tải toàn bộ danh mục quan hệ hợp lệ từ bảng relation_types trong DB."""
        query = "SELECT code, description, is_symmetric FROM relation_types ORDER BY code ASC;"
        try:
            async with self._connection_scope(conn) as c:
                rows = await c.fetch(query)
                catalog = [
                    RelationTypeCatalogDTO(
                        code=str(r["code"]),
                        description=str(r["description"]),
                        is_symmetric=bool(r["is_symmetric"]),
                    )
                    for r in rows
                ]
                self._cached_valid_relations = {item.code for item in catalog}
                return catalog
        except (asyncpg.PostgresError, OSError, RuntimeError) as exc:
            raise self._translate_error("get_relation_catalog", exc) from exc

    async def get_valid_relation_codes(
        self, conn: asyncpg.Connection | None = None
    ) -> set[str]:
        """Returns the set of active relation codes, fetching from DB if not yet cached."""
        if self._cached_valid_relations is not None:
            return self._cached_valid_relations
        catalog = await self.get_relation_catalog(conn)
        return {item.code for item in catalog}

    async def upsert_edges(
        self,
        edges: list[GraphEdgeEntity],
        conn: asyncpg.Connection | None = None,
    ) -> dict[tuple[uuid.UUID, uuid.UUID, str], uuid.UUID]:
        """Upserts graph edges, returning a mapping of (source, target, relation) to authoritative database edge UUID."""
        if not edges:
            return {}

        valid_codes = await self.get_valid_relation_codes(conn)
        for e in edges:
            if e.relation_type not in valid_codes:
                raise ValueError(
                    f"Invalid relation_type '{e.relation_type}'. Must be one of active database catalog: {sorted(valid_codes)}"
                )

        query = """
        INSERT INTO graph_edges (
            id, source_chunk_id, target_chunk_id, relation_type, rationale
        )
        SELECT r.id, r.source_chunk_id, r.target_chunk_id, r.relation_type, r.rationale
        FROM unnest($1::uuid[], $2::uuid[], $3::uuid[], $4::varchar(32)[], $5::text[]) 
            AS r(id, source_chunk_id, target_chunk_id, relation_type, rationale)
        ON CONFLICT (source_chunk_id, target_chunk_id, relation_type) 
        DO UPDATE SET 
            relation_type = EXCLUDED.relation_type,
            rationale = COALESCE(EXCLUDED.rationale, graph_edges.rationale)
        RETURNING id, source_chunk_id, target_chunk_id, relation_type;
        """
        deduped: dict[tuple[uuid.UUID, uuid.UUID, str], GraphEdgeEntity] = {}
        for e in edges:
            key = (e.source_chunk_id, e.target_chunk_id, e.relation_type)
            if key not in deduped or e.rationale is not None:
                deduped[key] = e

        unique_edges = list(deduped.values())
        edge_ids = [e.id for e in unique_edges]
        source_ids = [e.source_chunk_id for e in unique_edges]
        target_ids = [e.target_chunk_id for e in unique_edges]
        relations: list[str] = [e.relation_type for e in unique_edges]
        rationales: list[str | None] = [e.rationale for e in unique_edges]

        try:
            async with self._connection_scope(conn) as c:
                rows = await c.fetch(query, edge_ids, source_ids, target_ids, relations, rationales)
                return {
                    (
                        uuid.UUID(str(r["source_chunk_id"])),
                        uuid.UUID(str(r["target_chunk_id"])),
                        str(r["relation_type"]),
                    ): uuid.UUID(str(r["id"]))
                    for r in rows
                }
        except (asyncpg.PostgresError, OSError, RuntimeError) as exc:
            raise self._translate_error("upsert_edges", exc) from exc


    async def delete_directed_edge(
        self,
        source_chunk_id: uuid.UUID,
        target_chunk_id: uuid.UUID,
        relation_type: str | None = None,
        conn: asyncpg.Connection | None = None,
    ) -> int:
        """Deletes targeted directed relationship edge(s) between two chunks, optionally filtered by relation_type."""
        if relation_type is not None:
            query = """
            DELETE FROM graph_edges
            WHERE source_chunk_id = $1 AND target_chunk_id = $2 AND relation_type = $3;
            """
            params = [source_chunk_id, target_chunk_id, relation_type]
        else:
            query = """
            DELETE FROM graph_edges
            WHERE source_chunk_id = $1 AND target_chunk_id = $2;
            """
            params = [source_chunk_id, target_chunk_id]

        try:
            async with self._connection_scope(conn) as c:
                status = await c.execute(query, *params)
                return int(status.rsplit(" ", 1)[-1] or 0)
        except (asyncpg.PostgresError, OSError, RuntimeError) as exc:
            raise self._translate_error("delete_directed_edge", exc) from exc

    async def list_edges_for_chunks(
        self, chunk_ids: list[uuid.UUID], conn: asyncpg.Connection | None = None
    ) -> list[GraphEdgeEntity]:
        """Lists edges originating from any of the provided chunk IDs."""
        if not chunk_ids:
            return []
        query = """
        SELECT id, source_chunk_id, target_chunk_id, relation_type, created_at, rationale
        FROM graph_edges
        WHERE source_chunk_id = ANY($1::uuid[]);
        """
        try:
            async with self._connection_scope(conn) as c:
                rows = await c.fetch(query, chunk_ids)
                return [
                    GraphEdgeEntity(
                        id=uuid.UUID(str(r["id"])),
                        source_chunk_id=uuid.UUID(str(r["source_chunk_id"])),
                        target_chunk_id=uuid.UUID(str(r["target_chunk_id"])),
                        relation_type=str(r["relation_type"]),
                        created_at=r["created_at"],
                        rationale=str(r["rationale"]) if r["rationale"] is not None else None,
                    )
                    for r in rows
                ]
        except (asyncpg.PostgresError, OSError, RuntimeError) as exc:
            raise self._translate_error("list_edges_for_chunks", exc) from exc

    async def traverse(
        self,
        source_chunk_id: uuid.UUID,
        nav_direction: str = "OUTGOING",
        depth_limit: int = 2,
        filter_relations: list[str] | None = None,
        match_limit: int = 20,
        conn: asyncpg.Connection | None = None,
    ) -> list[GraphTraversalStepDTO]:
        """Traverses knowledge graph bidirectionally for symmetric edges via traverse_knowledge_graph."""
        sql = """
        SELECT id, source_chunk_id, target_chunk_id, relation_type, depth, source_path, target_path, target_text,
               target_contextualized_text, target_doc_slug, target_start_line, target_end_line, rationale
        FROM traverse_knowledge_graph($1::uuid, $2::text, $3::int, $4::varchar(32)[], $5::int);
        """
        try:
            async with self._connection_scope(conn) as c:
                rows = await c.fetch(
                    sql,
                    source_chunk_id,
                    nav_direction,
                    depth_limit,
                    filter_relations or None,
                    match_limit,
                )
                return [
                    GraphTraversalStepDTO(
                        edge_id=uuid.UUID(str(r["id"])),
                        source_chunk_id=uuid.UUID(str(r["source_chunk_id"])),
                        target_chunk_id=uuid.UUID(str(r["target_chunk_id"])),
                        relation_type=str(r["relation_type"]),
                        depth=int(r["depth"]),
                        source_path=str(r["source_path"]),
                        target_path=str(r["target_path"]),
                        target_text=str(r["target_text"]),
                        target_contextualized_text=str(r["target_contextualized_text"]),
                        target_doc_slug=str(r["target_doc_slug"]),
                        target_start_line=int(r["target_start_line"]),
                        target_end_line=int(r["target_end_line"]),
                        rationale=str(r["rationale"]) if r["rationale"] is not None else None,
                    )
                    for r in rows
                ]
        except (asyncpg.PostgresError, OSError, RuntimeError) as exc:
            raise self._translate_error("traverse_knowledge_graph", exc) from exc

