from __future__ import annotations

from collections.abc import Sequence

import asyncpg

from rag_eval.ingestion.staging import (
    StagingChunk,
    StagingChunkDelta,
    StagingEdge,
    StagingEdgeFilter,
    StagingEdgeInput,
    StgReparentResult,
)
from rag_eval.ingestion.staging.manager import StagingManager
from rag_eval.ingestion.staging.models import (
    ChunkFinalizeStatus,
    ChunkProgressStats,
    RelationTypeFilter,
    StagingStatusFilter,
    StgAddEdgesResult,
    StgCommitResult,
    StgFinalizeResult,
    StgGetChunkResult,
    StgGetRawResult,
    StgGrepResult,
    StgGrepScope,
    StgListSessionsResult,
    StgPatchResult,
    StgPollPendingResult,
    StgPreviewHit,
    StgPreviewResult,
    StgRemoveEdgeResult,
    StgReopenResult,
)
from rag_eval.mcp.tools.embedder import (
    QueryEmbedder,
    SentenceTransformerQueryEmbedder,
)
from rag_eval.mcp.tools.sensors import (
    HIERARCHICAL_DIRECTION_DESCRIPTION,
    HIERARCHICAL_DIRECTION_DOCS,
    RERANK_POOL,
    ChunkBacklogResult,
    CorpusRuntimeSensors,
    GraphDirection,
    GraphTraverseResult,
    HierarchicalNavigateResult,
    HybridSearchResult,
    VerbatimGrepResult,
)
from rag_eval.mcp.tools.staging import CorpusStagingTools
from rag_eval.retrieval.reranker import CorpusReranker
from rag_eval.schemas import (
    GraphTraversalStepDTO,
    HierarchicalDirection,
    HierarchyNodeDTO,
    SearchHitDTO,
)


class CorpusMCPTools:
    """Canonical 18-tool facade composing runtime sensors and staging operations via strict DI."""

    def __init__(
        self,
        sensors: CorpusRuntimeSensors,
        staging: CorpusStagingTools,
    ) -> None:
        self._sensors = sensors
        self._staging = staging

    @classmethod
    def build(
        cls,
        pool: asyncpg.Pool | None = None,
        staging_manager: StagingManager | None = None,
        embedding_engine: QueryEmbedder | None = None,
        reranker: CorpusReranker | None = None,
        rerank_by_default: bool = False,
    ) -> CorpusMCPTools:
        manager = staging_manager or StagingManager()
        return cls(
            sensors=CorpusRuntimeSensors(
                pool=pool,
                embedding_engine=embedding_engine,
                staging_manager=manager,
                reranker=reranker,
                rerank_by_default=rerank_by_default,
            ),
            staging=CorpusStagingTools(staging_manager=manager, pool=pool),
        )

    @property
    def sensors(self) -> CorpusRuntimeSensors:
        return self._sensors

    @property
    def staging(self) -> CorpusStagingTools:
        return self._staging

    async def build_dynamic_corpus_manifest(self) -> str:
        return await self._sensors.build_dynamic_corpus_manifest()

    async def hybrid_search(
        self,
        query: str,
        limit: int = 10,
        rerank: bool | None = None,
        rerank_pool: int = RERANK_POOL,
        doc_slugs: list[str] | None = None,
        path_prefix: str | None = None,
        only_resolved: bool | None = None,
    ) -> HybridSearchResult:
        return await self._sensors.hybrid_search(
            query=query,
            limit=limit,
            rerank=rerank,
            rerank_pool=rerank_pool,
            doc_slugs=doc_slugs,
            path_prefix=path_prefix,
            only_resolved=only_resolved,
        )

    async def verbatim_grep(
        self,
        pattern: str,
        is_regex: bool = False,
        case_sensitive: bool = False,
        limit: int = 20,
    ) -> VerbatimGrepResult:
        return await self._sensors.verbatim_grep(
            pattern=pattern,
            is_regex=is_regex,
            case_sensitive=case_sensitive,
            limit=limit,
        )

    async def hierarchical_navigate(
        self,
        path: str | None = None,
        chunk_id: str | None = None,
        direction: HierarchicalDirection = HierarchicalDirection.CHILDREN,
    ) -> HierarchicalNavigateResult:
        return await self._sensors.hierarchical_navigate(
            path=path, chunk_id=chunk_id, direction=direction
        )

    async def graph_traverse(
        self,
        source_path: str,
        direction: GraphDirection = "OUTGOING",
        max_depth: int = 2,
        filter_relations: list[str] | None = None,
    ) -> GraphTraverseResult:
        return await self._sensors.graph_traverse(
            source_path=source_path,
            direction=direction,
            max_depth=max_depth,
            filter_relations=filter_relations,
        )

    async def corpus_backlog_poll(
        self,
        doc_slug: str | None = None,
        limit: int = 50,
    ) -> ChunkBacklogResult:
        return await self._sensors.corpus_backlog_poll(
            doc_slug=doc_slug,
            limit=limit,
        )

    async def stg_preview(
        self,
        doc_slug: str,
        path_prefix: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> StgPreviewResult:
        return await self._staging.stg_preview(
            doc_slug=doc_slug,
            path_prefix=path_prefix,
            limit=limit,
            offset=offset,
        )

    async def stg_get_chunk(self, doc_slug: str, path: str) -> StgGetChunkResult:
        return await self._staging.stg_get_chunk(doc_slug=doc_slug, path=path)

    async def stg_get_raw(
        self, doc_slug: str, start_line: int = 1, end_line: int = 100
    ) -> StgGetRawResult:
        return await self._staging.stg_get_raw(
            doc_slug=doc_slug, start_line=start_line, end_line=end_line
        )

    async def stg_grep(
        self,
        doc_slug: str,
        pattern: str,
        is_regex: bool = False,
        case_sensitive: bool = False,
        search_in: StgGrepScope = "ALL",
        limit: int = 50,
    ) -> StgGrepResult:
        return await self._staging.stg_grep(
            doc_slug=doc_slug,
            pattern=pattern,
            is_regex=is_regex,
            case_sensitive=case_sensitive,
            search_in=search_in,
            limit=limit,
        )

    async def stg_patch(
        self,
        doc_slug: str,
        updated_chunks: Sequence[StagingChunkDelta | StagingChunk | dict[str, object]] | None = None,
        removed_paths: list[str] | None = None,
        cascade_breadcrumbs: bool = True,
    ) -> StgPatchResult:
        return await self._staging.stg_patch(
            doc_slug=doc_slug,
            updated_chunks=updated_chunks,
            removed_paths=removed_paths,
            cascade_breadcrumbs=cascade_breadcrumbs,
        )

    async def stg_add_edges(
        self,
        doc_slug: str,
        edges: Sequence[StagingEdge | StagingEdgeInput | dict[str, object]],
    ) -> StgAddEdgesResult:
        return await self._staging.stg_add_edges(
            doc_slug=doc_slug,
            edges=edges,
        )

    async def stg_reparent(
        self,
        doc_slug: str,
        old_path_prefix: str,
        new_path_prefix: str,
        dry_run: bool = False,
    ) -> StgReparentResult:
        return await self._staging.stg_reparent(
            doc_slug=doc_slug,
            old_path_prefix=old_path_prefix,
            new_path_prefix=new_path_prefix,
            dry_run=dry_run,
        )

    async def stg_poll_pending_chunks(
        self,
        doc_slug: str,
        limit: int = 10,
        path_prefix: str | None = None,
    ) -> StgPollPendingResult:
        return await self._staging.stg_poll_pending_chunks(
            doc_slug=doc_slug,
            limit=limit,
            path_prefix=path_prefix,
        )

    async def stg_finalize_chunks(
        self,
        doc_slug: str,
        paths: list[str],
    ) -> StgFinalizeResult:
        return await self._staging.stg_finalize_chunks(
            doc_slug=doc_slug,
            paths=paths,
        )

    async def stg_commit(self, doc_slug: str) -> StgCommitResult:
        return await self._staging.stg_commit(doc_slug=doc_slug)

    async def stg_list_sessions(
        self, status: StagingStatusFilter | None = None
    ) -> StgListSessionsResult:
        return await self._staging.stg_list_sessions(status=status)

    async def stg_reopen_session(
        self,
        doc_slug: str,
        reason: str = "",
    ) -> StgReopenResult:
        return await self._staging.stg_reopen_session(doc_slug=doc_slug, reason=reason)

    async def stg_remove_edge(
        self,
        doc_slug: str,
        source_path: str = "",
        target_path: str | None = None,
        relation_type: RelationTypeFilter | None = None,
        clear_all_targets: bool = False,
        edges: Sequence[StagingEdgeFilter | dict[str, object]] | None = None,
    ) -> StgRemoveEdgeResult:
        return await self._staging.stg_remove_edge(
            doc_slug=doc_slug,
            source_path=source_path,
            target_path=target_path,
            relation_type=relation_type,
            clear_all_targets=clear_all_targets,
            edges=edges,
        )

    async def stg_validate(self, doc_slug: str) -> dict[str, object]:
        return await self._staging.stg_validate(doc_slug=doc_slug)


__all__ = [
    "HIERARCHICAL_DIRECTION_DESCRIPTION",
    "HIERARCHICAL_DIRECTION_DOCS",
    "RERANK_POOL",
    "ChunkBacklogResult",
    "ChunkFinalizeStatus",
    "ChunkProgressStats",
    "CorpusMCPTools",
    "CorpusReranker",
    "CorpusRuntimeSensors",
    "CorpusStagingTools",
    "GraphDirection",
    "GraphTraversalStepDTO",
    "GraphTraverseResult",
    "HierarchicalDirection",
    "HierarchicalNavigateResult",
    "HierarchyNodeDTO",
    "HybridSearchResult",
    "QueryEmbedder",
    "RelationTypeFilter",
    "SearchHitDTO",
    "SentenceTransformerQueryEmbedder",
    "StagingChunk",
    "StagingChunkDelta",
    "StagingEdge",
    "StagingEdgeFilter",
    "StagingStatusFilter",
    "StgAddEdgesResult",
    "StgCommitResult",
    "StgFinalizeResult",
    "StgGetChunkResult",
    "StgGetRawResult",
    "StgGrepResult",
    "StgGrepScope",
    "StgListSessionsResult",
    "StgPatchResult",
    "StgPollPendingResult",
    "StgPreviewHit",
    "StgPreviewResult",
    "StgRemoveEdgeResult",
    "StgReopenResult",
    "StgReparentResult",
    "VerbatimGrepResult",
]
