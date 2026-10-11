from __future__ import annotations

import asyncio
import logging
from typing import Final

import asyncpg

from rag_eval.db.connection import get_db_pool
from rag_eval.db.repositories import CorpusRepository
from rag_eval.exceptions import (
    E_AST_GROUNDING_VALIDATION,
    E_CORPUS_INTEGRITY_VIOLATION,
    E_INVALID_DOCUMENT_HIERARCHY,
    CorpusDomainError,
)
from rag_eval.retrieval.embedder import QueryEmbedder
from rag_eval.retrieval.engine import RetrievalEngine
from rag_eval.retrieval.reranker import CorpusReranker
from rag_eval.schemas import (
    GraphDirection,
    GraphLink,
    GraphTraversalStepDTO,
    HierarchicalDirection,
    HierarchyNodeDTO,
    ProvisionText,
    RawDocumentSliceResult,
    RelationType,
    SearchDocument,
    UnifiedGraphTraverseResult,
    UnifiedHierarchyResult,
    UnifiedSearchResult,
    clean_node_metadata,
    group_in_reading_order,
    split_context_and_text,
    validate_ltree_path,
)

logger = logging.getLogger("rag_eval.mcp.tools.sensors")

RERANK_POOL: Final[int] = 10
MAX_RAW_LINES: Final[int] = 200


# ---------------------------------------------------------------------------
# Canonical Agent-First Models & Result Containers
# ---------------------------------------------------------------------------





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
        order_by_reading_order: bool = False,
    ) -> UnifiedSearchResult:
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
                order_by_reading_order=order_by_reading_order,
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
        limit: int = 15,
    ) -> UnifiedHierarchyResult:
        """Navigates hierarchical document tree via ChunkRepository, factoring results
        into reading-order context groups bounded by limit.
        """
        repo = await self._get_repo()
        clean_path = validate_ltree_path(path)
        origin_chunk = await repo.chunks.get_by_path(clean_path)
        if not origin_chunk:
            parts = clean_path.split(".")
            matched_doc = None
            for start_idx in range(len(parts)):
                for end_idx in range(len(parts), start_idx, -1):
                    cand = ".".join(parts[start_idx:end_idx])
                    doc = await repo.documents.get_by_slug(cand)
                    if doc:
                        matched_doc = doc
                        break
                if matched_doc:
                    break

            if matched_doc:
                doc_chunks = await repo.chunks.list_by_document(matched_doc.id)
                matching = [c for c in doc_chunks if c.path.startswith(clean_path) or c.path == clean_path]
                if matching:
                    origin_chunk = min(matching, key=lambda c: c.start_line)
                elif doc_chunks:
                    origin_chunk = min(doc_chunks, key=lambda c: c.start_line)

            if not origin_chunk:
                for start_idx in range(len(parts)):
                    prefix_cand = ".".join(parts[start_idx:])
                    matching_docs = await repo.documents.list_by_prefix(prefix_cand)
                    if matching_docs:
                        matched_doc = matching_docs[0]
                        doc_chunks = await repo.chunks.list_by_document(matched_doc.id)
                        if doc_chunks:
                            origin_chunk = min(doc_chunks, key=lambda c: c.start_line)
                            break

        if not origin_chunk:
            raise CorpusDomainError(
                error_code=E_INVALID_DOCUMENT_HIERARCHY,
                message=f"Không tìm thấy chunk tương ứng với path='{clean_path}'.",
            )

        dir_val = direction.value if isinstance(direction, HierarchicalDirection) else str(direction)
        dir_enum = HierarchicalDirection(dir_val)
        nav_anchor = (
            clean_path
            if (
                dir_enum in (HierarchicalDirection.CHILDREN, HierarchicalDirection.SUBTREE)
                and clean_path != origin_chunk.path
                and origin_chunk.path.startswith(clean_path)
            )
            else origin_chunk.path
        )
        nodes_dto = await repo.chunks.navigate_hierarchy(
            origin_chunk.document_id, nav_anchor, dir_val
        )
        if not nodes_dto and dir_enum == HierarchicalDirection.CHILDREN:
            doc = await repo.documents.get_by_id(origin_chunk.document_id)
            doc_slug_val = doc.doc_slug if doc else clean_path
            all_doc_chunks = await repo.chunks.list_by_document(origin_chunk.document_id)
            matching_children = [
                c for c in all_doc_chunks
                if c.path.startswith(clean_path) and c.path != clean_path
            ]
            if matching_children:
                nodes_dto = [
                    HierarchyNodeDTO(
                        chunk_id=c.id,
                        path=c.path,
                        doc_slug=doc_slug_val,
                        start_line=c.start_line,
                        end_line=c.end_line,
                        verbatim_text=c.verbatim_text,
                        contextualized_text=c.contextualized_text,
                        metadata=c.metadata,
                        relative_depth=1,
                    )
                    for c in matching_children
                ]

        total = len(nodes_dto)
        effective_limit = max(1, min(limit, 50))
        truncated = total > effective_limit
        selected_nodes = nodes_dto[:effective_limit]

        doc = await repo.documents.get_by_id(origin_chunk.document_id)
        doc_slug = doc.doc_slug if doc else clean_path.split(".")[0]
        doc_title = doc.title if doc else doc_slug
        documents: dict[str, SearchDocument] = {
            doc_slug: SearchDocument(doc_slug=doc_slug, title=doc_title, metadata={})
        }

        reading_items: list[tuple[str, str, ProvisionText]] = []
        for n in selected_nodes:
            ctx, txt = split_context_and_text(n.contextualized_text, n.verbatim_text)
            reading_items.append(
                (
                    n.doc_slug or doc_slug,
                    ctx,
                    ProvisionText(
                        path=n.path,
                        text=txt,
                        start_line=n.start_line,
                        end_line=n.end_line,
                        metadata=clean_node_metadata(n.metadata),
                    ),
                )
            )

        groups = group_in_reading_order(reading_items)

        return UnifiedHierarchyResult(
            anchor_path=origin_chunk.path,
            direction=dir_enum,
            documents=documents,
            groups=groups,
            total=total,
            truncated=truncated,
        )

    async def graph_traverse(
        self,
        source_path: str,
        direction: GraphDirection = GraphDirection.OUTGOING,
        max_depth: int = 2,
        filter_relations: list[RelationType] | None = None,
        limit_per_link: int = 20,
    ) -> UnifiedGraphTraverseResult:
        """Traverses knowledge graph, grouping steps by citation provenance with fair quotas."""
        repo = await self._get_repo()
        clean_path = validate_ltree_path(source_path)
        chunk = await repo.chunks.get_by_path(clean_path)
        if not chunk:
            raise CorpusDomainError(
                error_code=E_INVALID_DOCUMENT_HIERARCHY,
                message=f"Không tìm thấy chunk tương ứng với source_path='{source_path}'.",
            )

        # Overfetch to allow fair per-link quotas
        effective_quota = max(1, min(limit_per_link, 100))
        match_limit = max_depth * effective_quota * 10
        filter_codes = [r.value for r in filter_relations] if filter_relations else None
        steps_dto = await repo.graph.traverse(
            chunk.id,
            nav_direction=direction.value,
            depth_limit=max_depth,
            filter_relations=filter_codes,
            match_limit=match_limit,
        )

        # Partition steps into citation links
        link_buckets: dict[tuple[str, GraphDirection, str, str, int], list[GraphTraversalStepDTO]] = {}
        for s in steps_dto:
            key = (s.source_path, direction, s.relation_type, s.citation_text, s.depth)
            if key not in link_buckets:
                link_buckets[key] = []
            link_buckets[key].append(s)

        # Batch resolve document titles for all reached documents
        distinct_slugs = list({s.target_doc_slug for s in steps_dto if s.target_doc_slug})
        docs = await repo.documents.list_by_slugs(distinct_slugs)
        documents: dict[str, SearchDocument] = {
            d.doc_slug: SearchDocument(doc_slug=d.doc_slug, title=d.title, metadata={})
            for d in docs
        }
        for slug in distinct_slugs:
            if slug not in documents:
                documents[slug] = SearchDocument(doc_slug=slug, title=slug, metadata={})

        graph_links: list[GraphLink] = []
        for (from_p, d_dir, rel_t, cit_txt, depth), steps in link_buckets.items():
            total = len(steps)
            truncated = total > effective_quota
            selected = steps[:effective_quota]

            items: list[tuple[str, str, ProvisionText]] = []
            for s in selected:
                ctx, txt = split_context_and_text(s.target_contextualized_text, s.target_text)
                items.append(
                    (
                        s.target_doc_slug,
                        ctx,
                        ProvisionText(
                            path=s.target_path,
                            text=txt,
                            start_line=s.target_start_line,
                            end_line=s.target_end_line,
                            metadata={},
                        ),
                    )
                )

            groups = group_in_reading_order(items)
            graph_links.append(
                GraphLink(
                    from_path=from_p,
                    direction=d_dir,
                    relation_type=rel_t,
                    citation_text=cit_txt,
                    depth=depth,
                    total=total,
                    truncated=truncated,
                    groups=groups,
                )
            )

        return UnifiedGraphTraverseResult(
            source_path=clean_path,
            documents=documents,
            links=graph_links,
        )

    async def get_raw(
        self,
        path_or_slug: str,
        start_line: int = 1,
        end_line: int | None = None,
    ) -> RawDocumentSliceResult:
        """Retrieves raw unparsed slice of document text within [start_line, end_line] (max 200 lines)."""
        clean_input = path_or_slug.strip()
        if not clean_input:
            raise CorpusDomainError(
                error_code=E_AST_GROUNDING_VALIDATION,
                message="Tham số 'path_or_slug' không được để trống.",
            )

        repo = await self._get_repo()

        # 1. Resolve document by slug directly
        doc = await repo.documents.get_by_slug(clean_input)

        # 2. If not found, resolve via chunk LTree path
        if not doc:
            try:
                clean_path = validate_ltree_path(clean_input)
                origin_chunk = await repo.chunks.get_by_path(clean_path)
                if origin_chunk:
                    doc = await repo.documents.get_by_id(origin_chunk.document_id)
            except ValueError:
                origin_chunk = None

        # 3. If still not found, try matching document by prefix or substring
        if not doc:
            matching_docs = await repo.documents.list_by_prefix(clean_input)
            if matching_docs:
                doc = matching_docs[0]

        if not doc:
            raise CorpusDomainError(
                error_code=E_INVALID_DOCUMENT_HIERARCHY,
                message=f"Không tìm thấy tài liệu hoặc chunk tương ứng với '{clean_input}'.",
            )

        if doc.raw_text is None:
            raise CorpusDomainError(
                error_code=E_CORPUS_INTEGRITY_VIOLATION,
                message=f"Tài liệu '{doc.doc_slug}' không có raw_text trong cơ sở dữ liệu.",
            )

        lines = doc.raw_text.splitlines()
        total_lines = len(lines)

        if start_line < 1:
            raise CorpusDomainError(
                error_code=E_AST_GROUNDING_VALIDATION,
                message=f"start_line ({start_line}) phải >= 1.",
            )

        if total_lines == 0:
            return RawDocumentSliceResult(
                doc_slug=doc.doc_slug,
                title=doc.title,
                start_line=1,
                end_line=1,
                total_lines=0,
                raw_text="",
            )

        if start_line > total_lines:
            raise CorpusDomainError(
                error_code=E_AST_GROUNDING_VALIDATION,
                message=f"start_line ({start_line}) vượt quá tổng số dòng của tài liệu ({total_lines}).",
            )

        if end_line is None:
            effective_end = min(total_lines, start_line + MAX_RAW_LINES - 1)
        else:
            if end_line < start_line:
                raise CorpusDomainError(
                    error_code=E_AST_GROUNDING_VALIDATION,
                    message=f"end_line ({end_line}) không được nhỏ hơn start_line ({start_line}).",
                )
            requested_span = end_line - start_line + 1
            if requested_span > MAX_RAW_LINES:
                raise CorpusDomainError(
                    error_code=E_AST_GROUNDING_VALIDATION,
                    message=(
                        f"Phạm vi yêu cầu ({requested_span} dòng) vượt quá giới hạn tối đa cho phép "
                        f"là {MAX_RAW_LINES} dòng mỗi lần gọi. Vui lòng thu hẹp khoảng [start_line, end_line]."
                    ),
                )
            effective_end = min(total_lines, end_line)

        sliced_lines = lines[start_line - 1 : effective_end]
        raw_slice = "\n".join(sliced_lines)

        return RawDocumentSliceResult(
            doc_slug=doc.doc_slug,
            title=doc.title,
            start_line=start_line,
            end_line=effective_end,
            total_lines=total_lines,
            raw_text=raw_slice,
        )


__all__ = [
    "MAX_RAW_LINES",
    "RERANK_POOL",
    "CorpusRuntimeSensors",
    "GraphDirection",
    "HierarchicalDirection",
    "RawDocumentSliceResult",
    "RelationType",
    "UnifiedGraphTraverseResult",
    "UnifiedHierarchyResult",
    "UnifiedSearchResult",
]
