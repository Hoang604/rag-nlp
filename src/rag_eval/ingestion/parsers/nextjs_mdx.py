from __future__ import annotations

import logging
import re
from pathlib import Path

from markdown_it import MarkdownIt
from markdown_it.tree import SyntaxTreeNode

from rag_eval.exceptions import E_CORPUS_INTEGRITY_VIOLATION, CorpusDomainError
from rag_eval.ingestion.registry import BaseCodingParser
from rag_eval.schemas import (
    ParsedChunkDraft,
    ParsedDocumentDraft,
    canonicalize_ltree_path,
    sanitize_ltree_label,
    validate_ltree_path,
)

logger = logging.getLogger(__name__)

_FRONTMATTER_REGEX = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _disambiguate_label(candidate: str, used_labels: set[str]) -> str:
    """Ensures label is unique among sibling nodes under the same parent."""
    clean = sanitize_ltree_label(candidate)
    if clean not in used_labels:
        used_labels.add(clean)
        return clean

    counter = 1
    while f"{clean}_{counter}" in used_labels:
        counter += 1
    unique_label = f"{clean}_{counter}"
    used_labels.add(unique_label)
    return unique_label


class NextJSMDXParser(BaseCodingParser):
    """Dedicated Section-Level parser for Next.js App Router technical documentation (MDX/MD).

    Enforces:
    1. Section-Level Chunking: Explanatory prose, code blocks, tables, and lists under
       a Heading (H1/H2/H3) form an atomic chunk up to 4,000 characters.
    2. Tag Unwrapping with Space Padding: Strips container tags (<AppOnly>, <PagesOnly>)
       with whitespace substitution, guaranteeing adjacent code tokens never mash together.
    3. Themed Media Conversion: Normalizes <Image ...> with srcLight/srcDark and caption
       spans into standard Markdown ![alt](url)\n*caption*.
    4. Zero Fallback: Dedicated strictly to Next.js documentation files.
    """

    name: str = "nextjs_mdx"

    def __init__(self, max_chunk_chars: int = 4000) -> None:
        self.max_chunk_chars = max_chunk_chars
        self._md = MarkdownIt("commonmark").enable("table")

    def can_handle(self, file_path: Path, raw_text: str = "") -> bool:
        """Matches Next.js Markdown and MDX documentation files."""
        suffix = Path(file_path).suffix.lower()
        return suffix in (".mdx", ".md")

    def _sanitize_nextjs_content(self, content: str) -> tuple[str, str, dict[str, object]]:
        """Extracts YAML frontmatter, unwraps JSX containers, and normalizes media preserving exact 1:1 line mapping."""
        title = ""
        meta: dict[str, object] = {}
        lines = content.splitlines()

        # 1. Parse and extract YAML frontmatter, blanking lines to preserve 1:1 line correspondence
        if lines and lines[0].strip() == "---":
            close_idx = None
            for i in range(1, len(lines)):
                if lines[i].strip() == "---":
                    close_idx = i
                    break
            if close_idx is not None:
                for line in lines[1:close_idx]:
                    if ":" in line:
                        k, v = line.split(":", 1)
                        k_clean = k.strip().lower()
                        v_clean = v.strip().strip("\"'")
                        meta[k_clean] = v_clean
                        if k_clean == "title" and not title:
                            title = v_clean
                for i in range(close_idx + 1):
                    lines[i] = " "

        # 2. Line-by-line sanitization outside code fences
        in_code_fence = False
        in_multiline_comment = False
        clean_lines: list[str] = []

        for line in lines:
            stripped = line.strip()

            # Check code fence boundary
            if stripped.startswith("```"):
                in_code_fence = not in_code_fence
                clean_lines.append(line)
                continue

            if in_code_fence:
                clean_lines.append(line)
                continue

            cur_line = line

            # Handle multiline comments {/* ... */}
            if in_multiline_comment:
                if "*/}" in cur_line:
                    cur_line = re.sub(r"^.*?\*/\}", " ", cur_line)
                    in_multiline_comment = False
                else:
                    clean_lines.append(" ")
                    continue

            while "{/*" in cur_line:
                if "*/}" in cur_line:
                    cur_line = re.sub(r"\{/\*.*?\*/\}", " ", cur_line)
                else:
                    cur_line = re.sub(r"\{/\*.*$", " ", cur_line)
                    in_multiline_comment = True
                    break

            clean_lines.append(cur_line)

        body = "\n".join(clean_lines)

        # 3. Protect code fences and inline backtick code spans before tag/image transformations
        code_blocks: list[str] = []

        def _mask_code(m: re.Match[str]) -> str:
            idx = len(code_blocks)
            code_blocks.append(m.group(0))
            nl_count = m.group(0).count("\n")
            return f"__MASKED_CODE_{idx}__" + ("\n" * nl_count)

        masked_body = re.compile(r"(?ms)^```[^\n]*\n.*?^```(?:\n|$)").sub(_mask_code, body)

        inline_spans: list[str] = []

        def _mask_inline(m: re.Match[str]) -> str:
            idx = len(inline_spans)
            inline_spans.append(m.group(0))
            return f"__MASKED_INLINE_{idx}__"

        masked_body = re.sub(r"`[^`\n]+`", _mask_inline, masked_body)

        # 4. Normalize themed <Image ... /> and captions without shifting line counts
        def _replace_image_block(match: re.Match[str]) -> str:
            full_match = match.group(0)
            alt_m = re.search(r'alt=["\']([^"\']*)["\']', full_match)
            alt = alt_m.group(1) if alt_m else "Diagram"

            src_m = re.search(r'src(?:Light)?=["\']([^"\']+)["\']', full_match)
            if not src_m:
                src_m = re.search(r'srcDark=["\']([^"\']+)["\']', full_match)
            src = src_m.group(1) if src_m else ""

            caption_m = re.search(r"<span[^>]*>(.*?)</span>", full_match, re.DOTALL)
            caption = caption_m.group(1).strip() if caption_m else ""

            replacement_parts = [f"![{alt}]({src})"]
            if caption:
                replacement_parts.append(f"*{caption}*")
            replacement = "\n".join(replacement_parts)

            orig_newlines = full_match.count("\n")
            rep_newlines = replacement.count("\n")
            if orig_newlines > rep_newlines:
                replacement += "\n" * (orig_newlines - rep_newlines)
            return replacement

        masked_body = re.sub(
            r"(?s)<div[^>]*>\s*<Image\b(?=[^>]*\b(?:src|srcLight|srcDark)\b)[^>]*/>\s*(?:<span[^>]*>.*?</span>\s*)?</div>",
            _replace_image_block,
            masked_body,
        )
        masked_body = re.sub(
            r"(?s)<Image\b(?=[^>]*\b(?:src|srcLight|srcDark)\b)[^>]*/>",
            _replace_image_block,
            masked_body,
        )

        # 5. Unwrap JSX container tags with space padding preserving any multiline newlines
        def _unwrap_tag(m: re.Match[str]) -> str:
            nl_count = m.group(0).count("\n")
            return " " + ("\n" * nl_count)

        unwrapped = re.sub(r"</?[a-zA-Z][a-zA-Z0-9_:-]*(?:\s+[^>]*?)?>", _unwrap_tag, masked_body)

        # Restore inline spans
        for idx, span in enumerate(inline_spans):
            unwrapped = unwrapped.replace(f"__MASKED_INLINE_{idx}__", span)

        # Restore code blocks verbatim
        for idx, block in enumerate(code_blocks):
            nl_count = block.count("\n")
            unwrapped = unwrapped.replace(f"__MASKED_CODE_{idx}__" + ("\n" * nl_count), block)

        # Collapse multi-spaces within lines while preserving newlines
        clean_lines = [re.sub(r"[ \t]+", " ", l) if l.strip() else " " for l in unwrapped.split("\n")]
        clean_text = "\n".join(clean_lines)

        assert len(clean_text.splitlines()) == len(content.splitlines()), (
            f"Line count invariant violation: clean_text has {len(clean_text.splitlines())} lines, "
            f"raw content has {len(content.splitlines())} lines."
        )

        return clean_text, title, meta

    def parse(
        self,
        file_path: Path,
        doc_slug: str | None = None,
        corpus_root: Path | None = None,
    ) -> ParsedDocumentDraft:
        """Parses Next.js documentation file into ParsedDocumentDraft with Section-Level chunks."""
        resolved_path = Path(file_path).resolve()
        if not resolved_path.exists() or not resolved_path.is_file():
            raise CorpusDomainError(
                error_code=E_CORPUS_INTEGRITY_VIOLATION,
                message=f"File '{file_path}' does not exist or is not a readable file.",
                data={"path": str(file_path)},
            )

        raw_content = resolved_path.read_text("utf-8", errors="replace")

        # Determine canonical doc_slug
        if doc_slug is not None:
            slug = canonicalize_ltree_path(doc_slug)
        elif corpus_root is not None and resolved_path.is_relative_to(corpus_root.resolve()):
            rel = resolved_path.relative_to(corpus_root.resolve())
            stem_path = rel.with_suffix("").as_posix()
            slug = canonicalize_ltree_path(stem_path)
        else:
            slug = canonicalize_ltree_path(resolved_path.stem)

        return self.parse_text(raw_content, doc_slug=slug)

    def parse_text(
        self,
        raw_content: str,
        doc_slug: str,
        title: str | None = None,
    ) -> ParsedDocumentDraft:
        """Parses raw text of Next.js documentation into ParsedDocumentDraft with Section-Level chunks."""
        slug = canonicalize_ltree_path(doc_slug)
        clean_text, fm_title, fm_meta = self._sanitize_nextjs_content(raw_content)

        if not clean_text:
            return ParsedDocumentDraft(
                doc_slug=slug,
                title=title or fm_title or "",
                raw_text=raw_content,
                chunks=[],
                edges=[],
                metadata={
                    "total_lines": len(raw_content.splitlines()),
                    "format_type": "nextjs_mdx",
                    **fm_meta,
                },
            )

        # Parse with CommonMark AST to extract sections and headings
        tokens = self._md.parse(clean_text)
        syntax_tree = SyntaxTreeNode(tokens)

        # Determine effective document title
        effective_title = title or fm_title
        if not effective_title:
            for child in syntax_tree.children:
                if child.type == "heading" and child.tag in ("h1", "h2"):
                    effective_title = "".join(c.content for c in child.children).strip()
                    break
        effective_title = effective_title or "Documentation"

        raw_lines = clean_text.splitlines()

        # Build Section Tree
        # Each heading defines a section boundary.
        # Prose, code, tables, and lists are gathered into the active section.
        class SectionBuilder:
            def __init__(
                self,
                level: int,
                title: str,
                path: str,
                breadcrumbs: list[str],
                start_line: int,
            ) -> None:
                self.level = level
                self.title = title
                self.path = path
                self.breadcrumbs = breadcrumbs
                self.start_line = start_line
                self.end_line = start_line
                self.content_lines: list[str] = []

        root_section = SectionBuilder(
            level=0,
            title=effective_title,
            path=slug,
            breadcrumbs=[effective_title],
            start_line=0,
        )

        # Stack holds (level, SectionBuilder, used_child_labels)
        stack: list[tuple[int, SectionBuilder, set[str]]] = [(0, root_section, set())]
        completed_sections: list[SectionBuilder] = []

        children = syntax_tree.children
        for node in children:
            if node.type == "heading":
                h_level = int(node.tag[1]) if len(node.tag) > 1 and node.tag[1].isdigit() else 1
                h_title = "".join(c.content for c in node.children).strip() or "Section"
                h_start = node.map[0] + 1 if node.map else 1
                h_end = node.map[1] if node.map else h_start

                # Pop sections of same or deeper level
                while len(stack) > 1 and stack[-1][0] >= h_level:
                    _, popped, _ = stack.pop()
                    completed_sections.append(popped)

                _, parent_builder, child_labels = stack[-1]
                slug_label = _disambiguate_label(h_title, child_labels)
                new_path = validate_ltree_path(f"{parent_builder.path}.{slug_label}")
                new_breadcrumbs = list(parent_builder.breadcrumbs)
                if not new_breadcrumbs or new_breadcrumbs[-1].lower() != h_title.lower():
                    new_breadcrumbs.append(h_title)

                new_section = SectionBuilder(
                    level=h_level,
                    title=h_title,
                    path=new_path,
                    breadcrumbs=new_breadcrumbs,
                    start_line=h_start,
                )
                new_section.end_line = h_end
                stack.append((h_level, new_section, set()))
                continue

            # Gather content lines for the current active section
            if node.map:
                s_0, e_0 = node.map
                active_builder = stack[-1][1]
                node_text = "\n".join(raw_lines[s_0:e_0]).strip()
                if node_text:
                    if not active_builder.content_lines and active_builder.level == 0:
                        active_builder.start_line = s_0 + 1
                    active_builder.content_lines.append(node_text)
                    active_builder.end_line = max(active_builder.end_line, e_0)

        # Flush remaining sections on stack
        while stack:
            _, remaining, _ = stack.pop()
            completed_sections.append(remaining)

        # If root section has pre-heading intro text and child sections exist,
        # fold root intro into the first child section to avoid isolated micro-chunks
        child_sections = [s for s in completed_sections if s.level > 0]
        if root_section.content_lines and child_sections:
            child_sections.sort(key=lambda s: s.start_line)
            first_child = child_sections[0]
            first_child.content_lines = root_section.content_lines + first_child.content_lines
            if root_section.start_line > 0:
                first_child.start_line = min(first_child.start_line, root_section.start_line)
            root_section.content_lines = []

        # Generate atomic section chunks (One cohesive chunk per heading section)
        chunks: list[ParsedChunkDraft] = []
        for sec in completed_sections:
            body_text = "\n\n".join(sec.content_lines).strip()
            if not body_text:
                continue

            # Full verbatim including heading title if available
            if sec.level > 0 and not body_text.startswith(("#", f"#{sec.level}")):
                full_verbatim = f"## {sec.title}\n\n{body_text}"
            else:
                full_verbatim = body_text

            bc_prefix = f"[{' > '.join(sec.breadcrumbs)}]\n"
            chunk_meta: dict[str, object] = {
                "heading": sec.title,
                "node_type": "SECTION",
                "has_code": "```" in full_verbatim,
                "has_table": "|" in full_verbatim,
                "ancestor_titles": sec.breadcrumbs,
            }
            chunks.append(
                ParsedChunkDraft(
                    path=sec.path,
                    verbatim_text=full_verbatim,
                    contextualized_text=f"{bc_prefix}{full_verbatim}",
                    start_line=sec.start_line,
                    end_line=sec.end_line,
                    metadata=chunk_meta,
                )
            )

        # Sort chunks by start_line and path
        chunks.sort(key=lambda c: (c.start_line, c.path))

        doc_meta = dict(fm_meta)
        doc_meta["total_lines"] = len(raw_content.splitlines())
        doc_meta["format_type"] = "nextjs_mdx"
        doc_meta["chunks_count"] = len(chunks)

        return ParsedDocumentDraft(
            doc_slug=slug,
            title=effective_title,
            raw_text=raw_content,
            chunks=chunks,
            edges=[],
            metadata=doc_meta,
        )
