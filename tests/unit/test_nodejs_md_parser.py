from __future__ import annotations

import tempfile
from pathlib import Path

from rag_eval.ingestion.parsers.nextjs_mdx import NextJSMDXParser
from rag_eval.ingestion.parsers.nodejs_md import NodeJSMarkdownParser
from rag_eval.ingestion.registry import CodingParserRegistry


def test_nodejs_parser_extracts_comment_metadata_and_preserves_line_numbers() -> None:
    """Verifies that NodeJSMarkdownParser extracts HTML comment metadata, synthesizes YAML version badges,
    strips standalone HTML anchor tags, binds H1 to root (no duplicate H1 path), and emits overview + API chunks.
    """
    content = """# Sample Module

<!--introduced_in=v1.0.0-->

> Stability: 2 - Stable

<!--name=sample_mod-->
<!-- source_link=lib/sample.js -->

Module overview paragraph.

## `sample.execute(input[, options])`

<!-- YAML
added:
  - v2.1.0
deprecated: v4.0.0
changes:
  - version: v3.0.0
    pr-url: https://example.com/pr/1
    description: Updated internal behavior.
-->

* `input` {string} Input token.
* Returns: {Promise}

Executes the operation asynchronously.

```mjs
import { execute } from 'node:sample';
await execute('test');
```

<a id="NEXT_ANCHOR"></a>

[ref_link]: other.md#anchor
"""
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
        f.write(content)
        path = Path(f.name)

    try:
        parser = NodeJSMarkdownParser()
        assert parser.can_handle(path, content) is True

        draft = parser.parse(path)
        assert draft.doc_slug.startswith("nodejs.")
        assert draft.title == "Sample Module"
        assert draft.metadata["introduced_in"] == "v1.0.0"
        assert draft.metadata["module_name"] == "sample_mod"
        assert draft.metadata["source_link"] == "lib/sample.js"
        assert draft.metadata["format_type"] == "nodejs_md"
        assert draft.metadata["framework"] == "nodejs"

        assert len(draft.chunks) == 2
        overview_chunk = draft.chunks[0]
        assert overview_chunk.path == f"{draft.doc_slug}.overview"
        assert "Module overview paragraph." in overview_chunk.verbatim_text

        chunk = draft.chunks[1]
        assert chunk.path == f"{draft.doc_slug}.sample_execute_input_options"
        assert chunk.contextualized_text.startswith("[Node.js > Sample Module > `sample.execute(input[, options])`]\n")
        assert "*Added in: v2.1.0 — Deprecated in: v4.0.0*" in chunk.verbatim_text
        assert "*Added in: -" not in chunk.verbatim_text
        assert "pr-url:" not in chunk.verbatim_text
        assert "NEXT_ANCHOR" not in chunk.verbatim_text
        assert "[ref_link]:" not in chunk.verbatim_text
        assert chunk.metadata["stability"] == "2"
        assert chunk.metadata["has_code"] is True
        assert chunk.metadata["has_table"] is False
    finally:
        path.unlink(missing_ok=True)


def test_nodejs_parser_folds_consecutive_overloaded_headings_and_drops_empty_non_overloads() -> None:
    """Verifies that consecutive same-level headings sharing the same callable name are folded together,
    while unrelated empty headings (like V8 flag lists) are discarded instead of merged.
    """
    content = """# Runtime Module

<!--introduced_in=v1.0.0-->

### `--empty-flag-one`

### `--empty-flag-two`

### `new Runner(first[, second])`

### `new Runner(options)`

<!-- YAML
added: v1.2.0
-->

Constructs a new runner instance with either positional arguments or an options object.
"""
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
        f.write(content)
        path = Path(f.name)

    try:
        parser = NodeJSMarkdownParser()
        draft = parser.parse(path, doc_slug="nodejs.runtime")

        assert len(draft.chunks) == 1
        chunk = draft.chunks[0]
        assert "--empty-flag" not in chunk.verbatim_text
        assert "## `new Runner(first[, second])`" in chunk.verbatim_text
        assert "## `new Runner(options)`" in chunk.verbatim_text
        assert "Constructs a new runner instance" in chunk.verbatim_text
        assert chunk.start_line == 9
    finally:
        path.unlink(missing_ok=True)


def test_nodejs_parser_separates_class_members_and_folds_method_internal_subheadings() -> None:
    """Verifies that metadata-only class containers do not emit empty chunks, independent member headings
    (even at H5) emit distinct chunks, and method-internal parameter/caveat subheadings stay inside the method.
    """
    content = """# Stream Sample

<!--introduced_in=v15.0.0-->

#### Class: `SampleStream`

<!-- YAML
added: v15.0.0
-->

* Extends: {EventEmitter}

##### Event: `'data'`

<!-- YAML
added: v15.0.0
-->

* `chunk` {Buffer}

Emitted when data is available.

##### `sampleStream.process(input, options)`

<!-- YAML
added: v15.0.0
-->

Executes stream processing.

###### `options`

Detailed explanation of the `options` parameter.

###### Caveats

Platform-specific caveats for `sampleStream.process`.
"""
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
        f.write(content)
        path = Path(f.name)

    try:
        parser = NodeJSMarkdownParser()
        draft = parser.parse(path, doc_slug="nodejs.stream_sample")

        assert len(draft.chunks) == 2
        event_chunk, method_chunk = draft.chunks
        assert event_chunk.path == "nodejs.stream_sample.class_samplestream.event_data"
        assert method_chunk.path == "nodejs.stream_sample.class_samplestream.samplestream_process_input_options"
        assert "###### `options`" in method_chunk.verbatim_text
        assert "###### Caveats" in method_chunk.verbatim_text
    finally:
        path.unlink(missing_ok=True)


def test_nodejs_parser_handles_multiline_stability_and_symbolic_cli_headings() -> None:
    """Verifies that multi-line '> Stability:' callouts on container headings do not emit junk chunks,
    and symbolic CLI headings ('-', '--') map to distinct semantic ltree labels instead of 'section_1'.
    """
    content = """# CLI Sample

<!--introduced_in=v1.0.0-->

## Legacy Codes

> Stability: 0 - Deprecated. These codes are inconsistent, or have
> been removed.

### `ERR_SAMPLE`

Sample error description.

## Options

### `-`

Read from stdin.

### `--`

Indicate the end of node options.
"""
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
        f.write(content)
        path = Path(f.name)

    try:
        parser = NodeJSMarkdownParser()
        draft = parser.parse(path, doc_slug="nodejs.cli_sample")

        paths = [c.path for c in draft.chunks]
        assert paths == [
            "nodejs.cli_sample.legacy_codes.err_sample",
            "nodejs.cli_sample.options.dash",
            "nodejs.cli_sample.options.double_dash",
        ]
        assert draft.chunks[0].metadata["stability"] == "0"
    finally:
        path.unlink(missing_ok=True)


def test_registry_dispatches_nodejs_vs_nextjs_accurately(tmp_path: Path) -> None:
    """Verifies that CodingParserRegistry dispatches Node.js vs Next.js files without collision and rejects unknown Markdown."""
    import pytest

    from rag_eval.ingestion.registry import UnsupportedFrameworkError

    CodingParserRegistry.clear()
    CodingParserRegistry.register(NodeJSMarkdownParser())
    CodingParserRegistry.register(NextJSMDXParser())

    nodejs_dir = tmp_path / "nodejs"
    nodejs_dir.mkdir()
    node_file = nodejs_dir / "mod.md"
    node_file.write_text("# Node Mod\n\n<!--introduced_in=v1.0.0-->\n\nNode content.\n", encoding="utf-8")

    nextjs_dir = tmp_path / "nextjs"
    nextjs_dir.mkdir()
    next_file = nextjs_dir / "page.mdx"
    next_file.write_text("---\ntitle: Page\n---\n\n# Page\n\nNext content.\n", encoding="utf-8")

    unknown_dir = tmp_path / "other_domain"
    unknown_dir.mkdir()
    unknown_file = unknown_dir / "random.md"
    unknown_file.write_text("# Random Doc\n\nPlain text without Next.js or Node.js markers.\n", encoding="utf-8")

    node_parser = CodingParserRegistry.get_parser(node_file)
    assert node_parser.name == "nodejs_md"
    node_draft = node_parser.parse(node_file, corpus_root=nodejs_dir)
    assert node_draft.doc_slug == "nodejs.mod"

    next_parser = CodingParserRegistry.get_parser(next_file)
    assert next_parser.name == "nextjs_mdx"
    next_draft = next_parser.parse(next_file, corpus_root=nextjs_dir)
    assert next_draft.doc_slug == "nextjs.page"

    with pytest.raises(UnsupportedFrameworkError):
        CodingParserRegistry.get_parser(unknown_file)
