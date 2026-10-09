import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from rag_eval.ingestion.pipeline import DirectIngestionCoordinator


@pytest.mark.asyncio
async def test_direct_ingest_file(tmp_path: Path) -> None:
    """Verifies file-based direct ingestion."""
    mock_pool = MagicMock()
    mock_repo = MagicMock()
    mock_repo.documents.get_by_slug = AsyncMock(return_value=None)

    mock_loader = MagicMock()
    mock_loader.load_document = AsyncMock(return_value=uuid.uuid4())
    mock_loader.load_chunks = AsyncMock(return_value={"file_spec.p": uuid.uuid4()})
    mock_loader.load_graph_edges = AsyncMock(return_value={})
    mock_loader.resolve_chunk_paths = AsyncMock(return_value={})

    file_p = tmp_path / "test.md"
    file_p.write_text("# File Spec\n\nFile content.", encoding="utf-8")

    coordinator = DirectIngestionCoordinator(
        pool=mock_pool,
        compute_embeddings=False,
        corpus_repo=mock_repo,
        loader=mock_loader,
    )

    res = await coordinator.ingest_file(
        file_path=file_p,
        doc_slug="file_spec",
        title="File Spec",
    )

    assert res.doc_slug == "file_spec"
    assert res.chunks_count >= 1


@pytest.mark.asyncio
async def test_direct_ingest_bytes() -> None:
    """Verifies byte stream direct ingestion."""
    mock_pool = MagicMock()
    mock_repo = MagicMock()
    mock_repo.documents.get_by_slug = AsyncMock(return_value=None)

    mock_loader = MagicMock()
    mock_loader.load_document = AsyncMock(return_value=uuid.uuid4())
    mock_loader.load_chunks = AsyncMock(return_value={"byte_spec.p": uuid.uuid4()})
    mock_loader.load_graph_edges = AsyncMock(return_value={})
    mock_loader.resolve_chunk_paths = AsyncMock(return_value={})

    raw_bytes = b"# Byte Spec\n\nByte content paragraph."
    coordinator = DirectIngestionCoordinator(
        pool=mock_pool,
        compute_embeddings=False,
        corpus_repo=mock_repo,
        loader=mock_loader,
    )

    res = await coordinator.ingest_bytes(
        content=raw_bytes,
        file_name="byte_spec.md",
        doc_slug="byte_spec",
        title="Byte Spec",
    )

    assert res.doc_slug == "byte_spec"
    assert res.chunks_count >= 1
