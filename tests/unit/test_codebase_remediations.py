from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

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
from rag_eval.ingestion.staging.manager import StagingManager
from rag_eval.ingestion.staging.models import (
    ContextType,
    StagingChunk,
    StagingChunkDelta,
    StagingStatus,
)
from rag_eval.ingestion.staging.operations import apply_chunk_deltas_to_session
from rag_eval.ingestion.staging.session import StagingDocumentSession
from rag_eval.ingestion.wal import GenesisSnapshot, WALSessionStore
from rag_eval.schemas import sanitize_ltree_label
from rag_eval.web.services.tree import TreeHierarchyBuilder
from rag_eval.web.services.validation import PreFlightValidator


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


def test_normalize_bytes_extensionless_deduction() -> None:
    """Verifies that extensionless uploads deduce file suffix from fmt to trigger the correct parser."""
    normalizer = DocumentNormalizer()

    # Synthetic text payload with markdown
    md_content = b"# Document Header\n\nContent paragraph.\n"
    doc_md = normalizer.normalize_bytes(
        content=md_content, file_name="blob_without_extension", mime_type="text/markdown"
    )
    assert doc_md.format_type == SupportedFormat.MARKDOWN
    assert doc_md.metadata.get("original_filename") == "blob_without_extension"

    # Synthetic mock for PDF branch: when suffix is empty, it chooses .pdf
    with patch.object(normalizer, "normalize_file") as mock_norm_file:
        mock_norm_file.return_value = NormalizedDocument(
            format_type=SupportedFormat.PDF,
            raw_text="mock pdf text",
            total_lines=1,
            tables=[],
            metadata={},
        )
        pdf_bytes = b"%PDF-1.4 mock content"
        doc_pdf = normalizer.normalize_bytes(
            content=pdf_bytes, file_name="raw_upload_stream", mime_type="application/pdf"
        )
        assert mock_norm_file.called
        called_path = mock_norm_file.call_args[0][0]
        assert str(called_path).endswith(".pdf")
        assert doc_pdf.metadata.get("original_filename") == "raw_upload_stream"

    # Synthetic mock for DOCX branch: when suffix is empty, it chooses .docx
    with patch.object(normalizer, "normalize_file") as mock_norm_file:
        mock_norm_file.return_value = NormalizedDocument(
            format_type=SupportedFormat.DOCX,
            raw_text="mock docx text",
            total_lines=1,
            tables=[],
            metadata={},
        )
        docx_bytes = b"mock docx bytes"
        doc_docx = normalizer.normalize_bytes(
            content=docx_bytes,
            file_name="word_stream",
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        assert mock_norm_file.called
        called_path = mock_norm_file.call_args[0][0]
        assert str(called_path).endswith(".docx")
        assert doc_docx.metadata.get("original_filename") == "word_stream"


def test_apply_chunk_deltas_breadcrumb_cascading() -> None:
    """Verifies that updating a chunk with cascade_breadcrumbs=True recalculates descendant breadcrumbs."""
    session = StagingDocumentSession(
        doc_slug="test_doc",
        title="Document Title",
        raw_text="Sample text",
        status=StagingStatus.DRAFT,
        chunks=[
            StagingChunk(
                path="test_doc.sec_1",
                verbatim_text="# Chuong 1: Tong Quan",
                contextualized_text="# Chuong 1: Tong Quan",
                start_line=1,
                end_line=1,
                metadata={"heading_raw": "Chuong 1: Tong Quan"},
            ),
            StagingChunk(
                path="test_doc.sec_1.part_a",
                verbatim_text="Noi dung chi tiet part A.",
                contextualized_text="[Chuong 1: Tong Quan]\nNoi dung chi tiet part A.",
                start_line=2,
                end_line=3,
                metadata={"ancestor_titles": ["Chuong 1: Tong Quan"]},
            ),
            StagingChunk(
                path="test_doc.sec_1.part_b",
                verbatim_text="Noi dung chi tiet part B.",
                contextualized_text="[Chuong 1: Tong Quan]\nNoi dung chi tiet part B.",
                start_line=4,
                end_line=5,
                metadata={"ancestor_titles": ["Chuong 1: Tong Quan"]},
            ),
            StagingChunk(
                path="test_doc.sec_2",
                verbatim_text="# Chuong 2: Kien Truc",
                contextualized_text="# Chuong 2: Kien Truc",
                start_line=6,
                end_line=6,
                metadata={"heading_raw": "Chuong 2: Kien Truc"},
            ),
        ],
    )

    # Patch sec_1 title
    delta = StagingChunkDelta(
        path="test_doc.sec_1",
        verbatim_text="# Chuong 1: Tong Quan He Thong Mo Rong",
        metadata={"heading_raw": "Chuong 1: Tong Quan He Thong Mo Rong"},
    )

    report = apply_chunk_deltas_to_session(
        session=session,
        deltas=[delta],
        cascade_breadcrumbs=True,
    )

    assert report.updated_count == 1
    assert report.cascaded_count == 2

    # Descendants must have updated breadcrumb prefixes
    part_a = session.get_chunk("test_doc.sec_1.part_a")
    assert part_a is not None
    assert part_a.contextualized_text.startswith("[Chuong 1: Tong Quan He Thong Mo Rong]\n")
    assert part_a.metadata.get("ancestor_titles") == ["Chuong 1: Tong Quan He Thong Mo Rong"]

    part_b = session.get_chunk("test_doc.sec_1.part_b")
    assert part_b is not None
    assert part_b.contextualized_text.startswith("[Chuong 1: Tong Quan He Thong Mo Rong]\n")
    assert part_b.metadata.get("ancestor_titles") == ["Chuong 1: Tong Quan He Thong Mo Rong"]

    # sec_2 is unaffected
    sec_2 = session.get_chunk("test_doc.sec_2")
    assert sec_2 is not None
    assert sec_2.contextualized_text == "# Chuong 2: Kien Truc"


def test_preflight_validator_coordinate_continuity_rule_4(tmp_path: Path) -> None:
    """Verifies SEC-INGEST-002: Rule 4 COORDINATE_CONTINUITY validates start_line and end_line bounds."""
    manager = StagingManager(staging_dir=tmp_path)
    session = manager.create_session_from_raw(
        doc_slug="coord_doc",
        title="Coordinate Doc",
        raw_text="# Title\n\nLine 1\nLine 2",
    )
    validator = PreFlightValidator()
    report = validator.validate(session)
    assert report.total_checks == 8
    coord_summary = report.summary.get("coordinate_continuity")
    assert isinstance(coord_summary, dict)
    assert coord_summary["passed"] is True

    # Corrupt coordinates on a chunk
    session.chunks[0].start_line = 0
    report_fail = validator.validate(session)
    fail_summary = report_fail.summary.get("coordinate_continuity")
    assert isinstance(fail_summary, dict)
    assert fail_summary["passed"] is False
    assert any(i.rule == "COORDINATE_CONTINUITY" for i in report_fail.issues)

    session.chunks[0].start_line = 10
    session.chunks[0].end_line = 5
    report_fail2 = validator.validate(session)
    fail2_summary = report_fail2.summary.get("coordinate_continuity")
    assert isinstance(fail2_summary, dict)
    assert fail2_summary["passed"] is False


def test_leaf_disambiguation_does_not_leak_into_anchors() -> None:
    """Verifies SEC-INGEST-003: Disambiguated leaves (p_1, tbl_1, code_1) never register as anchors."""
    extractor = LineageBreadcrumbAndEdgeExtractor()
    chunks = [
        StagingChunk(
            path="doc.sec_1",
            verbatim_text="Section One Text",
            contextualized_text="Section One Text",
            start_line=1,
            end_line=2,
            metadata={"heading_raw": "Section One", "node_type": "SECTION"},
        ),
        StagingChunk(
            path="doc.sec_1.p_1",
            verbatim_text="Paragraph 1 with link to [Leaf](#p-1) and [Table](#tbl-1) and [Sec](#section-one)",
            contextualized_text="Paragraph 1",
            start_line=3,
            end_line=4,
            metadata={"node_type": "PARAGRAPH"},
        ),
        StagingChunk(
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


def test_tree_hierarchy_builder_ast_node_types_and_labels(tmp_path: Path) -> None:
    """Verifies SEC-INGEST-006: TreeHierarchyBuilder sets accurate node_type and human-readable label."""
    manager = StagingManager(staging_dir=tmp_path)
    session = manager.create_session_from_raw(
        doc_slug="tree_ast_doc",
        title="Tree AST Doc",
        raw_text="# Section Alpha\n\nParagraph text.\n\n| H1 | H2 |\n|---|---|\n| A | B |",
    )
    builder = TreeHierarchyBuilder()
    tree = builder.build_tree(session)
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
    # Check that labels are not raw segments like 'sec_1' where heading exists
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
async def test_hydrate_session_from_db_preserves_unresolved_external_refs(tmp_path: Path) -> None:
    """Verifies DEF-INGEST-012: Hydrating a session from DB queries chunk_context_refs for unresolved external dependencies."""
    manager = StagingManager(staging_dir=tmp_path)
    mock_pool = MagicMock()
    mock_conn = MagicMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
    mock_pool.acquire.return_value.__aexit__.return_value = None

    mock_doc = MagicMock()
    mock_doc.id = uuid.uuid4()
    mock_doc.title = "Hydrated Doc"
    mock_doc.metadata = {}
    mock_doc.raw_text = "Doc text"

    chunk_id = uuid.uuid4()
    mock_chunk = MagicMock()
    mock_chunk.id = chunk_id
    mock_chunk.path = "hydrated_doc.sec_1"
    mock_chunk.verbatim_text = "Verbatim"
    mock_chunk.contextualized_text = "Contextualized"
    mock_chunk.start_line = 1
    mock_chunk.end_line = 1
    mock_chunk.metadata = {}
    mock_chunk.context_type = "REQUIRES_EXTERNAL_CONTEXT"
    mock_chunk.is_all_refs_resolved = False

    mock_corpus = MagicMock()
    mock_corpus.documents.get_by_slug = AsyncMock(return_value=mock_doc)
    mock_corpus.chunks.list_by_document = AsyncMock(return_value=[mock_chunk])
    mock_corpus.graph.list_edges_for_chunks = AsyncMock(return_value=[])
    mock_corpus.chunks.resolve_ids_batch = AsyncMock(return_value={})

    mock_conn.fetch = AsyncMock(
        return_value=[{"source_path": "hydrated_doc.sec_1", "target_path": "other_doc.sec_5"}]
    )

    with patch("rag_eval.db.repositories.CorpusRepository", return_value=mock_corpus):
        session = await manager.hydrate_session_from_db("hydrated_doc", pool=mock_pool)

    assert len(session.edges) == 1
    assert session.edges[0].source_path == "hydrated_doc.sec_1"
    assert session.edges[0].target_path == "other_doc.sec_5"
    assert session.chunks[0].context_type == ContextType.REQUIRES_EXTERNAL_CONTEXT


def test_wal_init_genesis_lock_and_exists_guard(tmp_path: Path) -> None:
    """Verifies DEF-INGEST-014: exists() checks either genesis or wal, and init_genesis refuses to clobber existing session."""
    store = WALSessionStore(session_dir=tmp_path / "wal_guard_doc")
    assert store.exists() is False

    genesis = GenesisSnapshot(
        doc_slug="wal_guard_doc",
        title="WAL Guard Doc",
        raw_text="Sample text",
        genesis_hash="abc123hash",
        initial_chunks=[],
        initial_edges=[],
    )
    store.init_genesis(genesis)
    assert store.exists() is True

    # Attempting to re-init genesis must raise integrity violation
    with pytest.raises(CorpusDomainError) as exc_info:
        store.init_genesis(genesis)
    assert exc_info.value.error_code == E_CORPUS_INTEGRITY_VIOLATION


def test_wal_large_record_get_head_lsn(tmp_path: Path) -> None:
    """Verifies DEF-INGEST-016: get_head_lsn parses WAL lines exceeding 4096 bytes without truncation."""
    store = WALSessionStore(session_dir=tmp_path / "wal_large_doc")
    genesis = GenesisSnapshot(
        doc_slug="wal_large_doc",
        title="WAL Large Doc",
        raw_text="Sample text",
        genesis_hash="abc",
        initial_chunks=[],
        initial_edges=[],
    )
    store.init_genesis(genesis)
    assert store.get_head_lsn() == 0

    large_payload = {
        "large_data": "x" * 12000,
        "items": list(range(100)),
    }
    rec, _ = store.append_record(
        actor="TEST",
        op_type="LARGE_OP",
        description="Testing large record parsing",
        payload=large_payload,
    )
    assert rec.lsn == 1
    assert store.get_head_lsn() == 1


