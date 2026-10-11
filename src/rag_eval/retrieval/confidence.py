from __future__ import annotations

from collections.abc import Sequence
from typing import Final, Literal

from rag_eval.schemas import SearchHitDTO

LOW_SIMILARITY: Final[float] = 0.70
HIGH_SIMILARITY: Final[float] = 0.82
LOW_RERANK: Final[float] = -1.0

SearchConfidence = Literal["none", "low", "medium", "high"]


def compute_search_confidence(hits: Sequence[SearchHitDTO]) -> SearchConfidence:
    """Hàm thuần túy tính toán mức độ tin cậy của tập kết quả tìm kiếm với Sparse Match Gating.

    Invariants:
    1. Tập rỗng -> "none".
    2. Không có sparse match (has_sparse == False):
       - max_dense < LOW_SIMILARITY (0.70) -> "none".
       - max_dense >= LOW_SIMILARITY (0.70) -> trần tối đa là "low" (không bao giờ "medium" hay "high").
    3. Có sparse match (has_sparse == True):
       - Reranker veto (tất cả điểm rerank khả dụng < LOW_RERANK) -> ép xuống "low".
       - max_dense >= HIGH_SIMILARITY (0.82) -> "high".
       - max_dense >= LOW_SIMILARITY (0.70) -> "medium".
       - Còn lại -> "low".
    """
    if not hits:
        return "none"

    max_dense = max(h.dense_similarity for h in hits)
    has_sparse = any((h.sparse_rank is not None and h.sparse_rank < 999) for h in hits)
    scores = [h.rerank_score for h in hits if h.rerank_score is not None]

    if not has_sparse:
        return "low" if max_dense >= LOW_SIMILARITY else "none"

    # Confirmed sparse match
    if scores and max(scores) < LOW_RERANK:
        return "low"
    if max_dense >= HIGH_SIMILARITY:
        return "high"
    if max_dense >= LOW_SIMILARITY:
        return "medium"
    return "low"

