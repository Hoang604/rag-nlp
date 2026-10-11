from __future__ import annotations

import re
import uuid

import pytest

from rag_eval.schemas import (
    ChunkEntity,
    sanitize_ltree_label,
)
from rag_eval.web.services.tree import TreeHierarchyBuilder


def test_sanitize_ltree_label_vietnamese_and_bounds() -> None:
    """Verifies Vietnamese transliteration, accent removal, character bounding, and sanitization."""
    # 1. Vietnamese diacritics transliteration
    assert sanitize_ltree_label("Đặc tả") == "dac_ta"
    assert sanitize_ltree_label("ĐẶC TẢ HỆ THỐNG") == "dac_ta_he_thong"
    assert sanitize_ltree_label("cơ sở dữ liệu") == "co_so_du_lieu"
    assert sanitize_ltree_label("ứng dụng đa phân tán") == "ung_dung_da_phan_tan"

    # 2. Length bounding to 250 characters
    long_input = "muc_" + ("a" * 300)
    sanitized = sanitize_ltree_label(long_input)
    assert len(sanitized) <= 250
    assert len(sanitized) == 250
    assert not sanitized.endswith("_")

    # 3. Empty or all-special characters raises ValueError (no fake fallback)
    with pytest.raises(ValueError):
        sanitize_ltree_label("")
    with pytest.raises(ValueError):
        sanitize_ltree_label("!!!@@@###$$$")

    # 4. Non-Latin Unicode scripts produce deterministic ASCII hash fallback
    cjk_label = sanitize_ltree_label("概要")
    assert cjk_label.startswith("u_")
    assert len(cjk_label) == 14  # 'u_' + 12 hex chars
    assert re.match(r"^u_[0-9a-f]{12}$", cjk_label)
    assert sanitize_ltree_label("概要") == cjk_label

    cyrillic_label = sanitize_ltree_label("документация")
    assert cyrillic_label.startswith("u_")


def test_tree_hierarchy_builder_ast_node_types_and_labels() -> None:
    """Verifies SEC-INGEST-006: TreeHierarchyBuilder sets accurate node_type and human-readable label."""
    doc_id = uuid.uuid4()
    chunks = [
        ChunkEntity(
            id=uuid.uuid4(),
            document_id=doc_id,
            path="tree_ast_doc.sec_1",
            verbatim_text="# Section Alpha",
            contextualized_text="# Section Alpha",
            start_line=1,
            end_line=1,
            metadata={"heading_raw": "Section Alpha", "node_type": "SECTION"},
        ),
        ChunkEntity(
            id=uuid.uuid4(),
            document_id=doc_id,
            path="tree_ast_doc.sec_1.p_1",
            verbatim_text="Paragraph text.",
            contextualized_text="[Section Alpha] Paragraph text.",
            start_line=2,
            end_line=2,
            metadata={"node_type": "PARAGRAPH"},
        ),
        ChunkEntity(
            id=uuid.uuid4(),
            document_id=doc_id,
            path="tree_ast_doc.sec_1.tbl_1",
            verbatim_text="| H1 | H2 |\n|---|---|\n| A | B |",
            contextualized_text="[Section Alpha] Table",
            start_line=3,
            end_line=5,
            metadata={"node_type": "TABLE", "is_table": True},
        ),
    ]

    builder = TreeHierarchyBuilder()
    tree = builder.build_tree(doc_slug="tree_ast_doc", title="Tree AST Doc", chunks=chunks)
    assert tree.root.node_type == "DOCUMENT"
    assert len(tree.root.children) > 0

    all_nodes = []
    def _collect(n):
        all_nodes.append(n)
        for child in n.children:
            _collect(child)
    _collect(tree.root)

    node_types = {n.node_type for n in all_nodes}
    assert "DOCUMENT" in node_types
    assert ("PARAGRAPH" in node_types or "SECTION" in node_types)
    headings = [n.label for n in all_nodes if "Alpha" in n.label]
    assert len(headings) >= 1



@pytest.mark.asyncio
async def test_upsert_edges_string_relations_deduplication() -> None:
    """Verifies that GraphRepository.upsert_edges deduplicates and unrolls string relation types without duck-typing."""
    from unittest.mock import AsyncMock, MagicMock

    from rag_eval.db.repositories.graph import GraphRepository
    from rag_eval.schemas import GraphEdgeEntity

    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=[])
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

    repo = GraphRepository(pool=mock_pool)
    repo.get_valid_relation_codes = AsyncMock(return_value={"REFERENCES", "EXTENDS"})

    c1, c2 = uuid.uuid4(), uuid.uuid4()
    edges = [
        GraphEdgeEntity(
            source_chunk_id=c1,
            target_chunk_id=c2,
            relation_type="REFERENCES",
            citation_text="Valid citation.",
        ),
        GraphEdgeEntity(
            source_chunk_id=c1,
            target_chunk_id=c2,
            relation_type="REFERENCES",
            citation_text="Valid citation.",
        ),
    ]
    res = await repo.upsert_edges(edges)
    assert res == {}
    mock_conn.fetch.assert_awaited_once()
    args = mock_conn.fetch.call_args[0]
    # Check relations list without relying on exact positional argument index
    assert any(isinstance(a, list) and set(a) == {"REFERENCES"} for a in args)


@pytest.mark.asyncio
async def test_verbatim_grep_order_by_reading_order() -> None:
    """Verifies that RetrievalEngine forwards order_by_reading_order to VerbatimGrepQuery."""
    from unittest.mock import AsyncMock, MagicMock, patch

    from rag_eval.retrieval.engine import RetrievalEngine
    from rag_eval.schemas import VerbatimGrepQuery

    mock_pool = MagicMock()
    engine = RetrievalEngine(pool=mock_pool)
    with patch("rag_eval.retrieval.engine.CorpusRepository") as mock_repo_cls:
        mock_repo = MagicMock()
        mock_repo.chunks.hybrid_search = AsyncMock(return_value=[])
        mock_repo.chunks.verbatim_grep = AsyncMock(return_value=([], 0))
        mock_repo_cls.return_value = mock_repo

        await engine.search_venn(
            query="test",
            pattern="SETTINGS",
            order_by_reading_order=True,
        )
        called_dto: VerbatimGrepQuery = mock_repo.chunks.verbatim_grep.call_args[0][0]
        assert called_dto.order_by_reading_order is True


