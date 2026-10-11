from __future__ import annotations

import logging

import asyncpg

from rag_eval.db.connection import get_db_pool
from rag_eval.retrieval.enrichment import (
    KnowledgeEnrichmentService,
)
from rag_eval.schemas import (
    CurateEdgesResult,
    EdgeKey,
    EdgeProposal,
)

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

    async def graph_curate_edges(
        self,
        add_edges: list[EdgeProposal] | None = None,
        remove_edges: list[EdgeKey] | None = None,
        reason: str = "",
    ) -> CurateEdgesResult:
        """Executes atomic batch edge addition and removal with audit logging."""
        service = await self._get_service()
        return await service.curate_edges(
            add_edges=add_edges,
            remove_edges=remove_edges,
            reason=reason,
            actor="AGENT",
        )
