from __future__ import annotations

import asyncio
from dataclasses import dataclass

import asyncpg

from rag_eval.db.repositories import CorpusRepository
from rag_eval.retrieval.confidence import compute_search_confidence
from rag_eval.retrieval.embedder import QueryEmbedder
from rag_eval.retrieval.reranker import CorpusReranker
from rag_eval.schemas import (
    HybridSearchQuery,
    ProvisionText,
    SearchDocument,
    SearchFoundIn,
    SearchHitDTO,
    UnifiedSearchResult,
    VerbatimGrepQuery,
    clean_node_metadata,
    group_ranked,
    split_context_and_text,
)


@dataclass(frozen=True)
class SearchPipelineResult:
    hits: list[SearchHitDTO]
    confidence: str
    expanded_query: str


class RetrievalEngine:
    """Canonical search & rerank pipeline coordinator shared by Web and MCP."""

    def __init__(
        self,
        pool: asyncpg.Pool,
        embedder: QueryEmbedder | None = None,
        reranker: CorpusReranker | None = None,
        rerank_by_default: bool = False,
    ) -> None:
        self._pool = pool
        self._embedder = embedder
        self._reranker = reranker
        self._rerank_by_default = rerank_by_default

    async def embed_query_safe(self, query: str) -> list[float] | None:
        if self._embedder is None:
            return None
        try:
            return await self._embedder.embed_query(query)
        except (RuntimeError, ValueError, TypeError, OSError, AttributeError) as exc:
            import logging

            logging.getLogger(__name__).warning(
                "Dense query embedding failed, degrading to sparse BM25: %s", exc
            )
            return None

    async def search(
        self,
        query: str,
        limit: int = 10,
        rerank: bool | None = None,
        rerank_pool: int = 10,
        doc_slugs: list[str] | None = None,
        path_prefix: str | None = None,
    ) -> SearchPipelineResult:
        repo = CorpusRepository(self._pool)
        query_vector = await self.embed_query_safe(query)

        want_rerank = self._rerank_by_default if rerank is None else rerank
        want_rerank = want_rerank and self._reranker is not None
        fetch_limit = max(limit, rerank_pool) if want_rerank else limit

        query_dto = HybridSearchQuery(
            query_text=query,
            query_vector=query_vector,
            match_limit=fetch_limit,
            rrf_k=60,
            target_documents=doc_slugs or None,
            path_prefix=path_prefix,
            ts_config="simple",
        )
        hits = await repo.chunks.hybrid_search(query_dto)
        if want_rerank and self._reranker is not None and len(hits) > 1:
            hits = await self._reranker.rerank(query, hits, top_k=limit)
        else:
            hits = hits[:limit]

        return SearchPipelineResult(
            hits=hits,
            confidence=compute_search_confidence(hits),
            expanded_query=query,
        )

    async def search_venn(
        self,
        query: str,
        pattern: str,
        limit: int = 10,
        rerank: bool | None = None,
        rerank_pool: int = 10,
        doc_slugs: list[str] | None = None,
        path_prefix: str | None = None,
        is_regex: bool = False,
        case_sensitive: bool = False,
        order_by_reading_order: bool = False,
    ) -> UnifiedSearchResult:
        """Executes concurrent dual-channel search, computes factored Venn sets,
        evaluates CrossEncoder reranking, and dynamically computes confidence.
        """
        repo = CorpusRepository(self._pool)

        want_rerank = self._rerank_by_default if rerank is None else rerank
        want_rerank = want_rerank and self._reranker is not None
        fetch_limit = max(limit, rerank_pool) if want_rerank else limit

        async def _exec_semantic() -> list[SearchHitDTO]:
            query_vector = await self.embed_query_safe(query)
            query_dto = HybridSearchQuery(
                query_text=query,
                query_vector=query_vector,
                match_limit=fetch_limit,
                rrf_k=60,
                target_documents=doc_slugs or None,
                path_prefix=path_prefix,
                ts_config="simple",
            )
            raw_hits = await repo.chunks.hybrid_search(query_dto)
            if want_rerank and self._reranker is not None and len(raw_hits) > 1:
                return await self._reranker.rerank(query, raw_hits, top_k=limit)
            return raw_hits[:limit]

        async def _exec_verbatim() -> tuple[list[SearchHitDTO], int]:
            grep_dto = VerbatimGrepQuery(
                query_pattern=pattern,
                target_documents=doc_slugs or None,
                path_prefix=path_prefix,
                is_regex=is_regex,
                case_sensitive=case_sensitive,
                match_limit=limit,
                order_by_reading_order=order_by_reading_order,
            )
            hits, total_count = await repo.chunks.verbatim_grep(grep_dto)
            return hits[:limit], total_count

        semantic_hits, (verbatim_hits, verbatim_total) = await asyncio.gather(
            _exec_semantic(),
            _exec_verbatim(),
        )

        confidence = compute_search_confidence(semantic_hits)

        # Build index maps for Venn partitioning
        semantic_map: dict[str, SearchHitDTO] = {h.path: h for h in semantic_hits}
        verbatim_map: dict[str, SearchHitDTO] = {h.path: h for h in verbatim_hits}

        matches: list[tuple[SearchFoundIn, str, str, ProvisionText]] = []
        documents: dict[str, SearchDocument] = {}

        # 1. 'both' matches in semantic order
        for s_hit in semantic_hits:
            if s_hit.path in verbatim_map:
                ctx, txt = split_context_and_text(s_hit.contextualized_text, s_hit.verbatim_text)
                prov = ProvisionText(
                    path=s_hit.path,
                    text=txt,
                    start_line=s_hit.start_line,
                    end_line=s_hit.end_line,
                    metadata=clean_node_metadata(s_hit.metadata),
                )
                matches.append(("both", s_hit.doc_slug, ctx, prov))
                if s_hit.doc_slug not in documents:
                    documents[s_hit.doc_slug] = SearchDocument(
                        doc_slug=s_hit.doc_slug,
                        title=s_hit.doc_title or s_hit.doc_slug,
                        metadata={},
                    )

        # 2. 'semantic_only' matches in semantic order
        for s_hit in semantic_hits:
            if s_hit.path not in verbatim_map:
                ctx, txt = split_context_and_text(s_hit.contextualized_text, s_hit.verbatim_text)
                prov = ProvisionText(
                    path=s_hit.path,
                    text=txt,
                    start_line=s_hit.start_line,
                    end_line=s_hit.end_line,
                    metadata=clean_node_metadata(s_hit.metadata),
                )
                matches.append(("semantic_only", s_hit.doc_slug, ctx, prov))
                if s_hit.doc_slug not in documents:
                    documents[s_hit.doc_slug] = SearchDocument(
                        doc_slug=s_hit.doc_slug,
                        title=s_hit.doc_title or s_hit.doc_slug,
                        metadata={},
                    )

        # 3. 'verbatim_only' matches in verbatim order
        for v_hit in verbatim_hits:
            if v_hit.path not in semantic_map:
                ctx, txt = split_context_and_text(v_hit.contextualized_text, v_hit.verbatim_text)
                prov = ProvisionText(
                    path=v_hit.path,
                    text=txt,
                    start_line=v_hit.start_line,
                    end_line=v_hit.end_line,
                    metadata=clean_node_metadata(v_hit.metadata),
                )
                matches.append(("verbatim_only", v_hit.doc_slug, ctx, prov))
                if v_hit.doc_slug not in documents:
                    documents[v_hit.doc_slug] = SearchDocument(
                        doc_slug=v_hit.doc_slug,
                        title=v_hit.doc_title or v_hit.doc_slug,
                        metadata={},
                    )

        groups = group_ranked(matches)
        verbatim_truncated = verbatim_total > len(verbatim_hits)

        return UnifiedSearchResult(
            query=query,
            pattern=pattern,
            documents=documents,
            groups=groups,
            verbatim_total=verbatim_total,
            verbatim_truncated=verbatim_truncated,
            confidence=confidence,
        )
