from __future__ import annotations

import asyncio
import logging
import uuid
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
from rag_eval.retrieval.confidence import compute_search_confidence
from rag_eval.retrieval.embedder import QueryEmbedder
from rag_eval.retrieval.reranker import CorpusReranker
from rag_eval.schemas import (
    HierarchicalDirection,
    HybridSearchQuery,
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

RERANK_POOL: Final[int] = 10


# ---------------------------------------------------------------------------
# Canonical Agent-First Models & Result Containers
# ---------------------------------------------------------------------------


class AgentSearchHit(BaseModel):
    model_config = ConfigDict(extra="ignore")

    doc_slug: str
    doc_title: str
    path: str
    start_line: int
    end_line: int
    verbatim_text: str
    contextualized_text: str
    context_type: str
    is_all_refs_resolved: bool
    metadata: dict[str, object] = Field(default_factory=dict)


class HybridSearchResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    total_hits: int
    hits: list[AgentSearchHit]
    confidence: str
    expanded_query: str = ""


class VerbatimGrepResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    pattern: str
    is_regex: bool
    total_matches: int
    returned: int
    truncated: bool
    matches: list[AgentSearchHit]


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

    source_path: str
    target_path: str
    relation_type: str
    depth: int
    target_text: str = ""


class GraphTraverseResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    source_path: str
    total_paths: int
    paths: list[AgentGraphTraversalStep]


class AgentBacklogItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    doc_slug: str
    path: str
    target_path: str | None = None
    context_type: str = "REQUIRES_EXTERNAL_CONTEXT"
    is_all_refs_resolved: bool = False
    verbatim_text: str = ""
    contextualized_text: str = ""
    char_start: int | None = None
    char_end: int | None = None
    metadata: dict[str, object] = Field(default_factory=dict)


class ChunkBacklogResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    total_unfinalized: int
    returned: int
    items: list[AgentBacklogItem]


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

            confidence = compute_search_confidence(hits)
            agent_hits = [
                AgentSearchHit(
                    doc_slug=h.doc_slug,
                    doc_title=h.doc_title,
                    path=h.path,
                    start_line=h.start_line,
                    end_line=h.end_line,
                    verbatim_text=h.verbatim_text,
                    contextualized_text=h.contextualized_text,
                    context_type=str(h.context_type),
                    is_all_refs_resolved=h.is_all_refs_resolved,
                    metadata=dict(h.metadata),
                )
                for h in hits
            ]

            return HybridSearchResult(
                total_hits=len(agent_hits),
                hits=agent_hits,
                confidence=confidence,
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

            agent_hits = [
                AgentSearchHit(
                    doc_slug=h.doc_slug,
                    doc_title=h.doc_title,
                    path=h.path,
                    start_line=h.start_line,
                    end_line=h.end_line,
                    verbatim_text=h.verbatim_text,
                    contextualized_text=h.contextualized_text,
                    context_type=str(h.context_type),
                    is_all_refs_resolved=h.is_all_refs_resolved,
                    metadata=dict(h.metadata),
                )
                for h in hits
            ]

            return VerbatimGrepResult(
                pattern=pattern,
                is_regex=is_regex,
                total_matches=total,
                returned=len(agent_hits),
                truncated=(total > len(agent_hits)),
                matches=agent_hits,
            )
        except (OSError, RuntimeError, CorpusDomainError, TypeError, ValueError) as exc:
            logger.error("verbatim_grep failed: %s", exc)
            raise CorpusDomainError(
                error_code=E_AST_GROUNDING_VALIDATION,
                message=f"Verbatim grep execution error: {exc}",
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

        needed_ids = {s.source_chunk_id for s in steps_dto if s.depth > 1}
        id_to_path: dict[uuid.UUID, str] = {chunk.id: clean_path}
        if needed_ids:
            resolved = await repo.chunks.resolve_ids_batch(list(needed_ids))
            id_to_path.update(resolved)

        agent_steps: list[AgentGraphTraversalStep] = []
        for s in steps_dto:
            src_path = id_to_path.get(s.source_chunk_id)
            if src_path is None:
                raise CorpusDomainError(
                    error_code=E_INVALID_DOCUMENT_HIERARCHY,
                    message=(
                        f"Không thể phân giải đường dẫn nút nguồn (UUID: {s.source_chunk_id}) "
                        f"tại bước nhảy độ sâu {s.depth} cho đích '{s.target_path}'."
                    ),
                )
            agent_steps.append(
                AgentGraphTraversalStep(
                    source_path=src_path,
                    target_path=s.target_path,
                    relation_type=s.relation_type,
                    depth=s.depth,
                    target_text=s.target_text,
                )
            )

        return GraphTraverseResult(
            source_path=clean_path,
            total_paths=len(agent_steps),
            paths=agent_steps,
        )

    async def corpus_backlog_poll(
        self,
        doc_slug: str | None = None,
        limit: int = 50,
    ) -> ChunkBacklogResult:
        """Polls unresolved context dependencies via ChunkContextRefRepository."""
        repo = await self._get_repo()
        rows = await repo.context_refs.get_unresolved_backlog(doc_slug=doc_slug, limit=limit)

        agent_items = [
            AgentBacklogItem(
                doc_slug=b.doc_slug,
                path=b.path,
                target_path=b.target_path,
                context_type=str(b.context_type),
                is_all_refs_resolved=b.is_all_refs_resolved,
                verbatim_text=b.verbatim_text,
                contextualized_text=b.contextualized_text,
                char_start=b.char_start,
                char_end=b.char_end,
                metadata=dict(b.metadata),
            )
            for b in rows
        ]

        return ChunkBacklogResult(
            total_unfinalized=len(agent_items),
            returned=len(agent_items),
            items=agent_items,
        )
