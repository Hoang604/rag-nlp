from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Final, Literal

import asyncpg
from pydantic import BaseModel, ConfigDict, Field, computed_field

from rag_eval.db.connection import get_db_pool
from rag_eval.db.repositories import CorpusRepository
from rag_eval.exceptions import (
    E_AST_GROUNDING_VALIDATION,
    E_INVALID_DOCUMENT_HIERARCHY,
    CorpusDomainError,
)
from rag_eval.ingestion.staging.manager import StagingManager
from rag_eval.mcp.tools.embedder import QueryEmbedder
from rag_eval.retrieval.reranker import CorpusReranker
from rag_eval.schemas import (
    GraphTraversalStepDTO,
    HierarchicalDirection,
    HierarchyNodeDTO,
    HybridSearchQuery,
    SearchHitDTO,
    UnresolvedRefBacklogDTO,
    VerbatimGrepQuery,
    validate_ltree_path,
)

logger = logging.getLogger("rag_eval.mcp.tools.sensors")

GraphDirection = Literal["OUTGOING", "INCOMING", "BOTH"]

HIERARCHICAL_DIRECTION_DOCS: Final[dict[HierarchicalDirection, str]] = {
    HierarchicalDirection.CHILDREN: "Lấy các nút con trực tiếp (cấp nlevel + 1).",
    HierarchicalDirection.PARENT_CHAIN: "Lấy chuỗi tổ tiên từ tài liệu gốc xuống đến nút cha trực tiếp.",
    HierarchicalDirection.SIBLINGS: "Lấy các nút anh em cùng cấp dưới cùng một nút cha.",
}

HIERARCHICAL_DIRECTION_DESCRIPTION: Final = (
    "Hướng duyệt trên cây phân cấp: "
    + "; ".join(f"'{k.value}': {v}" for k, v in HIERARCHICAL_DIRECTION_DOCS.items())
)

LOW_SIMILARITY: Final[float] = 0.86
LOW_RERANK: Final[float] = -1.0
RERANK_POOL: Final[int] = 10


class HybridSearchResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    total_hits: int
    hits: list[SearchHitDTO]
    dense_is_informative: bool = True
    expanded_query: str = ""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def confidence(self) -> str:
        """Reports how much the caller should trust these hits."""
        if not self.hits:
            return "none"
        max_dense = max(h.dense_similarity for h in self.hits)
        has_sparse = any((h.sparse_rank is not None and h.sparse_rank < 999) for h in self.hits)
        scores = [h.rerank_score for h in self.hits if h.rerank_score is not None]

        if scores and max(scores) < LOW_RERANK:
            return "low"

        if max_dense >= 0.82:
            return "high"
        if max_dense >= 0.70:
            return "medium" if not has_sparse else "high"
        if not has_sparse and max_dense < LOW_SIMILARITY:
            return "none"
        return "medium" if has_sparse else "low"


class VerbatimGrepResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    pattern: str
    is_regex: bool
    total_matches: int
    returned: int
    truncated: bool
    matches: list[SearchHitDTO]


class HierarchicalNavigateResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    anchor_path: str = Field(..., description="Đường dẫn ltree của nút gốc làm mốc duyệt")
    direction: str = Field(..., description="Hướng duyệt đã thực hiện")
    total_nodes: int = Field(..., description="Tổng số nút trả về")
    nodes: list[HierarchyNodeDTO] = Field(
        default_factory=list,
        description="Danh sách phẳng các nút được sắp xếp theo đúng thứ tự đọc của tài liệu",
    )


class GraphTraverseResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    source_path: str
    total_paths: int
    paths: list[GraphTraversalStepDTO]


class ChunkBacklogResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    total_unfinalized: int
    returned: int
    items: list[UnresolvedRefBacklogDTO]


class CorpusRuntimeSensors:
    """Production database sensors communicating exclusively through CorpusRepository."""

    def __init__(
        self,
        pool: asyncpg.Pool | None = None,
        embedding_engine: QueryEmbedder | None = None,
        reranker: CorpusReranker | None = None,
        staging_manager: StagingManager | None = None,
        rerank_by_default: bool = False,
    ) -> None:
        self._pool = pool
        self._embedder = embedding_engine
        self._reranker = reranker
        self._rerank_by_default = rerank_by_default

    async def build_dynamic_corpus_manifest(self) -> str:
        """Constructs a markdown table of active documents in the corpus."""
        try:
            repo = await self._get_repo()
            docs = await repo.documents.list_active()
            if not docs:
                return "## DANH MỤC TÀI LIỆU HIỆN CÓ: (Trống)"
            lines = [
                "## DANH MỤC TÀI LIỆU TRONG HỆ THỐNG",
                "| Mã hiệu (doc_slug) | Tiêu đề tài liệu |",
                "| :--- | :--- |",
            ]
            for doc in docs:
                lines.append(f"| `{doc.doc_slug}` | {doc.title} |")
            return "\n".join(lines)
        except (asyncpg.PostgresError, OSError, RuntimeError, CorpusDomainError) as exc:
            logger.warning("Không thể lấy danh mục tài liệu động: %s", exc)
            return ""

    async def _get_repo(self) -> CorpusRepository:
        current_loop = asyncio.get_running_loop()
        pool_loop = getattr(self._pool, "_loop", None) if self._pool is not None else None
        if (
            self._pool is None
            or self._pool._closed
            or pool_loop is not current_loop
            or (isinstance(pool_loop, asyncio.AbstractEventLoop) and pool_loop.is_closed())
        ):
            self._pool = await get_db_pool()
        return CorpusRepository(self._pool)

    async def _embed_query(self, query: str) -> list[float] | None:
        if self._embedder is None:
            return None
        return await self._embedder.embed_query(query)

    async def hybrid_search(
        self,
        query: str,
        limit: int = 10,
        doc_slugs: list[str] | None = None,
        path_prefix: str | None = None,
        only_resolved: bool | None = None,
        rerank: bool | None = None,
        rerank_pool: int = RERANK_POOL,
    ) -> HybridSearchResult:
        """Executes generalized dense+sparse hybrid retrieval via ChunkRepository."""
        repo = await self._get_repo()
        vector_param = await self._embed_query(query)

        want_rerank = self._rerank_by_default if rerank is None else rerank
        want_rerank = want_rerank and self._reranker is not None
        fetch_limit = max(limit, rerank_pool) if want_rerank else limit

        query_dto = HybridSearchQuery(
            query_text=query,
            query_vector=vector_param,
            match_limit=fetch_limit,
            rrf_k=60,
            target_documents=doc_slugs or None,
            path_prefix=path_prefix,
            only_resolved=bool(only_resolved),
            ts_config="simple",
        )

        try:
            hits = await repo.chunks.hybrid_search(query_dto)

            if want_rerank and self._reranker is not None and len(hits) > 1:
                hits = await self._reranker.rerank(query, hits, top_k=limit)
            else:
                hits = hits[:limit]

            return HybridSearchResult(
                total_hits=len(hits),
                hits=hits,
                dense_is_informative=True,
                expanded_query=query,
            )
        except (OSError, RuntimeError, CorpusDomainError, TypeError, ValueError) as exc:
            logger.error("hybrid_search failed: %s", exc)
            raise CorpusDomainError(
                error_code=E_AST_GROUNDING_VALIDATION,
                message=f"Hybrid search execution error: {exc}",
            ) from exc

    async def verbatim_grep(
        self,
        pattern: str,
        is_regex: bool = False,
        case_sensitive: bool = False,
        limit: int = 20,
        path_prefix: str | None = None,
        only_resolved: bool | None = None,
        target_documents: list[str] | None = None,
    ) -> VerbatimGrepResult:
        """Executes exact / trigram grep search via ChunkRepository."""
        repo = await self._get_repo()

        query_dto = VerbatimGrepQuery(
            query_pattern=pattern,
            target_documents=target_documents or None,
            path_prefix=path_prefix,
            only_resolved=bool(only_resolved),
            is_regex=is_regex,
            case_sensitive=case_sensitive,
            match_limit=limit,
        )

        try:
            hits, total = await repo.chunks.verbatim_grep(query_dto)

            return VerbatimGrepResult(
                pattern=pattern,
                is_regex=is_regex,
                total_matches=total,
                returned=len(hits),
                truncated=(total > len(hits)),
                matches=hits,
            )
        except (OSError, RuntimeError, CorpusDomainError, TypeError, ValueError) as exc:
            logger.error("verbatim_grep failed: %s", exc)
            raise CorpusDomainError(
                error_code=E_AST_GROUNDING_VALIDATION,
                message=f"Verbatim grep execution error: {exc}",
            ) from exc

    async def hierarchical_navigate(
        self,
        path: str | None = None,
        chunk_id: str | None = None,
        direction: HierarchicalDirection = HierarchicalDirection.CHILDREN,
    ) -> HierarchicalNavigateResult:
        """Navigates hierarchical document tree via ChunkRepository."""
        repo = await self._get_repo()

        origin_chunk = None
        if chunk_id:
            try:
                origin_chunk = await repo.chunks.get_by_id(uuid.UUID(chunk_id))
            except ValueError as err:
                raise CorpusDomainError(
                    error_code=E_INVALID_DOCUMENT_HIERARCHY,
                    message=f"Định danh chunk_id '{chunk_id}' không phải là UUID hợp lệ.",
                ) from err
        elif path:
            clean_path = validate_ltree_path(path)
            origin_chunk = await repo.chunks.get_by_path(clean_path)
        else:
            raise CorpusDomainError(
                error_code=E_INVALID_DOCUMENT_HIERARCHY,
                message="Bắt buộc phải cung cấp 'path' (chuỗi ltree) hoặc 'chunk_id' (UUID) để duyệt cây phân cấp.",
            )

        if not origin_chunk:
            raise CorpusDomainError(
                error_code=E_INVALID_DOCUMENT_HIERARCHY,
                message=f"Không tìm thấy chunk tương ứng với chunk_id='{chunk_id}', path='{path}'.",
            )

        dir_val = direction.value
        nodes_dto = await repo.chunks.navigate_hierarchy(
            origin_chunk.document_id, origin_chunk.path, dir_val
        )

        return HierarchicalNavigateResult(
            anchor_path=origin_chunk.path,
            direction=dir_val,
            total_nodes=len(nodes_dto),
            nodes=nodes_dto,
        )

    async def graph_traverse(
        self,
        source_path: str,
        direction: GraphDirection = "OUTGOING",
        max_depth: int = 2,
        filter_relations: list[str] | None = None,
    ) -> GraphTraverseResult:
        """Traverses knowledge graph bidirectionally for symmetric edges via GraphRepository."""
        repo = await self._get_repo()
        clean_path = validate_ltree_path(source_path)
        chunk = await repo.chunks.get_by_path(clean_path)
        if not chunk:
            raise CorpusDomainError(
                error_code=E_INVALID_DOCUMENT_HIERARCHY,
                message=f"Không tìm thấy chunk tương ứng với source_path='{source_path}'.",
            )

        steps_dto = await repo.graph.traverse(
            chunk.id,
            nav_direction=direction,
            depth_limit=max_depth,
            filter_relations=filter_relations,
        )

        return GraphTraverseResult(
            source_path=source_path,
            total_paths=len(steps_dto),
            paths=list(steps_dto),
        )

    async def corpus_backlog_poll(
        self,
        doc_slug: str | None = None,
        limit: int = 50,
    ) -> ChunkBacklogResult:
        """Polls unresolved context dependencies via ChunkContextRefRepository."""
        repo = await self._get_repo()
        rows = await repo.context_refs.get_unresolved_backlog(doc_slug=doc_slug, limit=limit)

        return ChunkBacklogResult(
            total_unfinalized=len(rows),
            returned=len(rows),
            items=list(rows),
        )
