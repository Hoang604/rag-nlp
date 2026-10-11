import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from rag_eval.exceptions import E_INVALID_DOCUMENT_HIERARCHY, CorpusDomainError
from rag_eval.retrieval.enrichment import (
    KnowledgeEnrichmentService,
    LinkResult,
    UnlinkResult,
)
from rag_eval.schemas import RelationType


@pytest.mark.asyncio
async def test_link_chunks_success() -> None:
    """Verifies S-02 / I-02 / I-04: Agent links two chunks via path with whitespace normalization and rationale."""
    mock_pool = MagicMock()
    mock_repo = MagicMock()

    src_id = uuid.uuid4()
    tgt_id = uuid.uuid4()

    mock_chunk = MagicMock()
    mock_chunk.id = src_id
    mock_chunk.verbatim_text = "Sample text in source chunk."
    mock_repo.chunks.get_by_path = AsyncMock(return_value=mock_chunk)
    mock_repo.chunks.resolve_paths_batch = AsyncMock(
        return_value={"doc.sec_1": src_id, "doc.sec_2": tgt_id}
    )
    mock_repo.graph.upsert_edges = AsyncMock(return_value={})

    service = KnowledgeEnrichmentService(pool=mock_pool, corpus_repo=mock_repo)
    result = await service.link_chunks(
        source_path="  doc.sec_1  ",
        target_path="  doc.sec_2  ",
        relation_type="REFERENCES",
        citation_text="Sample   text",
        rationale="Explanatory context connecting both sections.",
    )

    assert isinstance(result, LinkResult)
    assert result.source_path == "doc.sec_1"
    assert result.target_path == "doc.sec_2"
    assert result.relation_type == RelationType.REFERENCES
    assert result.citation_text == "Sample   text"
    assert result.rationale == "Explanatory context connecting both sections."
    assert result.created is True

    mock_repo.graph.upsert_edges.assert_awaited_once()
    upserted_edge = mock_repo.graph.upsert_edges.call_args[0][0][0]
    assert upserted_edge.rationale == "Explanatory context connecting both sections."


@pytest.mark.asyncio
async def test_link_chunks_self_loop_rejected() -> None:
    """Verifies I-02: Self-loop links are rejected fast."""
    mock_pool = MagicMock()
    service = KnowledgeEnrichmentService(pool=mock_pool)

    with pytest.raises(CorpusDomainError) as exc_info:
        await service.link_chunks(
            source_path="doc.sec_1",
            target_path="doc.sec_1",
            relation_type="REFERENCES",
            citation_text="Sample citation",
        )
    assert exc_info.value.error_code == E_INVALID_DOCUMENT_HIERARCHY


@pytest.mark.asyncio
async def test_link_chunks_invalid_relation_rejected() -> None:
    """Verifies I-02: Invalid relation type is rejected fast."""
    mock_pool = MagicMock()
    service = KnowledgeEnrichmentService(pool=mock_pool)

    with pytest.raises(CorpusDomainError) as exc_info:
        await service.link_chunks(
            source_path="doc.sec_1",
            target_path="doc.sec_2",
            relation_type="NON_EXISTENT_RELATION",
            citation_text="Sample citation",
        )
    assert exc_info.value.error_code == E_INVALID_DOCUMENT_HIERARCHY


@pytest.mark.asyncio
async def test_link_chunks_ungrounded_citation_rejected() -> None:
    """Verifies S-04 / I-04: Ungrounded citation text is rejected with E_AST_GROUNDING_VALIDATION."""
    from rag_eval.exceptions import E_AST_GROUNDING_VALIDATION

    mock_pool = MagicMock()
    mock_repo = MagicMock()
    mock_chunk = MagicMock()
    mock_chunk.verbatim_text = "Real source chunk text."
    mock_repo.chunks.get_by_path = AsyncMock(return_value=mock_chunk)

    service = KnowledgeEnrichmentService(pool=mock_pool, corpus_repo=mock_repo)
    with pytest.raises(CorpusDomainError) as exc_info:
        await service.link_chunks(
            source_path="doc.sec_1",
            target_path="doc.sec_2",
            relation_type="REFERENCES",
            citation_text="Hallucinated text not found in source chunk",
        )
    assert exc_info.value.error_code == E_AST_GROUNDING_VALIDATION


@pytest.mark.asyncio
async def test_link_chunks_empty_citation_rejected() -> None:
    """Verifies I-04: Empty or whitespace citation text is rejected with E_AST_GROUNDING_VALIDATION."""
    from rag_eval.exceptions import E_AST_GROUNDING_VALIDATION

    mock_pool = MagicMock()
    service = KnowledgeEnrichmentService(pool=mock_pool)
    with pytest.raises(CorpusDomainError) as exc_info:
        await service.link_chunks(
            source_path="doc.sec_1",
            target_path="doc.sec_2",
            relation_type="REFERENCES",
            citation_text="   ",
        )
    assert exc_info.value.error_code == E_AST_GROUNDING_VALIDATION


@pytest.mark.asyncio
async def test_unlink_chunks_success() -> None:
    """Verifies S-03 / I-03 / I-04: Agent unlinks chunks trigger-safely via GraphRepository."""
    mock_pool = MagicMock()
    mock_repo = MagicMock()

    src_id = uuid.uuid4()
    tgt_id = uuid.uuid4()

    mock_repo.chunks.resolve_paths_batch = AsyncMock(
        return_value={"doc.sec_1": src_id, "doc.sec_2": tgt_id}
    )
    mock_repo.graph.delete_directed_edge = AsyncMock(return_value=1)

    service = KnowledgeEnrichmentService(pool=mock_pool, corpus_repo=mock_repo)
    result = await service.unlink_chunks(
        source_path="  doc.sec_1  ",
        target_path="  doc.sec_2  ",
        relation_type="REFERENCES",
    )

    assert isinstance(result, UnlinkResult)
    assert result.source_path == "doc.sec_1"
    assert result.target_path == "doc.sec_2"
    assert result.removed_edges_count == 1
    mock_repo.graph.delete_directed_edge.assert_awaited_once()
