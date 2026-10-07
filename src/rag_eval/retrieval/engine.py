from __future__ import annotations

from dataclasses import dataclass

import asyncpg

from rag_eval.db.repositories import CorpusRepository
from rag_eval.retrieval.confidence import compute_search_confidence
from rag_eval.retrieval.embedder import QueryEmbedder
from rag_eval.retrieval.reranker import CorpusReranker
from rag_eval.schemas import HybridSearchQuery, SearchHitDTO


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
        only_resolved: bool = False,
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
            only_resolved=only_resolved,
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
