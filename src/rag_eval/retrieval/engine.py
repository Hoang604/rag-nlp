from __future__ import annotations

import asyncio
from dataclasses import dataclass

import asyncpg

from rag_eval.db.repositories import CorpusRepository
from rag_eval.retrieval.confidence import compute_search_confidence
from rag_eval.retrieval.embedder import QueryEmbedder
from rag_eval.retrieval.reranker import CorpusReranker
from rag_eval.schemas import (
    AgentVennHit,
    HybridSearchQuery,
    SearchHitDTO,
    VennSearchResult,
    VerbatimGrepQuery,
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
    ) -> VennSearchResult:
        """Executes concurrent dual-channel search, computes disjoint Venn sets,
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

        async def _exec_verbatim() -> list[SearchHitDTO]:
            grep_dto = VerbatimGrepQuery(
                query_pattern=pattern,
                target_documents=doc_slugs or None,
                path_prefix=path_prefix,
                is_regex=is_regex,
                case_sensitive=case_sensitive,
                match_limit=limit,
            )
            hits, _ = await repo.chunks.verbatim_grep(grep_dto)
            return hits[:limit]

        semantic_hits, verbatim_hits = await asyncio.gather(
            _exec_semantic(),
            _exec_verbatim(),
        )

        confidence = compute_search_confidence(semantic_hits)

        # Build index maps for Venn tri-partitioning
        semantic_map: dict[str, tuple[int, SearchHitDTO]] = {
            h.path: (idx, h) for idx, h in enumerate(semantic_hits, start=1)
        }
        verbatim_map: dict[str, tuple[int, SearchHitDTO]] = {
            h.path: (idx, h) for idx, h in enumerate(verbatim_hits, start=1)
        }

        both_hits: list[AgentVennHit] = []
        semantic_only_hits: list[AgentVennHit] = []
        verbatim_only_hits: list[AgentVennHit] = []

        # 1. Evaluate semantic hits: route to both_hits or semantic_only_hits
        for path, (s_rank, s_hit) in semantic_map.items():
            if path in verbatim_map:
                v_rank, v_hit = verbatim_map[path]
                both_hits.append(
                    AgentVennHit(
                        doc_slug=s_hit.doc_slug,
                        doc_title=s_hit.doc_title,
                        path=s_hit.path,
                        start_line=s_hit.start_line,
                        end_line=s_hit.end_line,
                        verbatim_text=s_hit.verbatim_text,
                        contextualized_text=s_hit.contextualized_text,
                        metadata=dict(s_hit.metadata),
                        semantic_rank=s_rank,
                        verbatim_rank=v_rank,
                        semantic_score=float(s_hit.score),
                        verbatim_score=float(v_hit.score),
                        rerank_score=float(s_hit.rerank_score)
                        if s_hit.rerank_score is not None
                        else None,
                    )
                )
            else:
                semantic_only_hits.append(
                    AgentVennHit(
                        doc_slug=s_hit.doc_slug,
                        doc_title=s_hit.doc_title,
                        path=s_hit.path,
                        start_line=s_hit.start_line,
                        end_line=s_hit.end_line,
                        verbatim_text=s_hit.verbatim_text,
                        contextualized_text=s_hit.contextualized_text,
                        metadata=dict(s_hit.metadata),
                        semantic_rank=s_rank,
                        verbatim_rank=None,
                        semantic_score=float(s_hit.score),
                        verbatim_score=None,
                        rerank_score=float(s_hit.rerank_score)
                        if s_hit.rerank_score is not None
                        else None,
                    )
                )

        # 2. Evaluate verbatim hits: route remaining to verbatim_only_hits
        for path, (v_rank, v_hit) in verbatim_map.items():
            if path not in semantic_map:
                verbatim_only_hits.append(
                    AgentVennHit(
                        doc_slug=v_hit.doc_slug,
                        doc_title=v_hit.doc_title,
                        path=v_hit.path,
                        start_line=v_hit.start_line,
                        end_line=v_hit.end_line,
                        verbatim_text=v_hit.verbatim_text,
                        contextualized_text=v_hit.contextualized_text,
                        metadata=dict(v_hit.metadata),
                        semantic_rank=None,
                        verbatim_rank=v_rank,
                        semantic_score=None,
                        verbatim_score=float(v_hit.score),
                        rerank_score=None,
                    )
                )

        total_unique = len(both_hits) + len(semantic_only_hits) + len(verbatim_only_hits)
        return VennSearchResult(
            query=query,
            pattern=pattern,
            both_hits=both_hits,
            semantic_only_hits=semantic_only_hits,
            verbatim_only_hits=verbatim_only_hits,
            total_unique_hits=total_unique,
            confidence=confidence,
        )
