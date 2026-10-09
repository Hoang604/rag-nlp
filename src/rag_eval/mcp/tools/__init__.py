from __future__ import annotations

from rag_eval.mcp.tools.enrichment import CorpusEnrichmentTools
from rag_eval.mcp.tools.sensors import (
    HIERARCHICAL_DIRECTION_DESCRIPTION,
    HIERARCHICAL_DIRECTION_DOCS,
    RERANK_POOL,
    AgentGraphTraversalStep,
    AgentHierarchyNode,
    CorpusRuntimeSensors,
    GraphDirection,
    GraphTraverseResult,
    HierarchicalNavigateResult,
)
from rag_eval.retrieval.embedder import (
    QueryEmbedder,
    SentenceTransformerQueryEmbedder,
)
from rag_eval.retrieval.reranker import CorpusReranker
from rag_eval.schemas import (
    AgentVennHit,
    HierarchicalDirection,
    RelationType,
    VennSearchResult,
)


class CorpusMCPTools:
    """Canonical 5-tool facade composing runtime sensors and knowledge enrichment via strict DI."""

    def __init__(
        self,
        sensors: CorpusRuntimeSensors,
        enrichment: CorpusEnrichmentTools,
    ) -> None:
        self._sensors = sensors
        self._enrichment = enrichment

    @property
    def sensors(self) -> CorpusRuntimeSensors:
        return self._sensors

    @property
    def enrichment(self) -> CorpusEnrichmentTools:
        return self._enrichment

    async def build_dynamic_corpus_manifest(self) -> str:
        return await self._sensors.build_dynamic_corpus_manifest()

    async def hybrid_search(
        self,
        query: str,
        pattern: str,
        limit: int = 10,
        rerank: bool | None = None,
        rerank_pool: int = RERANK_POOL,
        doc_slugs: list[str] | None = None,
        path_prefix: str | None = None,
        is_regex: bool = False,
        case_sensitive: bool = False,
    ) -> VennSearchResult:
        return await self._sensors.hybrid_search(
            query=query,
            pattern=pattern,
            limit=limit,
            rerank=rerank,
            rerank_pool=rerank_pool,
            doc_slugs=doc_slugs,
            path_prefix=path_prefix,
            is_regex=is_regex,
            case_sensitive=case_sensitive,
        )

    async def hierarchical_navigate(
        self,
        path: str,
        direction: HierarchicalDirection = HierarchicalDirection.CHILDREN,
    ) -> HierarchicalNavigateResult:
        return await self._sensors.hierarchical_navigate(
            path=path, direction=direction
        )

    async def graph_traverse(
        self,
        source_path: str,
        direction: GraphDirection = "OUTGOING",
        max_depth: int = 2,
        filter_relations: list[str] | None = None,
        limit: int = 20,
    ) -> GraphTraverseResult:
        return await self._sensors.graph_traverse(
            source_path=source_path,
            direction=direction,
            max_depth=max_depth,
            filter_relations=filter_relations,
            limit=limit,
        )

    async def link_chunks(
        self,
        source_path: str,
        target_path: str,
        relation_type: RelationType | str,
        rationale: str | None = None,
    ) -> dict[str, object]:
        return await self._enrichment.link_chunks(
            source_path=source_path,
            target_path=target_path,
            relation_type=relation_type,
            rationale=rationale,
        )

    async def unlink_chunks(
        self,
        source_path: str,
        target_path: str,
        relation_type: RelationType | str | None = None,
    ) -> dict[str, object]:
        return await self._enrichment.unlink_chunks(
            source_path=source_path,
            target_path=target_path,
            relation_type=relation_type,
        )


__all__ = [
    "HIERARCHICAL_DIRECTION_DESCRIPTION",
    "HIERARCHICAL_DIRECTION_DOCS",
    "RERANK_POOL",
    "AgentGraphTraversalStep",
    "AgentHierarchyNode",
    "AgentVennHit",
    "CorpusEnrichmentTools",
    "CorpusMCPTools",
    "CorpusReranker",
    "CorpusRuntimeSensors",
    "GraphDirection",
    "GraphTraverseResult",
    "HierarchicalDirection",
    "HierarchicalNavigateResult",
    "QueryEmbedder",
    "RelationType",
    "SentenceTransformerQueryEmbedder",
    "VennSearchResult",
]
