import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch

import pytest

from rag_eval.retrieval.confidence import compute_search_confidence
from rag_eval.retrieval.reranker import CrossEncoderReranker, ThreadSafeScoreCache
from rag_eval.schemas import SearchHitDTO


def test_thread_safe_score_cache_concurrency() -> None:
    """Verifies that ThreadSafeScoreCache operates safely across 20 concurrent threads without size mutation errors."""
    cache = ThreadSafeScoreCache(maxsize=50)

    def cache_worker(tid: int) -> None:
        for i in range(100):
            key = (f"query_{tid}", f"passage_{i}")
            cache.put(key, float(i))
            val = cache.get(key)
            if val is not None:
                assert isinstance(val, float)

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(cache_worker, t) for t in range(20)]
        for f in futures:
            f.result()

    # Cache must respect maxsize bounded invariant
    assert len(cache._cache) <= 50


@pytest.mark.asyncio
async def test_single_hit_reranking() -> None:
    """Verifies that rerank() populates rerank_score even when given a single candidate hit."""
    with patch.dict("sys.modules", {"torch": MagicMock()}):
        mock_model = MagicMock()
        mock_model.predict.return_value = [0.85]
        reranker = CrossEncoderReranker(model=mock_model)
        hit = SearchHitDTO(
            chunk_id=uuid.uuid4(),
            doc_slug="test_doc",
            doc_title="Technical Document",
            path="test_doc.sec_1",
            start_line=1,
            end_line=2,
            verbatim_text="Pipeline component processing input data safely.",
            contextualized_text="Pipeline component processing input data safely.",
            score=0.85,
            dense_rank=1,
            sparse_rank=999,
            dense_similarity=0.85,
            rerank_score=None,
        )

        reranked = await reranker.rerank("processing input data", [hit])
        assert len(reranked) == 1
        assert reranked[0].rerank_score is not None
        assert isinstance(reranked[0].rerank_score, float)


def test_confidence_calibration() -> None:
    """Verifies that confidence is accurately calibrated:
    - With confirmed sparse match (sparse_rank < 999): evaluates high (>=0.82), medium (>=0.70), or low (<0.70).
    - Without sparse match (sparse_rank = 999): strictly gated to low (>=0.70) or none (<0.70), never high or medium.
    - Reranker veto: overrides confirmed sparse high confidence to low if scores are below threshold.
    """
    # 1. Confirmed Sparse Match Cases
    high_dense_sparse_hit = SearchHitDTO(
        chunk_id=uuid.uuid4(),
        doc_slug="test_doc",
        doc_title="Technical Document",
        path="test_doc.sec_1",
        start_line=1,
        end_line=2,
        verbatim_text="Core specification content.",
        contextualized_text="Core specification content.",
        score=0.91,
        dense_similarity=0.91,
        dense_rank=1,
        sparse_rank=1,
    )
    assert compute_search_confidence([high_dense_sparse_hit]) == "high"

    med_dense_sparse_hit = SearchHitDTO(
        chunk_id=uuid.uuid4(),
        doc_slug="test_doc",
        doc_title="Technical Document",
        path="test_doc.sec_1",
        start_line=1,
        end_line=2,
        verbatim_text="Core specification content.",
        contextualized_text="Core specification content.",
        score=0.75,
        dense_similarity=0.75,
        dense_rank=2,
        sparse_rank=1,
    )
    assert compute_search_confidence([med_dense_sparse_hit]) == "medium"

    low_dense_sparse_hit = SearchHitDTO(
        chunk_id=uuid.uuid4(),
        doc_slug="test_doc",
        doc_title="Technical Document",
        path="test_doc.sec_1",
        start_line=1,
        end_line=2,
        verbatim_text="Core specification content.",
        contextualized_text="Core specification content.",
        score=0.55,
        dense_similarity=0.55,
        dense_rank=10,
        sparse_rank=1,
    )
    assert compute_search_confidence([low_dense_sparse_hit]) == "low"

    # 2. Sparse Match Gating Cases (sparse_rank = 999: no sparse match)
    # Even with high dense similarity (0.91), absence of sparse match strictly caps confidence at "low"
    high_dense_unsparse_hit = SearchHitDTO(
        chunk_id=uuid.uuid4(),
        doc_slug="test_doc",
        doc_title="Technical Document",
        path="test_doc.sec_1",
        start_line=1,
        end_line=2,
        verbatim_text="Core specification content.",
        contextualized_text="Core specification content.",
        score=0.91,
        dense_similarity=0.91,
        dense_rank=1,
        sparse_rank=999,
    )
    assert compute_search_confidence([high_dense_unsparse_hit]) == "low"

    med_dense_unsparse_hit = SearchHitDTO(
        chunk_id=uuid.uuid4(),
        doc_slug="test_doc",
        doc_title="Technical Document",
        path="test_doc.sec_1",
        start_line=1,
        end_line=2,
        verbatim_text="Core specification content.",
        contextualized_text="Core specification content.",
        score=0.75,
        dense_similarity=0.75,
        dense_rank=2,
        sparse_rank=999,
    )
    assert compute_search_confidence([med_dense_unsparse_hit]) == "low"

    # Low dense (<0.70) without sparse match evaluates to "none"
    low_unsparse_hit = SearchHitDTO(
        chunk_id=uuid.uuid4(),
        doc_slug="test_doc",
        doc_title="Technical Document",
        path="test_doc.sec_1",
        start_line=1,
        end_line=2,
        verbatim_text="Core specification content.",
        contextualized_text="Core specification content.",
        score=0.40,
        dense_similarity=0.40,
        dense_rank=15,
        sparse_rank=999,
    )
    assert compute_search_confidence([low_unsparse_hit]) == "none"

    # 3. Reranker Veto Case
    vetoed_hit = SearchHitDTO(
        chunk_id=uuid.uuid4(),
        doc_slug="test_doc",
        doc_title="Technical Document",
        path="test_doc.sec_1",
        start_line=1,
        end_line=2,
        verbatim_text="Core specification content.",
        contextualized_text="Core specification content.",
        score=0.91,
        dense_similarity=0.91,
        dense_rank=1,
        sparse_rank=1,
        rerank_score=-1.5,
    )
    assert compute_search_confidence([vetoed_hit]) == "low"

