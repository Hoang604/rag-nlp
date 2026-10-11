from __future__ import annotations

import tempfile
from pathlib import Path

from rag_eval.ingestion.parsers.nextjs_mdx import NextJSMDXParser


def test_nextjs_parser_section_chunking_preserves_preamble_and_code() -> None:
    """Verifies Invariant I-02: Heading section contains both introductory prose and code block."""
    content = """---
title: Updating Route Handlers
---

# Updating Route Handlers

**After (Next.js 16):**

For server-only values, access environment variables directly in Server Components:

```tsx filename="app/page.tsx"
async function fetchData() {
  const dbUrl = process.env.DATABASE_URL
  return await db.query(dbUrl)
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
        assert len(draft.chunks) == 1

        chunk = draft.chunks[0]
        # Invariant: Preamble, explanatory directive, and code block are in the SAME chunk
        assert "**After (Next.js 16):**" in chunk.verbatim_text
        assert "For server-only values" in chunk.verbatim_text
        assert "async function fetchData()" in chunk.verbatim_text
        assert "Trailing explanatory sentence" in chunk.verbatim_text
        assert chunk.path.startswith("guides.route_handlers")
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
        # Invariant: Space exists between adjacent inline code spans
        assert "`app/page.tsx` `pages/index.tsx`" in chunk.verbatim_text
        assert "``" not in chunk.verbatim_text
    finally:
        path.unlink(missing_ok=True)


def test_nextjs_parser_themed_image_and_caption_cohesion() -> None:
    """Verifies Invariant I-04: Themed <Image ...> and sibling caption spans normalize into markdown images."""
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

Next sentence in navigation explanation.
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
        assert "Next sentence in navigation explanation." in chunk.verbatim_text
    finally:
        path.unlink(missing_ok=True)


def test_nextjs_parser_image_with_backtick_in_alt() -> None:
    """Verifies that inline backticks inside image alt tags do not cause delimiter collision or XML leakage."""
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
        draft = parser.parse(path, doc_slug="project_structure.src_folder")

        assert len(draft.chunks) == 1
        chunk = draft.chunks[0]
        assert "![An example folder structure with the `src` folder](/docs/light/project-organization-src-directory.png)" in chunk.verbatim_text
        assert 'folder"' not in chunk.verbatim_text
        assert "srcLight=" not in chunk.verbatim_text
        assert "/>" not in chunk.verbatim_text
    finally:
        path.unlink(missing_ok=True)


def test_nextjs_parser_folds_pre_heading_intro() -> None:
    """Verifies that pre-heading introductory sentences are folded into the first child section."""
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
        draft = parser.parse(path, doc_slug="install")

        assert len(draft.chunks) == 1
        chunk = draft.chunks[0]
        assert chunk.path == "install.quick_start"
        assert "Create a new Next.js app and run it locally." in chunk.verbatim_text
        assert "## Quick start" in chunk.verbatim_text
    finally:
        path.unlink(missing_ok=True)
