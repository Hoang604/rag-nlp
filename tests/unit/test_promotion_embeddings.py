from unittest.mock import MagicMock, patch

import pytest

from rag_eval.legal.exceptions import E_CORPUS_INTEGRITY_VIOLATION, CorpusDomainError
from rag_eval.legal.ingestion.loader import compute_chunk_embeddings


def test_promotion_embeddings() -> None:
    """Verifies that compute_chunk_embeddings raises CorpusDomainError(E_CORPUS_INTEGRITY_VIOLATION) on model failure instead of silently returning None."""
    with patch("rag_eval.legal.ingestion.loader.get_embedding_model") as mock_get_model:
        mock_model = MagicMock()
        mock_model.encode.side_effect = RuntimeError("PyTorch CUDA out of memory")
        mock_get_model.return_value = mock_model

        with pytest.raises(CorpusDomainError) as exc_info:
            compute_chunk_embeddings(["Điều 1. Phạm vi điều chỉnh"])

        assert exc_info.value.error_code == E_CORPUS_INTEGRITY_VIOLATION
        assert "Neural embedding generation failed" in exc_info.value.message


def test_promotion_embeddings_empty_texts() -> None:
    """Verifies that empty texts return empty list without loading model."""
    res = compute_chunk_embeddings([])
    assert res == []
