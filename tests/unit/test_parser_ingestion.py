from pathlib import Path

from rag_eval.ingestion.parser.chunker import HierarchicalASTSegmenter
from rag_eval.ingestion.parser.edges import LineageBreadcrumbAndEdgeExtractor
from rag_eval.ingestion.parser.engine import DocumentIngestionEngine
from rag_eval.ingestion.parser.normalizer import DocumentNormalizer, SupportedFormat
from rag_eval.ingestion.staging.manager import StagingManager
from rag_eval.ingestion.staging.models import RelationType
from rag_eval.schemas import validate_ltree_path


def test_document_normalizer_synthetic_mechanics() -> None:
    """Verifies that DocumentNormalizer converts synthetic Markdown into NormalizedDocument with intact line counts and tables."""
    normalizer = DocumentNormalizer()
    content = (
        "# Document Header\n"
        "\n"
        "Paragraph line one.\n"
        "Paragraph line two.\n"
        "\n"
        "| Col1 | Col2 |\n"
        "| --- | --- |\n"
        "| ValA | ValB |\n"
        "| ValC | ValD |\n"
        "\n"
        "Concluding line.\n"
    )

    doc = normalizer.normalize_text(content, SupportedFormat.MARKDOWN)
    assert doc.format_type == SupportedFormat.MARKDOWN
    assert doc.total_lines == 11
    assert len(doc.tables) == 1

    table = doc.tables[0]
    assert table.row_count == 2
    assert table.col_count == 2
    assert table.headers == ["Col1", "Col2"]
    assert table.start_line == 6
    assert table.end_line == 9


def test_ast_tree_decomposition_ltree_invariants() -> None:
    """Verifies that HierarchicalASTSegmenter constructs a valid ltree hierarchy adhering to PostgreSQL ltree constraints."""
    content = (
        "# System Architecture Specification\n"
        "\n"
        "System overview preamble text.\n"
        "\n"
        "## Subsystem Alpha\n"
        "\n"
        "Detailed mechanics for Subsystem Alpha.\n"
        "\n"
        "### Module One\n"
        "\n"
        "Technical invariants for Module One.\n"
        "\n"
        "## Subsystem Beta\n"
        "\n"
        "Detailed mechanics for Subsystem Beta.\n"
    )

    normalizer = DocumentNormalizer()
    norm_doc = normalizer.normalize_text(content)

    segmenter = HierarchicalASTSegmenter(max_chunk_chars=500)
    root = segmenter.parse_to_tree("sys_spec", norm_doc)

    assert root.path == "sys_spec"
    assert len(root.children) >= 1
    h1 = root.children[0]
    assert len(h1.children) >= 2

    leaf_nodes = segmenter.flatten_leaf_chunks(root)
    assert len(leaf_nodes) >= 3

    # Invariant: Every leaf path must satisfy PostgreSQL ltree syntax
    paths = set()
    for leaf in leaf_nodes:
        assert validate_ltree_path(leaf.path)
        assert leaf.path.startswith("sys_spec.")
        assert leaf.start_line >= 1
        assert leaf.end_line >= leaf.start_line
        assert leaf.end_line <= norm_doc.total_lines
        assert leaf.path not in paths
        paths.add(leaf.path)


def test_table_block_preservation_mechanics() -> None:
    """Verifies that table blocks are preserved whole without arbitrary paragraph fragmentation."""
    content = (
        "# Data Schema\n"
        "\n"
        "| Field | Type | Description |\n"
        "| --- | --- | --- |\n"
        "| id | uuid | Primary key identifier |\n"
        "| lsn | int8 | Log sequence monotonic counter |\n"
        "| payload | jsonb | Event payload data |\n"
        "\n"
        "Trailing notes following the table block.\n"
    )

    engine = DocumentIngestionEngine()
    chunks, _edges, _meta = engine.process_raw("schema_doc", "Data Schema", content)

    assert len(chunks) >= 1
    table_chunks = [c for c in chunks if c.metadata.get("is_table") is True]
    assert len(table_chunks) == 1

    tbl = table_chunks[0]
    assert tbl.metadata.get("row_count") == 3
    assert tbl.metadata.get("col_count") == 3
    assert tbl.metadata.get("headers") == ["Field", "Type", "Description"]
    assert "Primary key identifier" in tbl.verbatim_text
    assert "Log sequence monotonic counter" in tbl.verbatim_text


def test_100_percent_precision_deterministic_edges() -> None:
    """Verifies that edges are only established for 100% resolvable anchor targets, rejecting unresolved ones (zero false positives)."""
    content = (
        "# Root Overview\n"
        "\n"
        "See [Subsystem Beta Details](#subsystem-beta) for specifications.\n"
        "Also see [Invalid Anchor](#non-existent-section-target) which must be rejected.\n"
        "\n"
        "## Subsystem Beta\n"
        "\n"
        "This is the concrete implementation target of Subsystem Beta.\n"
    )

    engine = DocumentIngestionEngine()
    chunks, edges, _meta = engine.process_raw("edge_doc", "Root Overview", content)

    # Invariant: Must contain exactly 1 edge pointing to Subsystem Beta, and 0 hallucinated edges
    assert len(edges) == 1
    edge = edges[0]
    assert edge.relation_type == RelationType.REFERENCES.value
    assert "beta" in edge.target_path.lower()

    # Verify that target_path actually exists in chunks
    chunk_paths = {c.path for c in chunks}
    assert edge.target_path in chunk_paths
    assert edge.source_path in chunk_paths


def test_lineage_breadcrumb_contextualization() -> None:
    """Verifies that contextualized_text synthesizes the ancestral hierarchy while keeping verbatim_text pure."""
    content = (
        "# Architecture\n"
        "\n"
        "## Ingestion Pipeline\n"
        "\n"
        "### AST Normalizer\n"
        "\n"
        "AST Normalizer parses layout structures.\n"
    )

    normalizer = DocumentNormalizer()
    norm = normalizer.normalize_text(content)
    segmenter = HierarchicalASTSegmenter()
    root = segmenter.parse_to_tree("arch", norm)
    leaves = segmenter.flatten_leaf_chunks(root)

    extractor = LineageBreadcrumbAndEdgeExtractor()
    staging_chunks = extractor.synthesize_breadcrumbs(root, leaves)

    deepest = next(c for c in staging_chunks if "normalizer" in c.path.lower() and c.path.endswith(".p"))
    assert "AST Normalizer parses layout structures." == deepest.verbatim_text.strip()
    assert "[Architecture > Ingestion Pipeline > AST Normalizer]" in deepest.contextualized_text


def test_pdf_normalization_markdown_table_sync() -> None:
    """Verifies that markdown table extraction in normalizer aligns 1:1 with line numbers."""
    normalizer = DocumentNormalizer()
    content = (
        "Document Preamble Header\n"
        "\n"
        "Some preceding text on line 3.\n"
        "\n"
        "| Metric | Value | Status |\n"
        "| :--- | :--- | :--- |\n"
        "| Precision | 1.0 | Pass |\n"
        "| Recall | 0.8 | Target |\n"
        "\n"
        "Trailing text on line 10.\n"
    )

    doc = normalizer.normalize_text(content, SupportedFormat.MARKDOWN)
    assert len(doc.tables) == 1
    tbl = doc.tables[0]
    assert tbl.start_line == 5
    assert tbl.end_line == 8
    assert tbl.headers == ["Metric", "Value", "Status"]
    assert tbl.row_count == 2
    assert tbl.col_count == 3

    # Check that lines 5-8 in doc.raw_text match the table
    raw_lines = doc.raw_text.splitlines()
    assert "| Metric | Value | Status |" in raw_lines[tbl.start_line - 1]
    assert "| Recall | 0.8 | Target |" in raw_lines[tbl.end_line - 1]


def test_ast_paragraph_and_code_block_mechanics() -> None:
    """Verifies that paragraph boundaries and fenced code blocks produce distinct AST nodes."""
    content = (
        "# Core Architecture\n"
        "\n"
        "Paragraph 1 explains system boundaries.\n"
        "\n"
        "Paragraph 2 details state machines.\n"
        "\n"
        "```python\n"
        "def execute_pipeline():\n"
        "    return True\n"
        "```\n"
        "\n"
        "Paragraph 3 follows the code fence.\n"
    )

    normalizer = DocumentNormalizer()
    norm = normalizer.normalize_text(content)
    segmenter = HierarchicalASTSegmenter()
    root = segmenter.parse_to_tree("core_arch", norm)
    leaf_nodes = segmenter.flatten_leaf_chunks(root)

    node_types = [leaf.node_type for leaf in leaf_nodes]
    assert "SECTION" in node_types
    assert "PARAGRAPH" in node_types
    assert "CODE" in node_types

    code_leaf = next(leaf for leaf in leaf_nodes if leaf.node_type == "CODE")
    assert "def execute_pipeline():" in code_leaf.verbatim_text
    assert code_leaf.path.endswith(".code")

    para_leaves = [leaf for leaf in leaf_nodes if leaf.node_type == "PARAGRAPH"]
    assert len(para_leaves) == 3
    assert "Paragraph 1" in para_leaves[0].verbatim_text
    assert "Paragraph 2" in para_leaves[1].verbatim_text
    assert "Paragraph 3" in para_leaves[2].verbatim_text


def test_anchor_edge_precision_filters_generic_and_ambiguous() -> None:
    """Verifies that generic anchor targets (#p, #tbl, #code) and ambiguous duplicate headings are rejected."""
    content = (
        "# Root Document\n"
        "\n"
        "See [Generic Link 1](#p) and [Generic Link 2](#tbl).\n"
        "See [Ambiguous Section](#repeated-heading) which appears twice.\n"
        "See [Deterministic Section](#unique-target).\n"
        "\n"
        "## Repeated Heading\n"
        "\n"
        "First appearance of repeated heading.\n"
        "\n"
        "## Repeated Heading\n"
        "\n"
        "Second appearance of repeated heading.\n"
        "\n"
        "## Unique Target\n"
        "\n"
        "Concrete unambiguous section target.\n"
    )

    engine = DocumentIngestionEngine()
    _chunks, edges, _meta = engine.process_raw("precision_doc", "Root Document", content)

    # Invariant: Zero edges to #p, #tbl, or duplicate #repeated-heading.
    # Exactly 1 edge to #unique-target.
    assert len(edges) == 1
    edge = edges[0]
    assert "unique_target" in edge.target_path.lower()


def test_lineage_breadcrumb_strictly_ancestral() -> None:
    """Verifies that breadcrumbs strictly contain ancestor titles and do NOT duplicate the node's own title."""
    content = (
        "# Root System\n"
        "\n"
        "## Layer Alpha\n"
        "\n"
        "### Component Beta\n"
        "\n"
        "Component Beta mechanics description.\n"
    )

    engine = DocumentIngestionEngine()
    chunks, _edges, _meta = engine.process_raw("breadcrumb_doc", "Root System", content)

    beta_chunk = next(c for c in chunks if "component_beta" in c.path and c.path.endswith(".p"))
    # Contextualized text must show [Layer Alpha > Component Beta] for the paragraph,
    # and the heading chunk for Component Beta itself must show [Layer Alpha]
    beta_heading = next(c for c in chunks if c.path.endswith("component_beta"))
    assert "[Root System > Layer Alpha]" in beta_heading.contextualized_text
    assert "Component Beta" not in beta_heading.contextualized_text.split("]")[0]

    assert "[Root System > Layer Alpha > Component Beta]" in beta_chunk.contextualized_text


def test_cli_ingest_command_execution(tmp_path: Path, monkeypatch) -> None:
    """Verifies that the CLI ingest command creates a staging session from file on disk."""
    from typer.testing import CliRunner

    from rag_eval.cli import app

    staging_dir = tmp_path / "stg_cache"
    staging_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("rag_eval.cli.StagingManager", lambda: StagingManager(staging_dir=staging_dir))

    doc_file = tmp_path / "spec_test.md"
    doc_file.write_text(
        "# Specification\n\nContent for CLI ingestion testing.\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(app, ["ingest", str(doc_file), "--slug", "cli_spec"])
    assert result.exit_code == 0
    assert "Successfully created staging session" in result.output

    # Verify session on disk
    mgr = StagingManager(staging_dir=staging_dir)
    assert mgr.session_exists("cli_spec")
    session = mgr.load_session("cli_spec")
    assert len(session.chunks) >= 1


def test_binary_pdf_bytes_ingestion(tmp_path: Path) -> None:
    """Verifies that actual binary PDF bytes are parsed cleanly and staged with intact metadata."""
    import pymupdf

    # Generate a real valid binary PDF in memory using pymupdf
    pdf_doc = pymupdf.open()
    page = pdf_doc.new_page()
    page.insert_text((50, 50), "# PDF Architectural Blueprint\n\nPreamble explaining invariants.\n\n## Core Engine\n\nDetails of binary execution.\n")
    pdf_bytes = pdf_doc.tobytes()
    pdf_doc.close()

    normalizer = DocumentNormalizer()
    norm_doc = normalizer.normalize_bytes(pdf_bytes, "blueprint.pdf", "application/pdf")
    assert norm_doc.format_type == SupportedFormat.PDF
    assert norm_doc.total_lines >= 1
    assert norm_doc.metadata.get("original_filename") == "blueprint.pdf"
    assert "Architectural Blueprint" in norm_doc.raw_text

    # Ingest into staging manager from bytes
    staging_dir = tmp_path / "stg_cache"
    staging_dir.mkdir(parents=True, exist_ok=True)
    mgr = StagingManager(staging_dir=staging_dir)
    session = mgr.create_session_from_bytes(
        doc_slug="pdf_blueprint",
        title="PDF Architectural Blueprint",
        content=pdf_bytes,
        file_name="blueprint.pdf",
    )
    assert len(session.chunks) >= 2
    assert mgr.session_exists("pdf_blueprint")


def test_corrupted_docx_exception_shielding() -> None:
    """Verifies that corrupted DOCX files trigger a clean CorpusDomainError instead of unhandled library crashes."""
    import pytest

    from rag_eval.exceptions import CorpusDomainError

    normalizer = DocumentNormalizer()
    corrupted_bytes = b"PK\x03\x04corrupted_invalid_zip_content"

    with pytest.raises(CorpusDomainError) as exc_info:
        normalizer.normalize_bytes(corrupted_bytes, "broken.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")

    assert "broken.docx" in str(exc_info.value)


def test_single_line_oversized_paragraph_splitting() -> None:
    """Verifies that a continuous single-line paragraph exceeding max_chunk_chars is split into bounded chunks."""
    long_words = ["word" + str(i) for i in range(500)]
    single_line_paragraph = " ".join(long_words)  # ~3500 chars on 1 line

    content = f"# Deep Heading\n\n{single_line_paragraph}\n"
    normalizer = DocumentNormalizer()
    norm = normalizer.normalize_text(content)

    segmenter = HierarchicalASTSegmenter(max_chunk_chars=600)
    root = segmenter.parse_to_tree("long_line_doc", norm)
    leaf_nodes = segmenter.flatten_leaf_chunks(root)

    para_chunks = [leaf for leaf in leaf_nodes if leaf.node_type == "PARAGRAPH"]
    assert len(para_chunks) >= 5
    for p in para_chunks:
        assert len(p.verbatim_text) <= 700


def test_unicode_anchor_deterministic_edges() -> None:
    """Verifies that deterministic edges resolve Unicode anchor slugs accurately with 100% precision."""
    content = (
        "# Hệ Thống\n"
        "\n"
        "Xem chi tiết tại [Đặc Tả Module](#đặc-tả-module) để biết thêm.\n"
        "\n"
        "## Đặc Tả Module\n"
        "\n"
        "Nội dung đặc tả chi tiết của module tiếng Việt.\n"
    )

    engine = DocumentIngestionEngine()
    _chunks, edges, _meta = engine.process_raw("unicode_doc", "Hệ Thống", content)

    assert len(edges) == 1
    edge = edges[0]
    assert edge.relation_type == RelationType.REFERENCES.value
    assert "dac_ta_module" in edge.target_path.lower()

