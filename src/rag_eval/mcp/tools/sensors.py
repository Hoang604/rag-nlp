from __future__ import annotations

import asyncio
import logging
from typing import Final, Literal

import asyncpg
from pydantic import BaseModel, ConfigDict, Field

from rag_eval.db.connection import get_db_pool
from rag_eval.db.repositories import CorpusRepository
from rag_eval.exceptions import (
    E_AST_GROUNDING_VALIDATION,
    E_INVALID_DOCUMENT_HIERARCHY,
    CorpusDomainError,
)
from rag_eval.retrieval.embedder import QueryEmbedder
from rag_eval.retrieval.engine import RetrievalEngine
from rag_eval.retrieval.reranker import CorpusReranker
from rag_eval.schemas import (
    AgentVennHit,
    HierarchicalDirection,
    VennSearchResult,
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

RERANK_POOL: Final[int] = 10


# ---------------------------------------------------------------------------
# Canonical Agent-First Models & Result Containers
# ---------------------------------------------------------------------------



class AgentHierarchyNode(BaseModel):
    model_config = ConfigDict(extra="ignore")

    path: str
    doc_slug: str
    start_line: int = Field(..., ge=1, description="Số dòng bắt đầu trong tài liệu")
    end_line: int = Field(..., ge=1, description="Số dòng kết thúc trong tài liệu")
    verbatim_text: str
    contextualized_text: str
    metadata: dict[str, object] = Field(default_factory=dict)
    relative_depth: int = 0


class HierarchicalNavigateResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    anchor_path: str = Field(..., description="Đường dẫn phân cấp của nút gốc làm mốc duyệt")
    direction: str = Field(..., description="Hướng duyệt đã thực hiện")
    total_nodes: int = Field(..., description="Tổng số nút trả về")
    nodes: list[AgentHierarchyNode] = Field(
        default_factory=list,
        description="Danh sách phẳng các nút được sắp xếp theo đúng thứ tự đọc của tài liệu",
    )


class AgentGraphTraversalStep(BaseModel):
    model_config = ConfigDict(extra="ignore")

    source_path: str = Field(..., min_length=1, description="Đường dẫn LTree của chunk nguồn")
    target_path: str = Field(..., min_length=1, description="Đường dẫn LTree của chunk đích")
    relation_type: str = Field(..., description="Loại quan hệ giữa 2 chunk")
    depth: int = Field(..., ge=1, description="Độ sâu bước nhảy trên đồ thị")
    target_text: str = Field(..., description="Nội dung văn bản gốc của chunk đích")
    target_contextualized_text: str = Field(..., min_length=1, description="Đoạn văn đầy đủ ngữ cảnh để trích dẫn trực tiếp")
    target_doc_slug: str = Field(..., min_length=1, description="Mã định danh tài liệu chứa chunk đích")
    target_start_line: int = Field(..., ge=1, description="Số dòng bắt đầu trong tài liệu gốc")
    target_end_line: int = Field(..., ge=1, description="Số dòng kết thúc trong tài liệu gốc")
    rationale: str | None = Field(default=None, description="Luận cứ ngữ nghĩa kết nối hai nút")


class GraphTraverseResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    source_path: str
    total_paths: int
    paths: list[AgentGraphTraversalStep]


# ---------------------------------------------------------------------------
# Corpus Runtime Sensors Implementation
# ---------------------------------------------------------------------------


class CorpusRuntimeSensors:
    """Production database sensors communicating exclusively through CorpusRepository."""

    def __init__(
        self,
        pool: asyncpg.Pool | None = None,
        embedding_engine: QueryEmbedder | None = None,
        reranker: CorpusReranker | None = None,
        rerank_by_default: bool = False,
    ) -> None:
        self._pool = pool
        self._embedder = embedding_engine
        self._reranker = reranker
        self._rerank_by_default = rerank_by_default
        self._engine: RetrievalEngine | None = None

    async def _get_engine(self) -> RetrievalEngine:
        repo = await self._get_repo()
        if self._engine is None or self._engine._pool is not repo.pool:
            self._engine = RetrievalEngine(
                pool=repo.pool,
                embedder=self._embedder,
                reranker=self._reranker,
                rerank_by_default=self._rerank_by_default,
            )
        return self._engine

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
        """Executes generalized dual-channel Venn retrieval via RetrievalEngine."""
        try:
            engine = await self._get_engine()
            return await engine.search_venn(
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
        except (OSError, RuntimeError, CorpusDomainError, TypeError, ValueError) as exc:
            logger.error("hybrid_search failed: %s", exc)
            raise CorpusDomainError(
                error_code=E_AST_GROUNDING_VALIDATION,
                message=f"Hybrid search execution error: {exc}",
            ) from exc

    async def hierarchical_navigate(
        self,
        path: str,
        direction: HierarchicalDirection = HierarchicalDirection.CHILDREN,
    ) -> HierarchicalNavigateResult:
        """Navigates hierarchical document tree via ChunkRepository."""
        repo = await self._get_repo()
        clean_path = validate_ltree_path(path)
        origin_chunk = await repo.chunks.get_by_path(clean_path)
        if not origin_chunk:
            raise CorpusDomainError(
                error_code=E_INVALID_DOCUMENT_HIERARCHY,
                message=f"Không tìm thấy chunk tương ứng với path='{clean_path}'.",
            )

        dir_val = direction.value
        nodes_dto = await repo.chunks.navigate_hierarchy(
            origin_chunk.document_id, origin_chunk.path, dir_val
        )

        agent_nodes = [
            AgentHierarchyNode(
                path=n.path,
                doc_slug=n.doc_slug,
                start_line=n.start_line,
                end_line=n.end_line,
                verbatim_text=n.verbatim_text,
                contextualized_text=n.contextualized_text,
                metadata=dict(n.metadata),
                relative_depth=n.relative_depth,
            )
            for n in nodes_dto
        ]

        return HierarchicalNavigateResult(
            anchor_path=origin_chunk.path,
            direction=dir_val,
            total_nodes=len(agent_nodes),
            nodes=agent_nodes,
        )

    async def graph_traverse(
        self,
        source_path: str,
        direction: GraphDirection = "OUTGOING",
        max_depth: int = 2,
        filter_relations: list[str] | None = None,
        limit: int = 20,
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
            match_limit=limit,
        )

        agent_steps: list[AgentGraphTraversalStep] = [
            AgentGraphTraversalStep(
                source_path=s.source_path,
                target_path=s.target_path,
                relation_type=s.relation_type,
                depth=s.depth,
                target_text=s.target_text,
                target_contextualized_text=s.target_contextualized_text,
                target_doc_slug=s.target_doc_slug,
                target_start_line=s.target_start_line,
                target_end_line=s.target_end_line,
                rationale=s.rationale,
            )
            for s in steps_dto
        ]

        return GraphTraverseResult(
            source_path=clean_path,
            total_paths=len(agent_steps),
            paths=agent_steps,
        )


__all__ = [
    "HIERARCHICAL_DIRECTION_DESCRIPTION",
    "HIERARCHICAL_DIRECTION_DOCS",
    "RERANK_POOL",
    "AgentGraphTraversalStep",
    "AgentHierarchyNode",
    "AgentVennHit",
    "CorpusRuntimeSensors",
    "GraphDirection",
    "GraphTraverseResult",
    "HierarchicalDirection",
    "HierarchicalNavigateResult",
    "VennSearchResult",
]
