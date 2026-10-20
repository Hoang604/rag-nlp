from __future__ import annotations

import tempfile
from pathlib import Path

from rag_eval.ingestion.parsers.nextjs_mdx import NextJSMDXParser


def test_nextjs_parser_section_chunking_preserves_preamble_and_code() -> None:
    """Verifies Invariant I-02: Heading section contains both introductory prose and code block with intact indentation."""
    content = """---
title: Updating Route Handlers
description: Primary route handler description
related:
  title: Next Steps
  description: Nested related description that must not overwrite primary
---

# Updating Route Handlers

**After (Next.js 16):**

For server-only values, access environment variables directly in Server Components:

```tsx filename="app/page.tsx"
async function fetchData() {
  const dbUrl = process.env.DATABASE_URL
  if (dbUrl) {
    return await db.query(dbUrl)
  }
}
```

Trailing explanatory sentence following the code.
"""
    with tempfile.NamedTemporaryFile("w", suffix=".mdx", delete=False) as f:
        f.write(content)
        path = Path(f.name)

    try:
        parser = NextJSMDXParser()
        draft = parser.parse(path, doc_slug="guides.route_handlers")

        assert draft.title == "Updating Route Handlers"
        assert draft.metadata["description"] == "Primary route handler description"
        assert len(draft.chunks) == 1

        chunk = draft.chunks[0]
        assert "**After (Next.js 16):**" in chunk.verbatim_text
        assert "For server-only values" in chunk.verbatim_text
        assert "    return await db.query(dbUrl)" in chunk.verbatim_text
        assert "Trailing explanatory sentence" in chunk.verbatim_text
        assert chunk.path.startswith("guides.route_handlers")
        assert chunk.metadata["framework"] == "nextjs"
    finally:
        path.unlink(missing_ok=True)


def test_nextjs_parser_tag_unwrapping_prevents_mashed_backticks() -> None:
    """Verifies Invariant I-03: Container tag unwrapping adds whitespace padding so code spans never collide."""
    content = """---
title: Installation Guide
---

# Installation

3. Edit the <AppOnly>`app/page.tsx`</AppOnly><PagesOnly>`pages/index.tsx`</PagesOnly> file and save it.
"""
    with tempfile.NamedTemporaryFile("w", suffix=".mdx", delete=False) as f:
        f.write(content)
        path = Path(f.name)

    try:
        parser = NextJSMDXParser()
        draft = parser.parse(path, doc_slug="install")

        assert len(draft.chunks) == 1
        chunk = draft.chunks[0]
        assert "`app/page.tsx` `pages/index.tsx`" in chunk.verbatim_text
        assert "``" not in chunk.verbatim_text
    finally:
        path.unlink(missing_ok=True)


def test_nextjs_parser_themed_image_and_caption_cohesion() -> None:
    """Verifies Invariant I-04: Themed <Image ...> and sibling caption spans normalize into markdown images with exact end_line."""
    content = """---
title: Cache Inspection
---

# Instant Navigation

<div style={{ display: 'flex', flexDirection: 'column' }}>
  <Image
    alt="Inspect Cache Component"
    srcLight="/docs/light/inspector-load.png"
    srcDark="/docs/dark/inspector-load.png"
    width="472"
    height="389"
  />
  <span style={{ fontSize: '0.875rem', opacity: 0.7 }}>
    After a page refresh.
  </span>
</div>
"""
    with tempfile.NamedTemporaryFile("w", suffix=".mdx", delete=False) as f:
        f.write(content)
        path = Path(f.name)

    try:
        parser = NextJSMDXParser()
        draft = parser.parse(path, doc_slug="instant_nav")

        assert len(draft.chunks) == 1
        chunk = draft.chunks[0]
        assert "![Inspect Cache Component](/docs/light/inspector-load.png)" in chunk.verbatim_text
        assert "*After a page refresh.*" in chunk.verbatim_text
        assert chunk.start_line == 5
        assert chunk.end_line == 18
    finally:
        path.unlink(missing_ok=True)


def test_nextjs_parser_image_with_backtick_in_alt() -> None:
    """Verifies that inline backticks inside image alt tags do not cause delimiter collision or XML leakage and end_line covers closing tag."""
    content = """---
title: Project Structure
---

## `src` folder

Next.js supports storing application code inside an optional `src` folder.

<Image
  alt="An example folder structure with the `src` folder"
  srcLight="/docs/light/project-organization-src-directory.png"
  srcDark="/docs/dark/project-organization-src-directory.png"
  width="1600"
  height="687"
/>
"""
    with tempfile.NamedTemporaryFile("w", suffix=".mdx", delete=False) as f:
        f.write(content)
        path = Path(f.name)

    try:
        parser = NextJSMDXParser()
        draft = parser.parse(path, doc_slug="project_structure")

        assert len(draft.chunks) == 1
        chunk = draft.chunks[0]
        assert "![An example folder structure with the `src` folder](/docs/light/project-organization-src-directory.png)" in chunk.verbatim_text
        assert 'folder"' not in chunk.verbatim_text
        assert "srcLight=" not in chunk.verbatim_text
        assert "/>" not in chunk.verbatim_text
        assert chunk.start_line == 5
        assert chunk.end_line == 15
    finally:
        path.unlink(missing_ok=True)


def test_nextjs_parser_emits_pre_heading_intro_as_overview_without_line_inversion() -> None:
    """Verifies that pre-heading introductory content is emitted as <slug>.overview preserving 1:1 line order."""
    content = """---
title: Installation
---

Create a new Next.js app and run it locally.

## Quick start

1. Create a new Next.js app named `my-app`
"""
    with tempfile.NamedTemporaryFile("w", suffix=".mdx", delete=False) as f:
        f.write(content)
        path = Path(f.name)

    try:
        parser = NextJSMDXParser()
        draft = parser.parse(path, doc_slug="nextjs.install")

        assert len(draft.chunks) == 2
        overview, quick_start = draft.chunks[0], draft.chunks[1]
        assert overview.path == "nextjs.install.overview"
        assert overview.start_line == 5
        assert overview.end_line == 5
        assert overview.metadata["node_type"] == "OVERVIEW"
        assert "Create a new Next.js app and run it locally." in overview.verbatim_text

        assert quick_start.path == "nextjs.install.quick_start"
        assert quick_start.start_line == 7
        assert quick_start.end_line == 9
        assert quick_start.verbatim_text.startswith("## Quick start")
    finally:
        path.unlink(missing_ok=True)


def test_nextjs_parser_disambiguates_app_and_pages_router_headings_and_merges_codemod_pairs() -> None:
    """Verifies router-scoped heading disambiguation (_app / _pages) and H4+H5 codemod pair merging."""
    content = """---
title: Codemods and Routers
---

## Reference

<AppOnly>

### Functions

- `generateStaticParams`

</AppOnly>

<PagesOnly>

### Functions

- `getStaticProps`

</PagesOnly>

## Codemods

### 16.0

#### Remove unstable prefix from stabilized API

##### `remove-unstable-prefix`

Run `npx @next/codemod remove-unstable-prefix`.
"""
    with tempfile.NamedTemporaryFile("w", suffix=".mdx", delete=False) as f:
        f.write(content)
        path = Path(f.name)

    try:
        parser = NextJSMDXParser()
        draft = parser.parse(path, doc_slug="nextjs.guides")

        assert len(draft.chunks) == 3
        app_fn, pages_fn, codemod = draft.chunks[0], draft.chunks[1], draft.chunks[2]

        assert app_fn.path == "nextjs.guides.reference.functions"
        assert app_fn.metadata["router"] == "app"
        app_ancestors = app_fn.metadata["ancestor_titles"]
        assert isinstance(app_ancestors, list)
        assert "Functions (App Router)" in app_ancestors

        assert pages_fn.path == "nextjs.guides.reference.functions_pages"
        assert pages_fn.metadata["router"] == "pages"
        pages_ancestors = pages_fn.metadata["ancestor_titles"]
        assert isinstance(pages_ancestors, list)
        assert "Functions (Pages Router)" in pages_ancestors

        assert codemod.path == "nextjs.guides.codemods.16_0.remove_unstable_prefix"
        assert "#### Remove unstable prefix from stabilized API" in codemod.verbatim_text
        assert "##### `remove-unstable-prefix`" in codemod.verbatim_text
        assert codemod.start_line == 27
        assert codemod.end_line == 31
    finally:
        path.unlink(missing_ok=True)


def test_nextjs_parser_trims_trailing_list_blank_line_and_unwraps_self_closing_br() -> None:
    """Verifies Loop 2 boundary fixes: list end_line excludes trailing blank lines and <br/> is unwrapped."""
    content = """---
title: List and Table Boundaries
---

## System requirements

- Node.js 20.9+<br/>Required
- macOS, Windows, or Linux

## Next section

 Prose paragraph.
"""
    with tempfile.NamedTemporaryFile("w", suffix=".mdx", delete=False) as f:
        f.write(content)
        path = Path(f.name)

    try:
        parser = NextJSMDXParser()
        draft = parser.parse(path, doc_slug="nextjs.bounds")

        assert len(draft.chunks) == 2
        sys_req = draft.chunks[0]
        assert sys_req.start_line == 5
        assert sys_req.end_line == 8
        assert "<br/>" not in sys_req.verbatim_text
        assert "Node.js 20.9+ Required" in sys_req.verbatim_text
    finally:
        path.unlink(missing_ok=True)

