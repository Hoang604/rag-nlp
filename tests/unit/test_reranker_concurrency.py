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
            context_type="SELF_CONTAINED",
            is_all_refs_resolved=True,
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
    """Verifies that confidence is accurately calibrated: high dense similarity gives 'high' even with sparse rank 999."""
    # Test High Confidence: dense similarity >= 0.82
    high_dense_hit = SearchHitDTO(
        chunk_id=uuid.uuid4(),
        doc_slug="test_doc",
        doc_title="Technical Document",
        path="test_doc.sec_1",
        start_line=1,
        end_line=2,
        verbatim_text="Core specification content.",
        contextualized_text="Core specification content.",
        context_type="SELF_CONTAINED",
        is_all_refs_resolved=True,
        score=0.91,
        dense_similarity=0.91,
        dense_rank=1,
        sparse_rank=999,
    )
    assert compute_search_confidence([high_dense_hit]) == "high"

    # Test Medium Confidence: dense similarity between 0.70 and 0.82
    med_dense_hit = SearchHitDTO(
        chunk_id=uuid.uuid4(),
        doc_slug="test_doc",
        doc_title="Technical Document",
        path="test_doc.sec_1",
        start_line=1,
        end_line=2,
        verbatim_text="Core specification content.",
        contextualized_text="Core specification content.",
        context_type="SELF_CONTAINED",
        is_all_refs_resolved=True,
        score=0.75,
        dense_similarity=0.75,
        dense_rank=2,
        sparse_rank=999,
    )
    assert compute_search_confidence([med_dense_hit]) == "medium"

    # Test None Confidence: dense < 0.70 and sparse is 999
    low_hit = SearchHitDTO(
        chunk_id=uuid.uuid4(),
        doc_slug="test_doc",
        doc_title="Technical Document",
        path="test_doc.sec_1",
        start_line=1,
        end_line=2,
        verbatim_text="Core specification content.",
        contextualized_text="Core specification content.",
        context_type="SELF_CONTAINED",
        is_all_refs_resolved=True,
        score=0.40,
        dense_similarity=0.40,
        dense_rank=15,
        sparse_rank=999,
    )
    assert compute_search_confidence([low_hit]) == "none"
