from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from rag_eval.schemas import SearchHitDTO

LOW_SIMILARITY: Final[float] = 0.86
LOW_RERANK: Final[float] = -1.0


def compute_search_confidence(hits: Sequence[SearchHitDTO]) -> str:
    """Hàm thuần túy tính toán mức độ tin cậy của tập kết quả tìm kiếm dựa trên tín hiệu tương đồng và xếp hạng."""
    if not hits:
        return "none"
    max_dense = max(h.dense_similarity for h in hits)
    has_sparse = any((h.sparse_rank is not None and h.sparse_rank < 999) for h in hits)
    scores = [h.rerank_score for h in hits if h.rerank_score is not None]

    if scores and max(scores) < LOW_RERANK:
        return "low"
    if max_dense >= 0.82:
        return "high"
    if max_dense >= 0.70:
        return "medium" if not has_sparse else "high"
    if not has_sparse and max_dense < LOW_SIMILARITY:
        return "none"
    return "medium" if has_sparse else "low"
