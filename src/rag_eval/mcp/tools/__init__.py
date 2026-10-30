from __future__ import annotations

from rag_eval.mcp.tools.answer import (
    AnswerValidationViolation,
    AnswerValidator,
    CitationInput,
    CorpusAnswerTools,
    DefaultPathAnswerValidator,
    GroundedCitationDTO,
    SubmitGroundedAnswerResult,
    ValidatedAnswerPayload,
)
from rag_eval.mcp.tools.enrichment import CorpusEnrichmentTools
from rag_eval.mcp.tools.sensors import (
    MAX_RAW_LINES,
    RERANK_POOL,
    CorpusRuntimeSensors,
)
from rag_eval.retrieval.embedder import (
    QueryEmbedder,
    SentenceTransformerQueryEmbedder,
)
from rag_eval.retrieval.reranker import CorpusReranker
from rag_eval.schemas import (
    CurateEdgesResult,
    EdgeKey,
    EdgeProposal,
    GraphDirection,
    HierarchicalDirection,
    RawDocumentSliceResult,
    RelationType,
    UnifiedGraphTraverseResult,
    UnifiedHierarchyResult,
    UnifiedSearchResult,
    format_graph_direction_docs,
    format_hierarchical_direction_docs,
    format_hierarchical_direction_values,
    format_relation_type_docs,
)


class CorpusMCPTools:
    """Canonical tool facade composing runtime sensors, knowledge enrichment, and grounded answer submission via strict DI."""

    def __init__(
        self,
        sensors: CorpusRuntimeSensors,
        enrichment: CorpusEnrichmentTools,
        answer_tools: CorpusAnswerTools | None = None,
    ) -> None:
        self._sensors = sensors
        self._enrichment = enrichment
        self._answer_tools = answer_tools if answer_tools is not None else CorpusAnswerTools()

    @property
    def sensors(self) -> CorpusRuntimeSensors:
        return self._sensors

    @property
    def enrichment(self) -> CorpusEnrichmentTools:
        return self._enrichment

    @property
    def answer_tools(self) -> CorpusAnswerTools:
        return self._answer_tools

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
        order_by_reading_order: bool = False,
    ) -> UnifiedSearchResult:
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
            order_by_reading_order=order_by_reading_order,
        )

    async def hierarchical_navigate(
        self,
        path: str,
        direction: HierarchicalDirection = HierarchicalDirection.CHILDREN,
        limit: int = 15,
    ) -> UnifiedHierarchyResult:
        return await self._sensors.hierarchical_navigate(
            path=path,
            direction=direction,
            limit=limit,
        )

    async def graph_traverse(
        self,
        source_path: str,
        direction: GraphDirection = GraphDirection.OUTGOING,
        max_depth: int = 2,
        filter_relations: list[RelationType] | None = None,
        limit_per_link: int = 20,
    ) -> UnifiedGraphTraverseResult:
        return await self._sensors.graph_traverse(
            source_path=source_path,
            direction=direction,
            max_depth=max_depth,
            filter_relations=filter_relations,
            limit_per_link=limit_per_link,
        )

    async def graph_curate_edges(
        self,
        add_edges: list[EdgeProposal] | None = None,
        remove_edges: list[EdgeKey] | None = None,
        reason: str = "",
    ) -> CurateEdgesResult:
        return await self._enrichment.graph_curate_edges(
            add_edges=add_edges,
            remove_edges=remove_edges,
            reason=reason,
        )

    async def get_raw(
        self,
        path_or_slug: str,
        start_line: int = 1,
        end_line: int | None = None,
    ) -> RawDocumentSliceResult:
        return await self._sensors.get_raw(
            path_or_slug=path_or_slug,
            start_line=start_line,
            end_line=end_line,
        )

    async def submit_grounded_answer(
        self,
        answer: str,
        citations: list[CitationInput | str] | None = None,
        abstained: bool = False,
    ) -> SubmitGroundedAnswerResult:
        return await self._answer_tools.submit_grounded_answer(
            answer=answer,
            citations=citations,
            abstained=abstained,
        )


__all__ = [
    "MAX_RAW_LINES",
    "RERANK_POOL",
    "AnswerValidationViolation",
    "AnswerValidator",
    "CitationInput",
    "CorpusAnswerTools",
    "CorpusEnrichmentTools",
    "CorpusMCPTools",
    "CorpusReranker",
    "CorpusRuntimeSensors",
    "CurateEdgesResult",
    "DefaultPathAnswerValidator",
    "EdgeKey",
    "EdgeProposal",
    "GraphDirection",
    "GroundedCitationDTO",
    "HierarchicalDirection",
    "QueryEmbedder",
    "RawDocumentSliceResult",
    "RelationType",
    "SentenceTransformerQueryEmbedder",
    "SubmitGroundedAnswerResult",
    "UnifiedGraphTraverseResult",
    "UnifiedHierarchyResult",
    "UnifiedSearchResult",
    "ValidatedAnswerPayload",
    "format_graph_direction_docs",
    "format_hierarchical_direction_docs",
    "format_hierarchical_direction_values",
    "format_relation_type_docs",
]
