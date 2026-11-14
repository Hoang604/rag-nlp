import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from rag_eval.exceptions import E_CORPUS_INTEGRITY_VIOLATION, CorpusDomainError
from rag_eval.ingestion.pipeline import DirectIngestionCoordinator
from rag_eval.schemas import ParsedChunkDraft, ParsedDocumentDraft


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

    file_p = tmp_path / "test.mdx"
    file_p.write_text("---\ntitle: File Spec\n---\n\n# File Spec\n\nFile content.", encoding="utf-8")

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

    raw_bytes = b"---\ntitle: Byte Spec\n---\n\n# Byte Spec\n\nByte content paragraph."
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


def _make_coordinator() -> DirectIngestionCoordinator:
    mock_pool = MagicMock()
    mock_repo = MagicMock()
    mock_repo.documents.get_by_slug = AsyncMock(return_value=None)
    mock_loader = MagicMock()
    return DirectIngestionCoordinator(
        pool=mock_pool,
        compute_embeddings=False,
        corpus_repo=mock_repo,
        loader=mock_loader,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("chunks", "expected_fragment"),
    [
        (
            [
                ParsedChunkDraft("doc.a", "Line 1\nLine 2", "[Doc]\nLine 1\nLine 2", 1, 2, {}),
                ParsedChunkDraft("doc.b", "Line 2\nLine 3", "[Doc]\nLine 2\nLine 3", 2, 3, {}),
            ],
            "Overlapping chunk line spans",
        ),
        (
            [
                ParsedChunkDraft("doc.a", "Line 1", "[Doc]\nLine 1", 1, 5, {}),
            ],
            "out of bounds",
        ),
        (
            [
                ParsedChunkDraft("doc.a", "   ", "   ", 1, 1, {}),
            ],
            "empty verbatim_text",
        ),
        (
            [
                ParsedChunkDraft("doc.a", "Line 1", "[Doc]\nOther text", 1, 1, {}),
            ],
            "does not match verbatim_text",
        ),
        (
            [
                ParsedChunkDraft("other.a", "Line 1", "[Doc]\nLine 1", 1, 1, {}),
            ],
            "escapes document namespace",
        ),
        (
            [
                ParsedChunkDraft("doc.a", "Line 1", "[Doc]\nLine 1", 1, 1, {}),
                ParsedChunkDraft("doc.a", "Line 2", "[Doc]\nLine 2", 2, 2, {}),
            ],
            "Duplicate chunk path",
        ),
    ],
)
async def test_ingest_draft_rejects_domain_agnostic_invariant_violations(
    chunks: list[ParsedChunkDraft],
    expected_fragment: str,
) -> None:
    """Verifies DirectIngestionCoordinator rejects overlapping spans, out-of-bounds lines,
    empty verbatim_text, mismatched contextualized_text, duplicate paths, and namespace escapes.
    """
    coordinator = _make_coordinator()
    draft = ParsedDocumentDraft(
        doc_slug="doc",
        title="Doc",
        raw_text="Line 1\nLine 2\nLine 3",
        chunks=chunks,
        edges=[],
        metadata={},
    )

    with pytest.raises(CorpusDomainError) as exc_info:
        await coordinator._ingest_draft(draft)

    assert exc_info.value.error_code == E_CORPUS_INTEGRITY_VIOLATION
    assert expected_fragment in exc_info.value.message
