from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from rag_eval.cli import app
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
    ChunkReviewStatus,
    RelationType,
    StagingChunk,
    StagingChunkDelta,
    StagingEdge,
    StagingStatus,
)
from rag_eval.ingestion.staging.operations import apply_chunk_deltas_to_session
from rag_eval.ingestion.staging.session import StagingDocumentSession
from rag_eval.ingestion.wal import GenesisSnapshot, WALSessionStore
from rag_eval.mcp.tools import CorpusMCPTools
from rag_eval.mcp.tools.staging import CorpusStagingTools
from rag_eval.schemas import sanitize_ltree_label
from rag_eval.web.services.promotion import HumanPromotionEngine
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


def test_staging_manager_lifecycle_status_enforcement(tmp_path: Path) -> None:
    """Verifies that patch_chunks and add_edges reject non-DRAFT/AMENDMENT sessions."""
    manager = StagingManager(staging_dir=tmp_path)
    session = manager.create_session_from_raw(
        doc_slug="doc_lifecycle",
        title="Test Lifecycle",
        raw_text="# Title\n\nContent paragraph.",
    )

    # Transition session to AGENT_COMMITTED
    paths = [c.path for c in session.chunks]
    manager.finalize_chunks(doc_slug="doc_lifecycle", paths=paths)
    manager.update_session_status(
        doc_slug="doc_lifecycle",
        status=StagingStatus.AGENT_COMMITTED,
        actor="TEST",
        description="Committed by agent",
    )

    # 1. patch_chunks must raise CorpusDomainError
    with pytest.raises(CorpusDomainError) as exc_patch:
        manager.patch_chunks(
            doc_slug="doc_lifecycle",
            updated_chunks=[StagingChunkDelta(path=paths[0], verbatim_text="New text")],
        )
    assert "Không thể chỉnh sửa phiên staging" in exc_patch.value.message

    # 2. add_edges must raise CorpusDomainError
    with pytest.raises(CorpusDomainError) as exc_edge:
        manager.add_edges(
            doc_slug="doc_lifecycle",
            edges=[
                StagingEdge(
                    source_path=paths[0],
                    target_path="doc_lifecycle.target",
                    relation_type=RelationType.REFERENCES,
                )
            ],
        )
    assert "Không thể chỉnh sửa phiên staging" in exc_edge.value.message


@pytest.mark.asyncio
async def test_stg_validate_mcp_tool(tmp_path: Path) -> None:
    """Verifies that stg_validate executes PreFlightValidator and returns the validation report."""
    manager = StagingManager(staging_dir=tmp_path)
    manager.create_session_from_raw(
        doc_slug="valid_doc",
        title="Valid Document",
        raw_text="# Section One\n\nParagraph text here.",
    )

    staging_tools = CorpusStagingTools(staging_manager=manager)
    report = await staging_tools.stg_validate(doc_slug="valid_doc")

    assert isinstance(report, dict)
    assert "status" in report
    assert "passed" in report
    assert "issues" in report
    assert "summary" in report
    assert report["total_checks"] == 8

    # Also check delegation on CorpusMCPTools
    mcp_tools = CorpusMCPTools(sensors=MagicMock(), staging=staging_tools)
    mcp_report = await mcp_tools.stg_validate(doc_slug="valid_doc")
    assert mcp_report["status"] == report["status"]


def test_cli_promote_force_option(tmp_path: Path) -> None:
    """Verifies that cli promote --force automatically finalizes unreviewed chunks and approves draft sessions."""
    manager = StagingManager(staging_dir=tmp_path)
    session = manager.create_session_from_raw(
        doc_slug="cli_force_doc",
        title="CLI Force Document",
        raw_text="# Header\n\nVerbatim paragraph.",
    )
    assert session.status == StagingStatus.DRAFT
    assert any(c.review_status == ChunkReviewStatus.PENDING for c in session.chunks)

    runner = CliRunner()
    mock_instance = MagicMock()
    mock_res = MagicMock(chunks_promoted=len(session.chunks), edges_promoted=0)
    mock_instance.promote_session = AsyncMock(return_value=mock_res)

    with (
        patch("rag_eval.ingestion.staging.StagingManager", return_value=manager),
        patch("rag_eval.web.services.HumanPromotionEngine", return_value=mock_instance),
        patch("rag_eval.cli._prune_stale_chunks", new_callable=AsyncMock) as mock_prune,
        patch("rag_eval.cli._rebuild_indexes", new_callable=AsyncMock),
    ):
        mock_prune.return_value = 0
        result = runner.invoke(app, ["promote", "--force", "--no-embed"])

    assert result.exit_code == 0
    assert "Promoted 1 documents" in result.output

    # Verify session was updated to APPROVED and chunks finalized
    updated_session = manager.load_session("cli_force_doc")
    assert updated_session.status == StagingStatus.APPROVED
    for c in updated_session.chunks:
        assert c.review_status == ChunkReviewStatus.REVIEWED


@pytest.mark.asyncio
async def test_promotion_persists_context_refs_and_warns_unlinked_edges(tmp_path: Path) -> None:
    """Verifies SEC-INGEST-001 and SEC-INGEST-005: batch_create_refs is invoked and unlinked edges warn."""
    manager = StagingManager(staging_dir=tmp_path)
    session = manager.create_session_from_raw(
        doc_slug="promo_doc",
        title="Promotion Document",
        raw_text="# Section 1\n\nParagraph 1.\n\n# Section 2\n\nParagraph 2 text.",
    )
    # Add an edge between chunk 1 and 2, and an unlinked external edge while in DRAFT
    manager.add_edges(
        "promo_doc",
        edges=[
            StagingEdge(
                source_path=session.chunks[1].path,
                target_path=session.chunks[0].path,
                relation_type=RelationType.REFERENCES,
            ),
            StagingEdge(
                source_path=session.chunks[1].path,
                target_path="external_doc.sec_99",
                relation_type=RelationType.REFERENCES,
            ),
        ],
        actor="TEST",
    )

    # Finalize all chunks and approve session so promotion passes review gate
    paths = [c.path for c in session.chunks]
    manager.finalize_chunks("promo_doc", paths=paths, actor="TEST")
    session = manager.update_session_status(
        "promo_doc",
        StagingStatus.APPROVED,
        actor="TEST",
        description="Approved for test promotion",
    )

    mock_pool = MagicMock()
    mock_conn = MagicMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
    mock_pool.acquire.return_value.__aexit__.return_value = None
    mock_conn.transaction.return_value.__aenter__.return_value = None
    mock_conn.transaction.return_value.__aexit__.return_value = None
    mock_conn.execute = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=[])

    mock_loader = MagicMock()
    mock_doc_id = uuid.uuid4()
    mock_loader.load_document = AsyncMock(return_value=mock_doc_id)
    chunk_map: dict[str, uuid.UUID] = {}

    async def fake_load_chunks(chunks: list[object], conn: object = None) -> dict[str, uuid.UUID]:
        for c in chunks:
            p = getattr(c, "path", "")
            if p and p not in chunk_map:
                chunk_map[p] = uuid.uuid4()
        return chunk_map

    mock_loader.load_chunks = AsyncMock(side_effect=fake_load_chunks)
    mock_loader.resolve_chunk_paths = AsyncMock(return_value={})
    edge_persisted_id = uuid.uuid4()

    async def fake_load_edges(edges: list[object], conn: object = None) -> dict[tuple[uuid.UUID, uuid.UUID, str], uuid.UUID]:
        result = {}
        for e in edges:
            src = getattr(e, "source_chunk_id", None)
            tgt = getattr(e, "target_chunk_id", None)
            rel = getattr(e, "relation_type", "")
            if src and tgt:
                result[(src, tgt, rel)] = edge_persisted_id
        return result

    mock_loader.load_graph_edges = AsyncMock(side_effect=fake_load_edges)
    mock_loader.corpus_repo.context_refs.batch_create_refs = AsyncMock(return_value=1)
    mock_loader.corpus_repo.graph.delete_edges_for_chunks = AsyncMock(return_value=0)
    mock_loader.corpus_repo.graph.delete_outgoing_edges_for_chunks = AsyncMock(return_value=0)

    engine = HumanPromotionEngine(staging_manager=manager)
    with patch("rag_eval.web.services.promotion.PostgresBulkLoader", return_value=mock_loader):
        res = await engine.promote_session(doc_slug="promo_doc", pool=mock_pool, compute_embeddings=False)

    assert res.status == "SUCCESS"
    # Verify batch_create_refs was called with persisted refs!
    mock_loader.corpus_repo.context_refs.batch_create_refs.assert_awaited_once()
    called_refs = mock_loader.corpus_repo.context_refs.batch_create_refs.call_args[0][0]
    assert len(called_refs) == 2
    assert called_refs[0].chunk_id == chunk_map[session.chunks[1].path]
    assert called_refs[0].target_chunk_id == chunk_map[session.chunks[0].path]
    assert called_refs[0].edge_id == edge_persisted_id
    assert called_refs[1].target_path == "external_doc.sec_99"
    assert called_refs[1].target_chunk_id is None
    assert called_refs[1].edge_id is None


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


@pytest.mark.asyncio
async def test_mcp_stg_commit_sanitized_slug_validation(tmp_path: Path) -> None:
    """Verifies SEC-INGEST-004: stg_commit normalizes doc_slug before checking intra-doc edge targets."""
    manager = StagingManager(staging_dir=tmp_path)
    session = manager.create_session_from_raw(
        doc_slug="Doc-Slug-01",
        title="Sanitized Doc",
        raw_text="# Heading 1\n\nContent paragraph 1.\n\n# Heading 2\n\nContent paragraph 2.",
    )
    paths = [c.path for c in session.chunks]
    manager.finalize_chunks("Doc-Slug-01", paths=paths, actor="AGENT")

    # Add edge targeting valid internal chunk (from chunk 1 to chunk 0)
    manager.add_edges(
        "Doc-Slug-01",
        edges=[
            StagingEdge(
                source_path=session.chunks[1].path,
                target_path=session.chunks[0].path,
                relation_type=RelationType.REFERENCES,
            )
        ],
        actor="AGENT",
    )

    staging_tools = CorpusStagingTools(staging_manager=manager)
    res = await staging_tools.stg_commit("Doc-Slug-01")
    assert res.status == StagingStatus.AGENT_COMMITTED.value

    # 2. Verify stg_commit boundary check catches invalid intra-document edge targets
    session_test = manager.load_session("Doc-Slug-01")
    session_test.status = StagingStatus.DRAFT
    session_test.edges.append(
        StagingEdge(
            source_path=session_test.chunks[1].path,
            target_path="doc_slug_01.sec_999",
            relation_type=RelationType.REFERENCES,
        )
    )
    with patch.object(staging_tools, "_ensure_session", AsyncMock(return_value=session_test)):
        with pytest.raises(CorpusDomainError) as exc_info:
            await staging_tools.stg_commit("Doc-Slug-01")
        assert "Invalid edge target path" in str(exc_info.value.message)


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
async def test_re_promotion_prunes_context_refs_and_outgoing_edges(tmp_path: Path) -> None:
    """Verifies DEF-INGEST-010 & DEF-INGEST-011: Re-promotion deletes outgoing edges and context refs before load_chunks."""
    manager = StagingManager(staging_dir=tmp_path)
    session = manager.create_session_from_raw(
        doc_slug="re_promo_doc",
        title="Re Promotion Doc",
        raw_text="# Sec 1\n\nText 1",
    )
    paths = [c.path for c in session.chunks]
    manager.finalize_chunks("re_promo_doc", paths=paths, actor="TEST")
    manager.update_session_status(
        "re_promo_doc",
        StagingStatus.APPROVED,
        actor="TEST",
        description="Approved for test promotion",
    )

    mock_pool = MagicMock()
    mock_conn = MagicMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
    mock_pool.acquire.return_value.__aexit__.return_value = None
    mock_conn.transaction.return_value.__aenter__.return_value = None
    mock_conn.transaction.return_value.__aexit__.return_value = None
    mock_conn.execute = AsyncMock()
    old_chunk_id = uuid.uuid4()
    mock_conn.fetch = AsyncMock(return_value=[{"id": old_chunk_id}])

    mock_loader = MagicMock()
    mock_loader.load_document = AsyncMock(return_value=uuid.uuid4())
    mock_loader.load_chunks = AsyncMock(return_value={"re_promo_doc.sec_1.p": old_chunk_id})
    mock_loader.resolve_chunk_paths = AsyncMock(return_value={})
    mock_loader.load_graph_edges = AsyncMock(return_value={})
    mock_loader.corpus_repo.context_refs.batch_create_refs = AsyncMock(return_value=0)
    mock_loader.corpus_repo.graph.delete_outgoing_edges_for_chunks = AsyncMock(return_value=1)

    engine = HumanPromotionEngine(staging_manager=manager)
    with patch("rag_eval.web.services.promotion.PostgresBulkLoader", return_value=mock_loader):
        res = await engine.promote_session(doc_slug="re_promo_doc", pool=mock_pool, compute_embeddings=False)

    assert res.status == "SUCCESS"
    mock_loader.corpus_repo.graph.delete_outgoing_edges_for_chunks.assert_awaited_once_with([old_chunk_id], conn=mock_conn)


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


