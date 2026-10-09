from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from rag_eval.exceptions import (
    E_CORPUS_INTEGRITY_VIOLATION,
    CorpusDomainError,
)
from rag_eval.ingestion.parser.edges import LineageBreadcrumbAndEdgeExtractor
from rag_eval.ingestion.parser.normalizer import (
    DocumentNormalizer,
    NormalizedDocument,
    SupportedFormat,
)
from rag_eval.schemas import (
    ChunkEntity,
    ParsedChunkDraft,
    RelationType,
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

    # 3. Empty or all-special characters fallback
    assert sanitize_ltree_label("") == "node"
    assert sanitize_ltree_label("!!!@@@###$$$") == "node"


def test_leaf_disambiguation_does_not_leak_into_anchors() -> None:
    """Verifies SEC-INGEST-003: Disambiguated leaves (p_1, tbl_1, code_1) never register as anchors."""
    extractor = LineageBreadcrumbAndEdgeExtractor()
    chunks = [
        ParsedChunkDraft(
            path="doc.sec_1",
            verbatim_text="Section One Text",
            contextualized_text="Section One Text",
            start_line=1,
            end_line=2,
            metadata={"heading_raw": "Section One", "node_type": "SECTION"},
        ),
        ParsedChunkDraft(
            path="doc.sec_1.p_1",
            verbatim_text="Paragraph 1 with link to [Leaf](#p-1) and [Table](#tbl-1) and [Sec](#section-one)",
            contextualized_text="Paragraph 1",
            start_line=3,
            end_line=4,
            metadata={"node_type": "PARAGRAPH"},
        ),
        ParsedChunkDraft(
            path="doc.sec_1.tbl_1",
            verbatim_text="| Col1 | Col2 |\n|---|---|\n| Val1 | Val2 |",
            contextualized_text="Table 1",
            start_line=5,
            end_line=7,
            metadata={"node_type": "TABLE", "is_table": True},
        ),
    ]
    edges = extractor.extract_deterministic_edges(chunks, normalized=NormalizedDocument(
        format_type=SupportedFormat.MARKDOWN,
        raw_text="",
        total_lines=7,
    ))

    # Should only create 1 edge pointing to doc.sec_1 (section-one)
    # Zero edges to p-1 or tbl-1!
    assert len(edges) == 1
    assert edges[0].source_path == "doc.sec_1.p_1"
    assert edges[0].target_path == "doc.sec_1"
    assert edges[0].relation_type == RelationType.REFERENCES


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


def test_pdf_empty_text_and_corrupt_rejection(tmp_path: Path) -> None:
    """Verifies SEC-INGEST-008 & DEF-INGEST-007: DocumentNormalizer rejects empty/corrupt files with domain error."""
    normalizer = DocumentNormalizer()
    empty_pdf = tmp_path / "empty.pdf"
    empty_pdf.write_bytes(b"%PDF-1.4\n%%EOF")

    with pytest.raises(CorpusDomainError) as exc_info:
        normalizer.normalize_file(empty_pdf)
    assert exc_info.value.error_code == E_CORPUS_INTEGRITY_VIOLATION

    with pytest.raises(CorpusDomainError) as exc_info_text:
        normalizer.normalize_text("   \n\n  \t  ")
    assert exc_info_text.value.error_code == E_CORPUS_INTEGRITY_VIOLATION


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
        GraphEdgeEntity(source_chunk_id=c1, target_chunk_id=c2, relation_type="REFERENCES"),
        GraphEdgeEntity(source_chunk_id=c1, target_chunk_id=c2, relation_type="REFERENCES"),
    ]
    res = await repo.upsert_edges(edges)
    assert res == {}
    mock_conn.fetch.assert_awaited_once()
    args = mock_conn.fetch.call_args[0]
    # Parameter 4 is the relations list
    assert args[4] == ["REFERENCES"]

