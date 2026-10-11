from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from rag_eval.exceptions import (
    E_AST_GROUNDING_VALIDATION,
    E_INVALID_DOCUMENT_HIERARCHY,
    CorpusDomainError,
)
from rag_eval.retrieval.enrichment import KnowledgeEnrichmentService
from rag_eval.schemas import (
    CurateEdgesResult,
    EdgeKey,
    EdgeProposal,
    GraphEdgeEntity,
)


@pytest.mark.asyncio
async def test_curate_edges_missing_reason_rejected() -> None:
    """Verifies missing or empty audit reason is rejected with E_AST_GROUNDING_VALIDATION."""
    mock_pool = MagicMock()
    service = KnowledgeEnrichmentService(pool=mock_pool)

    with pytest.raises(CorpusDomainError) as exc_info:
        await service.curate_edges(
            add_edges=[
                EdgeProposal(
                    source_path="doc.sec_1",
                    target_path="doc.sec_2",
                    relation_type="REFERENCES",
                    citation_text="Sample citation",
                )
            ],
            reason="   ",
        )
    assert exc_info.value.error_code == E_AST_GROUNDING_VALIDATION
    assert exc_info.value.data.get("violation_code") == "MISSING_REASON"


@pytest.mark.asyncio
async def test_curate_edges_self_loop_rejected() -> None:
    """Verifies I-01 / I-05: Self-loop links are rejected fast."""
    mock_pool = MagicMock()
    service = KnowledgeEnrichmentService(pool=mock_pool)

    with pytest.raises(CorpusDomainError) as exc_info:
        await service.curate_edges(
            add_edges=[
                EdgeProposal(
                    source_path="doc.sec_1",
                    target_path="doc.sec_1",
                    relation_type="REFERENCES",
                    citation_text="Sample citation",
                )
            ],
            reason="Self loop test",
        )
    assert exc_info.value.error_code == E_INVALID_DOCUMENT_HIERARCHY
    assert exc_info.value.data.get("violation_code") == "SELF_REFERENCING_EDGE"


@pytest.mark.asyncio
async def test_curate_edges_invalid_relation_rejected() -> None:
    """Verifies I-05: Invalid relation type is rejected fast by schema validation."""
    with pytest.raises(ValidationError):
        EdgeProposal(
            source_path="doc.sec_1",
            target_path="doc.sec_2",
            relation_type="NON_EXISTENT_RELATION",  # type: ignore[arg-type]
            citation_text="Sample citation",
        )


@pytest.mark.asyncio
async def test_curate_edges_ungrounded_citation_rejected() -> None:
    """Verifies S-06 / I-05: Ungrounded citation text is rejected with UNGROUNDED_CITATION_TEXT."""
    mock_pool = MagicMock()
    mock_conn = MagicMock()
    mock_tx = AsyncMock()
    mock_conn.transaction.return_value = mock_tx
    mock_acquire = AsyncMock()
    mock_acquire.__aenter__.return_value = mock_conn
    mock_pool.acquire.return_value = mock_acquire

    mock_repo = MagicMock()
    src_id = uuid.uuid4()
    mock_repo.chunks.get_verbatim_by_paths = AsyncMock(
        return_value={"doc.sec_1": (src_id, "Real source chunk text content.")}
    )
    mock_repo.chunks.expand_to_leaf_paths = AsyncMock(
        return_value={"doc.sec_2": [("doc.sec_2", uuid.uuid4())]}
    )

    service = KnowledgeEnrichmentService(pool=mock_pool, corpus_repo=mock_repo)
    with pytest.raises(CorpusDomainError) as exc_info:
        await service.curate_edges(
            add_edges=[
                EdgeProposal(
                    source_path="doc.sec_1",
                    target_path="doc.sec_2",
                    relation_type="REFERENCES",
                    citation_text="Hallucinated text not found in source chunk",
                )
            ],
            reason="Testing ungrounded rejection",
        )
    assert exc_info.value.error_code == E_AST_GROUNDING_VALIDATION
    assert exc_info.value.data.get("violation_code") == "UNGROUNDED_CITATION_TEXT"


@pytest.mark.asyncio
async def test_curate_edges_atomic_batch_success() -> None:
    """Verifies S-05 / I-05: Agent curates batch edge additions and removals atomically."""
    mock_pool = MagicMock()
    mock_conn = MagicMock()
    mock_tx = AsyncMock()
    mock_conn.transaction.return_value = mock_tx
    mock_acquire = AsyncMock()
    mock_acquire.__aenter__.return_value = mock_conn
    mock_pool.acquire.return_value = mock_acquire

    mock_repo = MagicMock()
    src_id = uuid.uuid4()
    tgt_leaf_1 = uuid.uuid4()
    tgt_leaf_2 = uuid.uuid4()

    mock_repo.chunks.get_verbatim_by_paths = AsyncMock(
        return_value={"doc.sec_1": (src_id, "Source text with citation quote.")}
    )
    # Container expansion: doc.sec_container fans out to two leaves
    mock_repo.chunks.expand_to_leaf_paths = AsyncMock(
        return_value={
            "doc.sec_container": [
                ("doc.sec_container.child_a", tgt_leaf_1),
                ("doc.sec_container.child_b", tgt_leaf_2),
            ],
            "doc.old_target": [
                ("doc.old_target", uuid.uuid4()),
            ],
        }
    )

    async def fake_insert(entities: list[GraphEdgeEntity], **_kwargs: object) -> list[GraphEdgeEntity]:
        return entities

    mock_repo.graph.insert_edges_atomic = AsyncMock(side_effect=fake_insert)
    mock_repo.graph.log_edge_events = AsyncMock()

    # Deletion mock
    edge_to_del_id = uuid.uuid4()
    mock_repo.graph.find_edges = AsyncMock(
        return_value=[
            (edge_to_del_id, "doc.sec_1", "doc.old_target", "REFERENCES", "citation to del")
        ]
    )
    mock_repo.graph.delete_edge = AsyncMock()

    service = KnowledgeEnrichmentService(pool=mock_pool, corpus_repo=mock_repo)
    result = await service.curate_edges(
        add_edges=[
            EdgeProposal(
                source_path="doc.sec_1",
                target_path="doc.sec_container",
                relation_type="REFERENCES",
                citation_text="citation quote",
                rationale="Container link justification",
            )
        ],
        remove_edges=[
            EdgeKey(
                source_path="doc.sec_1",
                target_path="doc.old_target",
                relation_type="REFERENCES",
            )
        ],
        reason="Batch curation task 42",
        actor="AGENT",
    )

    assert isinstance(result, CurateEdgesResult)
    # 2 leaf edges added due to container fan-out
    assert len(result.added) == 2
    assert result.added[0].source_path == "doc.sec_1"
    assert result.added[0].target_path in ("doc.sec_container.child_a", "doc.sec_container.child_b")
    assert result.added[0].relation_type == "REFERENCES"

    # 1 edge removed
    assert len(result.removed) == 1
    assert result.removed[0].source_path == "doc.sec_1"
    assert result.removed[0].target_path == "doc.old_target"

    # Verified DB interactions
    mock_repo.graph.insert_edges_atomic.assert_awaited_once()
