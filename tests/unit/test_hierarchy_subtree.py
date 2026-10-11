import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from rag_eval.mcp.tools.sensors import CorpusRuntimeSensors
from rag_eval.schemas import (
    ChunkEntity,
    DocumentEntity,
    HierarchicalDirection,
    HierarchyNodeDTO,
    UnifiedHierarchyResult,
)


@pytest.mark.asyncio
async def test_corpus_sensors_hierarchical_navigate_subtree() -> None:
    """Verifies that CorpusRuntimeSensors.hierarchical_navigate dispatches SUBTREE cleanly and emits factored groups."""
    mock_pool = MagicMock()
    sensors = CorpusRuntimeSensors(pool=mock_pool)

    doc_id = uuid.uuid4()
    anchor_chunk = ChunkEntity(
        id=uuid.uuid4(),
        document_id=doc_id,
        path="spec_system.sec_1",
        verbatim_text="Section container text.",
        contextualized_text="[spec_system]\nSection container text.",
        start_line=1,
        end_line=9,
    )

    mock_repo = MagicMock()
    mock_repo.chunks.get_by_path = AsyncMock(return_value=anchor_chunk)
    mock_repo.documents.get_by_id = AsyncMock(
        return_value=DocumentEntity(
            id=doc_id,
            doc_slug="spec_system",
            title="Spec System Doc",
        )
    )

    child_node = HierarchyNodeDTO(
        chunk_id=uuid.uuid4(),
        path="spec_system.sec_1.sub_a",
        doc_slug="spec_system",
        start_line=10,
        end_line=25,
        verbatim_text="Descendant provision content.",
        contextualized_text="[spec_system > sec_1]\nDescendant provision content.",
        metadata={"node_type": "SUBSECTION"},
        relative_depth=1,
    )
    mock_repo.chunks.navigate_hierarchy = AsyncMock(return_value=[child_node])

    sensors._get_repo = AsyncMock(return_value=mock_repo)

    result = await sensors.hierarchical_navigate(
        path="spec_system.sec_1",
        direction=HierarchicalDirection.SUBTREE,
        limit=15,
    )

    assert isinstance(result, UnifiedHierarchyResult)
    assert result.anchor_path == "spec_system.sec_1"
    assert result.direction == HierarchicalDirection.SUBTREE
    assert result.total == 1
    assert result.truncated is False
    assert "spec_system" in result.documents
    assert result.documents["spec_system"].title == "Spec System Doc"

    assert len(result.groups) == 1
    group = result.groups[0]
    assert group.doc_slug == "spec_system"
    assert group.context == "spec_system > sec_1"
    assert len(group.provisions) == 1

    prov = group.provisions[0]
    assert prov.path == "spec_system.sec_1.sub_a"
    assert prov.text == "Descendant provision content."
    assert prov.start_line == 10
    assert prov.end_line == 25
