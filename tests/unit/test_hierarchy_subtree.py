import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from rag_eval.mcp.tools.sensors import CorpusRuntimeSensors
from rag_eval.schemas import ChunkEntity, HierarchicalDirection


@pytest.mark.asyncio
async def test_corpus_sensors_hierarchical_navigate_subtree() -> None:
    """Verifies that CorpusRuntimeSensors.hierarchical_navigate dispatches SUBTREE cleanly."""
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

    from rag_eval.schemas import HierarchyNodeDTO

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
    )

    assert result.anchor_path == "spec_system.sec_1"
    assert result.direction == "SUBTREE"
    assert result.total_nodes == 1
    assert len(result.nodes) == 1

    node = result.nodes[0]
    assert node.path == "spec_system.sec_1.sub_a"
    assert node.text == "Descendant provision content."
    assert node.context == "spec_system > sec_1"
    assert node.start_line == 10
    assert node.end_line == 25
