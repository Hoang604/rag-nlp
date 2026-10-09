from __future__ import annotations

import logging

import asyncpg

from rag_eval.db.connection import get_db_pool
from rag_eval.retrieval.enrichment import (
    KnowledgeEnrichmentService,
)
from rag_eval.schemas import RelationType

logger = logging.getLogger("rag_eval.mcp.tools.enrichment")


class CorpusEnrichmentTools:
    """Facade exposing knowledge graph enrichment tools for MCP Agents."""

    def __init__(
        self,
        service: KnowledgeEnrichmentService | None = None,
        pool: asyncpg.Pool | None = None,
    ) -> None:
        self._service = service
        self._pool = pool

    async def _get_service(self) -> KnowledgeEnrichmentService:
        if self._service is not None:
            return self._service
        if self._pool is None or self._pool._closed:
            self._pool = await get_db_pool()
        return KnowledgeEnrichmentService(self._pool)

    async def link_chunks(
        self,
        source_path: str,
        target_path: str,
        relation_type: RelationType | str,
        rationale: str | None = None,
    ) -> dict[str, object]:
        """Thiết lập cạnh quan hệ giữa 2 chunk dựa trên LTree path."""
        service = await self._get_service()
        res = await service.link_chunks(
            source_path=source_path,
            target_path=target_path,
            relation_type=relation_type,
            rationale=rationale,
        )
        return {
            "status": "SUCCESS",
            "source_path": res.source_path,
            "target_path": res.target_path,
            "relation_type": res.relation_type.value,
            "created": res.created,
            "rationale": res.rationale,
        }

    async def unlink_chunks(
        self,
        source_path: str,
        target_path: str,
        relation_type: RelationType | str | None = None,
    ) -> dict[str, object]:
        """Gỡ bỏ cạnh quan hệ giữa 2 chunk dựa trên LTree path."""
        service = await self._get_service()
        res = await service.unlink_chunks(
            source_path=source_path,
            target_path=target_path,
            relation_type=relation_type,
        )
        return {
            "status": "SUCCESS",
            "source_path": res.source_path,
            "target_path": res.target_path,
            "removed_edges_count": res.removed_edges_count,
        }
