from unittest.mock import MagicMock, patch

import pytest

from rag_eval.exceptions import E_CORPUS_INTEGRITY_VIOLATION, CorpusDomainError
from rag_eval.ingestion.loader import compute_chunk_embeddings


def test_chunk_embeddings_exception_shielding() -> None:
    """Verifies that compute_chunk_embeddings raises CorpusDomainError(E_CORPUS_INTEGRITY_VIOLATION) on model failure."""
    with (
        patch("rag_eval.ingestion.loader.get_embedding_model") as mock_get_model,
        patch.dict("sys.modules", {"torch": MagicMock()}),
    ):
        mock_model = MagicMock()
        mock_model.encode.side_effect = RuntimeError("PyTorch CUDA out of memory")
        mock_get_model.return_value = mock_model

        with pytest.raises(CorpusDomainError) as exc_info:
            compute_chunk_embeddings(["Chunk 1. Structural specification"])

        assert exc_info.value.error_code == E_CORPUS_INTEGRITY_VIOLATION
