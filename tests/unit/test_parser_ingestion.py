import pytest

from rag_eval.ingestion.parser.chunker import HierarchicalASTSegmenter
from rag_eval.ingestion.parser.edges import LineageBreadcrumbAndEdgeExtractor
from rag_eval.ingestion.parser.engine import DocumentIngestionEngine
from rag_eval.ingestion.parser.normalizer import (
    DocumentNormalizer,
    PageLayoutSanitizer,
    SupportedFormat,
)
from rag_eval.schemas import RelationType, validate_ltree_path


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
    draft = engine.process_raw("schema_doc", "Data Schema", content)

    assert len(draft.chunks) >= 1
    table_chunks = [c for c in draft.chunks if c.metadata.get("is_table") is True]
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
    draft = engine.process_raw("edge_doc", "Root Overview", content)

    # Invariant: Must contain exactly 1 edge pointing to Subsystem Beta, and 0 hallucinated edges
    assert len(draft.edges) == 1
    edge = draft.edges[0]
    assert edge.relation_type == RelationType.REFERENCES
    assert "beta" in edge.target_path.lower()

    # Verify that target_path actually exists in chunks
    chunk_paths = {c.path for c in draft.chunks}
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
    draft_chunks = extractor.synthesize_breadcrumbs(root, leaves)

    deepest = next(c for c in draft_chunks if "normalizer" in c.path.lower() and c.path.endswith(".p"))
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
    draft = engine.process_raw("precision_doc", "Root Document", content)

    # Invariant: Zero edges to #p, #tbl, or duplicate #repeated-heading.
    # Exactly 1 edge to #unique-target.
    assert len(draft.edges) == 1
    edge = draft.edges[0]
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
    draft = engine.process_raw("breadcrumb_doc", "Root System", content)

    beta_chunk = next(c for c in draft.chunks if "component_beta" in c.path and c.path.endswith(".p"))
    beta_heading = next(c for c in draft.chunks if c.path.endswith("component_beta"))
    assert "[Root System > Layer Alpha]" in beta_heading.contextualized_text
    assert "Component Beta" not in beta_heading.contextualized_text.split("]")[0]
    assert "[Root System > Layer Alpha > Component Beta]" in beta_chunk.contextualized_text


def test_binary_pdf_bytes_ingestion(tmp_path) -> None:
    """Verifies that actual binary PDF bytes are parsed cleanly into ParsedDocumentDraft."""
    import pymupdf

    pdf_doc = pymupdf.open()
    page = pdf_doc.new_page()
    page.insert_text(
        (50, 50),
        "# PDF Architectural Blueprint\n\nPreamble explaining invariants.\n\n## Core Engine\n\nDetails of binary execution.\n",
    )
    pdf_bytes = pdf_doc.tobytes()
    pdf_doc.close()

    normalizer = DocumentNormalizer()
    norm_doc = normalizer.normalize_bytes(pdf_bytes, "blueprint.pdf", "application/pdf")
    assert norm_doc.format_type == SupportedFormat.PDF
    assert norm_doc.total_lines >= 1
    assert norm_doc.metadata.get("original_filename") == "blueprint.pdf"
    assert "Architectural Blueprint" in norm_doc.raw_text

    engine = DocumentIngestionEngine()
    draft = engine.process_bytes(
        content=pdf_bytes,
        file_name="blueprint.pdf",
        doc_slug="pdf_blueprint",
        title="PDF Architectural Blueprint",
    )
    assert len(draft.chunks) >= 2
    assert draft.doc_slug == "pdf_blueprint"
    assert draft.raw_text is not None


def test_corrupted_docx_exception_shielding() -> None:
    """Verifies that corrupted DOCX files trigger a clean CorpusDomainError instead of unhandled library crashes."""
    from rag_eval.exceptions import E_CORPUS_INTEGRITY_VIOLATION, CorpusDomainError

    normalizer = DocumentNormalizer()
    corrupted_bytes = b"PK\x03\x04corrupted_invalid_zip_content"

    with pytest.raises(CorpusDomainError) as exc_info:
        normalizer.normalize_bytes(
            corrupted_bytes,
            "broken.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

    assert exc_info.value.error_code == E_CORPUS_INTEGRITY_VIOLATION


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
    draft = engine.process_raw("unicode_doc", "Hệ Thống", content)

    assert len(draft.edges) == 1
    edge = draft.edges[0]
    assert edge.relation_type == RelationType.REFERENCES
    assert "dac_ta_module" in edge.target_path.lower()


def test_page_layout_sanitizer_removes_repetitive_headers_and_footers() -> None:
    """Verifies that PageLayoutSanitizer strips repetitive boundary lines occurring across >= min_repetition pages."""
    raw_document = (
        "Running Header Title\n\nPage 1 unique body content paragraph.\n\nConfidential Footer Notice\x0c"
        "Running Header Title\n\nPage 2 unique body content paragraph.\n\nConfidential Footer Notice\x0c"
        "Running Header Title\n\nPage 3 unique body content paragraph.\n\nConfidential Footer Notice\x0c"
        "Running Header Title\n\nPage 4 unique body content paragraph.\n\nConfidential Footer Notice"
    )

    clean_text, artifacts = PageLayoutSanitizer.sanitize_document(
        raw_document, min_repetition=3, boundary_window=3
    )

    assert "Running Header Title" not in clean_text
    assert "Confidential Footer Notice" not in clean_text
    assert "Page 1 unique body content paragraph." in clean_text
    assert "Page 2 unique body content paragraph." in clean_text
    assert "Page 3 unique body content paragraph." in clean_text
    assert "Page 4 unique body content paragraph." in clean_text

    assert len(artifacts) >= 2
    header_art = next(a for a in artifacts if a.line_text == "Running Header Title")
    footer_art = next(a for a in artifacts if a.line_text == "Confidential Footer Notice")

    assert header_art.occurrences == 4
    assert footer_art.occurrences == 4


def test_page_layout_sanitizer_below_min_repetition_retains_text() -> None:
    """Verifies that sequences with fewer pages than min_repetition retain boundary lines intact."""
    raw_document = (
        "Running Header\n\nShort page 1 text.\n\nFooter Text\x0c"
        "Running Header\n\nShort page 2 text.\n\nFooter Text"
    )

    clean_text, artifacts = PageLayoutSanitizer.sanitize_document(
        raw_document, min_repetition=3, boundary_window=3
    )

    assert "Running Header" in clean_text
    assert "Footer Text" in clean_text
    assert len(artifacts) == 0


def test_document_normalizer_form_feed_page_break_sanitization() -> None:
    """Verifies that normalize_text preserves ground-truth form feed (\\x0c) into sanitize_document."""
    raw_input = (
        "Document Running Title\n\nContent of chapter 1.\n\nPage Footer\x0c"
        "Document Running Title\n\nContent of chapter 2.\n\nPage Footer\x0c"
        "Document Running Title\n\nContent of chapter 3.\n\nPage Footer"
    )

    normalizer = DocumentNormalizer()
    doc = normalizer.normalize_text(raw_input)

    assert "Document Running Title" not in doc.raw_text
    assert "Page Footer" not in doc.raw_text
    assert "Content of chapter 1." in doc.raw_text
    assert "Content of chapter 2." in doc.raw_text
    assert "Content of chapter 3." in doc.raw_text
    assert "sanitized_page_artifacts" in doc.metadata
    artifacts_meta = doc.metadata["sanitized_page_artifacts"]
    assert isinstance(artifacts_meta, list)
    assert len(artifacts_meta) == 2


def test_continuous_stream_layout_sanitization_with_periodic_anchors() -> None:
    """Verifies that continuous streams without form-feed characters strip periodic anchors, counters, and delimiters."""
    continuous_input = (
        "# Chapter 1 Overview\n\n"
        "Section 1 technical architecture details.\n\n"
        "Periodic Publication Anchor\n\n"
        "Page 1\n\n"
        "-\n\n"
        "## Subsystem Alpha\n\n"
        "Alpha subsystem mechanics.\n\n"
        "Periodic Publication Anchor\n\n"
        "Page 2\n\n"
        "-\n\n"
        "## Subsystem Beta\n\n"
        "Beta subsystem mechanics.\n\n"
        "Periodic Publication Anchor\n\n"
        "Page 3\n\n"
        "-\n\n"
        "## Final Conclusions\n\n"
        "Final technical takeaways.\n"
    )

    normalizer = DocumentNormalizer()
    doc = normalizer.normalize_text(continuous_input)

    assert "Periodic Publication Anchor" not in doc.raw_text
    assert "Section 1 technical architecture details." in doc.raw_text
    assert "Alpha subsystem mechanics." in doc.raw_text
    assert "Beta subsystem mechanics." in doc.raw_text
    assert "Final technical takeaways." in doc.raw_text
    assert "sanitized_page_artifacts" in doc.metadata
    artifacts_meta = doc.metadata["sanitized_page_artifacts"]
    assert isinstance(artifacts_meta, list)
    artifact_texts = [a["line_text"] for a in artifacts_meta if isinstance(a, dict)]
    assert "Periodic Publication Anchor" in artifact_texts


def test_markdown_semantic_preservation_code_fences_and_lists() -> None:
    """Verifies that code blocks, list items, and git diff markers are 100% preserved during sanitization."""
    markdown_content = (
        "# System Operations\n\n"
        "- List item option alpha\n"
        "- List item option beta\n"
        "- List item option gamma\n\n"
        "Here is a code example with delimiters and git diff syntax:\n\n"
        "```diff\n"
        "- deleted_line_in_diff = True\n"
        "+ added_line_in_diff = True\n"
        "---\n"
        "```\n\n"
        "1. Numbered procedure one\n"
        "2. Numbered procedure two\n"
    )

    normalizer = DocumentNormalizer()
    doc = normalizer.normalize_text(markdown_content)

    assert "- List item option alpha" in doc.raw_text
    assert "- List item option beta" in doc.raw_text
    assert "- List item option gamma" in doc.raw_text
    assert "1. Numbered procedure one" in doc.raw_text
    assert "2. Numbered procedure two" in doc.raw_text
    assert "```diff\n- deleted_line_in_diff = True\n+ added_line_in_diff = True\n---\n```" in doc.raw_text


def test_code_fence_multiline_whitespace_preservation() -> None:
    """Verifies Invariant I-02: 3+ consecutive newlines inside code fences are preserved 100% verbatim."""
    content = (
        "# Code Sample Header\n\n"
        "Here is code with multiple blank lines:\n\n"
        "```python\n"
        "def compute():\n"
        "\n"
        "\n"
        "\n"
        "    return 100\n"
        "```\n\n"
        "Trailing text.\n"
    )
    normalizer = DocumentNormalizer()
    doc = normalizer.normalize_text(content)

    assert "def compute():\n\n\n\n    return 100" in doc.raw_text
    assert "Trailing text." in doc.raw_text
