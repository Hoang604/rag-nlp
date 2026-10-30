from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
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

_CODEMOD_SLUG_REGEX = re.compile(r"^`[a-z0-9][a-z0-9_-]*`$")
_TOP_LEVEL_YAML_KEY_REGEX = re.compile(r"^([a-zA-Z0-9_-]+)\s*:\s*(.*)$")
NEXTJS_CONTENT_MARKER_REGEX = re.compile(
    r"\A---\s*\n(?:[^\n]*\n)*?title\s*:|<AppOnly>|<PagesOnly>|<Image\b|<Video\b|<FixCardGrid>",
    re.MULTILINE,
)


def _disambiguate_label(
    candidate: str,
    used_labels: set[str],
    router: str | None = None,
) -> str:
    """Ensures label is unique among sibling nodes under the same parent, preferring router suffix on collision."""
    clean = sanitize_ltree_label(candidate)
    if clean not in used_labels:
        used_labels.add(clean)
        return clean

    if router in ("app", "pages"):
        router_candidate = f"{clean}_{router}"
        if router_candidate not in used_labels:
            used_labels.add(router_candidate)
            return router_candidate

    counter = 1
    while f"{clean}_{counter}" in used_labels:
        counter += 1
    unique_label = f"{clean}_{counter}"
    used_labels.add(unique_label)
    return unique_label


@dataclass
class _BlockItem:
    text: str
    start_line: int
    end_line: int
    router: str | None = None


@dataclass
class _SectionNode:
    level: int
    title: str
    path: str
    breadcrumbs: list[str]
    start_line: int
    end_line: int
    router: str | None = None
    paired_heading_prefix: str | None = None
    blocks: list[_BlockItem] = field(default_factory=list)
    children: list[_SectionNode] = field(default_factory=list)


class NextJSMDXParser(BaseCodingParser):
    """Dedicated Section-Level parser for Next.js technical documentation (MDX/MD).

    Enforces:
    1. Exact 1:1 Line Preservation: Frontmatter, comments, media tags (<Image>, <Video>),
       diagnostic cards (<FixCardGrid>/<FixCard>), and router containers (<AppOnly>, <PagesOnly>)
       preserve exact 1-indexed [start_line, end_line] mappings against documents.raw_text.
    2. Router-Aware Section Hierarchy: Tracks <AppOnly> and <PagesOnly> scopes across both
       inline blocks and section headings, annotating breadcrumbs and disambiguating sibling paths.
    3. True Document Overview & Codemod Pair Cohesion: Emits pre-heading document introductions
       as <slug>.overview without inverting line order into the first H2, and merges paired
       H4 (description) + H5 (`codemod-slug`) headings in codemods documentation.
    4. Code Indentation Fidelity: Masks fenced code blocks prior to prose whitespace normalization
       so multi-level code indentation is preserved verbatim.
    """

    name: str = "nextjs_mdx"
    framework_prefix: str = "nextjs"

    def __init__(self) -> None:
        self._md = MarkdownIt("commonmark").enable("table")

    def can_handle(self, file_path: Path, raw_text: str = "") -> bool:
        """Matches Next.js Markdown and MDX documentation files by corpus path or Next.js MDX/frontmatter markers."""
        suffix = Path(file_path).suffix.lower()
        if suffix not in (".mdx", ".md"):
            return False

        parts_lower = {p.lower() for p in Path(file_path).parts}
        if "nextjs" in parts_lower or "next_docs" in parts_lower:
            return True

        return bool(raw_text and NEXTJS_CONTENT_MARKER_REGEX.search(raw_text))

    def _sanitize_nextjs_content(
        self, content: str
    ) -> tuple[str, str, dict[str, object], list[str | None], dict[int, int]]:
        """Extracts top-level YAML frontmatter, tracks router scopes, and normalizes MDX constructs
        while preserving exact 1:1 line count and end_line alignment.
        """
        title = ""
        meta: dict[str, object] = {}
        raw_lines = content.splitlines()
        total_lines = len(raw_lines)
        lines = list(raw_lines)

        # 1. Parse top-level YAML frontmatter keys (column 0 only) and blank frontmatter lines
        close_idx: int | None = None
        if lines and lines[0].strip() == "---":
            for i in range(1, len(lines)):
                if lines[i].strip() == "---":
                    close_idx = i
                    break
            if close_idx is not None:
                related_links: list[str] = []
                in_related_links = False
                for line in lines[1:close_idx]:
                    top_m = _TOP_LEVEL_YAML_KEY_REGEX.match(line)
                    if top_m:
                        in_related_links = False
                        k_clean = top_m.group(1).strip().lower()
                        v_clean = top_m.group(2).strip().strip("\"'")
                        if k_clean != "related":
                            meta[k_clean] = v_clean
                            if k_clean == "title" and not title:
                                title = v_clean
                        continue

                    stripped_fm = line.strip()
                    if stripped_fm.startswith("links:"):
                        in_related_links = True
                    elif in_related_links and stripped_fm.startswith("- "):
                        related_links.append(stripped_fm[2:].strip().strip("\"'"))

                if related_links:
                    meta["related_links"] = related_links

                for i in range(close_idx + 1):
                    lines[i] = " "

        # 2. Track <AppOnly> and <PagesOnly> line scopes and strip MDX comments outside code fences
        in_code_fence = False
        fence_marker = ""
        in_multiline_comment = False
        active_router: str | None = None
        line_router: list[str | None] = [None] * total_lines
        clean_lines: list[str] = []

        for idx, line in enumerate(lines):
            stripped = line.strip()

            # Check code fence boundary (supports 3 or more backticks)
            fence_m = re.match(r"^(`{3,})", stripped)
            if fence_m:
                ticks = fence_m.group(1)
                if not in_code_fence:
                    in_code_fence = True
                    fence_marker = ticks
                elif stripped.startswith(fence_marker) and stripped == ticks:
                    in_code_fence = False
                    fence_marker = ""
                line_router[idx] = active_router
                clean_lines.append(line)
                continue

            if in_code_fence:
                line_router[idx] = active_router
                clean_lines.append(line)
                continue

            cur_line = line

            # Handle multiline comments {/* ... */}
            if in_multiline_comment:
                if "*/}" in cur_line:
                    cur_line = re.sub(r"^.*?\*/\}", " ", cur_line)
                    in_multiline_comment = False
                else:
                    line_router[idx] = active_router
                    clean_lines.append(" ")
                    continue

            while "{/*" in cur_line:
                if "*/}" in cur_line:
                    cur_line = re.sub(r"\{/\*.*?\*/\}", " ", cur_line)
                else:
                    cur_line = re.sub(r"\{/\*.*$", " ", cur_line)
                    in_multiline_comment = True
                    break

            # Track standalone <AppOnly> / <PagesOnly> boundaries
            s_cur = cur_line.strip()
            if s_cur == "<AppOnly>":
                active_router = "app"
                line_router[idx] = active_router
                clean_lines.append(" ")
                continue
            if s_cur == "</AppOnly>":
                line_router[idx] = active_router
                active_router = None
                clean_lines.append(" ")
                continue
            if s_cur == "<PagesOnly>":
                active_router = "pages"
                line_router[idx] = active_router
                clean_lines.append(" ")
                continue
            if s_cur == "</PagesOnly>":
                line_router[idx] = active_router
                active_router = None
                clean_lines.append(" ")
                continue

            # Blank standalone anchor spans (<span id="..." />) so they do not attach to preceding sections
            if re.match(r"^<span\s+id=[^>]+/>\s*$", s_cur):
                line_router[idx] = active_router
                clean_lines.append(" ")
                continue

            line_router[idx] = active_router
            clean_lines.append(cur_line)

        body = "\n".join(clean_lines)

        # 3. Mask fenced code blocks and inline code spans before JSX transformations
        code_blocks: list[str] = []

        def _mask_code(m: re.Match[str]) -> str:
            idx = len(code_blocks)
            code_blocks.append(m.group(0))
            nl_count = m.group(0).count("\n")
            return f"__MASKED_CODE_{idx}__" + ("\n" * nl_count)

        masked_body = re.compile(
            r"(?ms)^[ \t]*(`{3,})[^\n]*\n.*?^[ \t]*\1[ \t]*(?:\n|$)"
        ).sub(_mask_code, body)

        inline_spans: list[str] = []

        def _mask_inline(m: re.Match[str]) -> str:
            idx = len(inline_spans)
            inline_spans.append(m.group(0))
            return f"__MASKED_INLINE_{idx}__"

        masked_body = re.sub(r"`[^`\n]+`", _mask_inline, masked_body)

        # Map 0-indexed end_line -> 0-indexed start_line for multi-line JSX blocks
        # where leading blank lines are placed above the synthesized Markdown line.
        multiline_jsx_start_map: dict[int, int] = {}

        def _place_at_block_end(
            full_match: str, replacement: str, match_start_offset: int
        ) -> str:
            orig_newlines = full_match.count("\n")
            rep_newlines = replacement.count("\n")
            if orig_newlines > rep_newlines:
                pad = orig_newlines - rep_newlines
                block_start_0 = masked_body[:match_start_offset].count("\n")
                first_synthesized_0 = block_start_0 + pad
                multiline_jsx_start_map[first_synthesized_0] = block_start_0
                return ("\n" * pad) + replacement
            return replacement

        # 4. Normalize themed <Image ... />, <Video ... />, and <FixCardGrid> blocks
        # placing synthesized Markdown at the bottom of the multi-line span so AST end_line
        # matches the closing JSX tag line 1:1.
        def _replace_image_block(match: re.Match[str]) -> str:
            full_match = match.group(0)
            alt_m = re.search(r'alt=["\']([^"\']*)["\']', full_match)
            prop_caption_m = re.search(r'caption=["\']([^"\']*)["\']', full_match)
            span_caption_m = re.search(r"<span[^>]*>(.*?)</span>", full_match, re.DOTALL)

            alt = (
                alt_m.group(1)
                if alt_m
                else (prop_caption_m.group(1) if prop_caption_m else "Diagram")
            )
            src_m = re.search(r'src(?:Light)?=["\']([^"\']+)["\']', full_match)
            if not src_m:
                src_m = re.search(r'srcDark=["\']([^"\']+)["\']', full_match)
            src = src_m.group(1) if src_m else ""

            caption = ""
            if span_caption_m:
                caption = span_caption_m.group(1).strip()
            elif prop_caption_m and alt_m:
                caption = prop_caption_m.group(1).strip()

            replacement_parts = [f"![{alt}]({src})"]
            if caption:
                replacement_parts.append(f"*{caption}*")
            replacement = "\n".join(replacement_parts)
            return _place_at_block_end(full_match, replacement, match.start())

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

        def _replace_video_block(match: re.Match[str]) -> str:
            full_match = match.group(0)
            cap_m = re.search(r'caption=["\']([^"\']*)["\']', full_match)
            src_m = re.search(r'src=["\']([^"\']+)["\']', full_match)
            caption = cap_m.group(1) if cap_m else "Video"
            src = src_m.group(1) if src_m else ""
            replacement = f"![Video: {caption}]({src})"
            return _place_at_block_end(full_match, replacement, match.start())

        masked_body = re.sub(
            r"(?s)<Video\b[^>]*/>",
            _replace_video_block,
            masked_body,
        )

        def _replace_fixcard_grid(match: re.Match[str]) -> str:
            full_match = match.group(0)
            cards: list[str] = []
            for card_m in re.finditer(r"(?s)<FixCard\b(.*?)/>", full_match):
                props = card_m.group(1)
                title_m = re.search(r'title=["\']([^"\']+)["\']', props)
                href_m = re.search(r'href=["\']([^"\']+)["\']', props)
                if title_m and href_m:
                    cards.append(f"- **Fix — [{title_m.group(1)}]({href_m.group(1)})**")
                elif title_m:
                    cards.append(f"- **Fix — {title_m.group(1)}**")
            replacement = "\n".join(cards) if cards else " "
            return _place_at_block_end(full_match, replacement, match.start())

        masked_body = re.sub(
            r"(?s)<FixCardGrid>.*?</FixCardGrid>",
            _replace_fixcard_grid,
            masked_body,
        )

        # 5. Convert inline semantic status icons (<Check />, <Cross />) and <summary> tags
        masked_body = re.sub(r"<Check\b[^>]*/>", "✓", masked_body)
        masked_body = re.sub(r"<Cross\b[^>]*/>", "✗", masked_body)

        def _replace_summary(m: re.Match[str]) -> str:
            inner = m.group(1).strip()
            nl_count = m.group(0).count("\n")
            return f"**{inner}**" + ("\n" * nl_count)

        masked_body = re.sub(
            r"(?s)<summary[^>]*>(.*?)</summary>", _replace_summary, masked_body
        )

        # 6. Unwrap remaining JSX/HTML container tags (including self-closing <br/>) with space padding
        def _unwrap_tag(m: re.Match[str]) -> str:
            nl_count = m.group(0).count("\n")
            return " " + ("\n" * nl_count)

        unwrapped = re.sub(
            r"</?[a-zA-Z][a-zA-Z0-9_:-]*(?:\s+[^>]*?)?\s*/?>",
            _unwrap_tag,
            masked_body,
        )

        # Restore inline spans prior to prose whitespace normalization
        for idx, span in enumerate(inline_spans):
            unwrapped = unwrapped.replace(f"__MASKED_INLINE_{idx}__", span)

        # Collapse multi-spaces on prose lines BEFORE restoring fenced code blocks
        # so code block indentation remains 100% intact.
        norm_lines = [
            re.sub(r"[ \t]+", " ", l) if l.strip() else " "
            for l in unwrapped.split("\n")
        ]
        unwrapped_norm = "\n".join(norm_lines)

        # Restore fenced code blocks verbatim
        for idx, block in enumerate(code_blocks):
            nl_count = block.count("\n")
            pattern = rf"__MASKED_CODE_{idx}__(?:\n[ \t]*){{{nl_count}}}"
            unwrapped_norm = re.sub(
                pattern, lambda _, b=block: b, unwrapped_norm, count=1
            )

        clean_text = unwrapped_norm
        assert len(clean_text.splitlines()) == total_lines, (
            f"Line count invariant violation: clean_text has {len(clean_text.splitlines())} lines, "
            f"raw content has {total_lines} lines."
        )

        return clean_text, title, meta, line_router, multiline_jsx_start_map

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
        slug = self.resolve_doc_slug(
            resolved_path, doc_slug=doc_slug, corpus_root=corpus_root
        )
        return self.parse_text(raw_content, doc_slug=slug)

    def _merge_paired_codemod_headings(self, node: _SectionNode) -> None:
        """Merges H4 (description) + sole H5 (`codemod-slug`) pairs in codemods documentation
        so the descriptive H4 heading and its line span stay attached to the codemod chunk
        and the resulting ltree path is a direct child of the H3 version node.
        """
        merged_children: list[_SectionNode] = []
        used_labels: set[str] = set()
        for child in node.children:
            self._merge_paired_codemod_headings(child)
            if (
                child.level == 4
                and len(child.children) == 1
                and child.children[0].level == 5
                and _CODEMOD_SLUG_REGEX.match(child.children[0].title.strip())
            ):
                h5_node = child.children[0]
                prefix_lines = [f"#### {child.title}"]
                if child.blocks:
                    prefix_lines.append(
                        "\n\n".join(b.text for b in child.blocks if b.text.strip())
                    )
                h5_node.paired_heading_prefix = "\n\n".join(prefix_lines)
                h5_node.start_line = min(child.start_line, h5_node.start_line)
                slug_label = _disambiguate_label(
                    h5_node.title, used_labels, router=h5_node.router
                )
                h5_node.path = validate_ltree_path(f"{node.path}.{slug_label}")
                h5_node.breadcrumbs = [
                    *node.breadcrumbs,
                    f"{child.title} ({h5_node.title})",
                ]
                merged_children.append(h5_node)
            else:
                used_labels.add(child.path.split(".")[-1])
                merged_children.append(child)
        node.children = merged_children

    def _emit_section_chunks(
        self,
        sec: _SectionNode,
        has_children: bool,
        used_paths: set[str],
    ) -> list[ParsedChunkDraft]:
        """Emits one cohesive chunk for the section if it has non-empty body blocks."""
        non_empty_blocks = [b for b in sec.blocks if b.text.strip()]
        if not non_empty_blocks:
            return []

        base_path = sec.path
        effective_breadcrumbs = list(sec.breadcrumbs)
        if sec.level == 0 and has_children:
            overview_candidate = validate_ltree_path(f"{sec.path}.overview")
            child_paths = {c.path for c in sec.children}
            if overview_candidate in child_paths or overview_candidate in used_paths:
                base_path = validate_ltree_path(f"{sec.path}.intro")
            else:
                base_path = overview_candidate
            effective_breadcrumbs.append("Overview")

        while base_path in used_paths:
            base_path = validate_ltree_path(f"{base_path}_2")
        used_paths.add(base_path)

        # Assemble blocks, inserting **[App Router]** / **[Pages Router]** markers when
        # a section body contains a mix of router scopes (e.g., shared intro + <AppOnly> + <PagesOnly>).
        block_router_states = {b.router for b in non_empty_blocks}
        effective_sec_router = sec.router
        if effective_sec_router is None and len(block_router_states) == 1:
            sole_router = next(iter(block_router_states))
            if sole_router in ("app", "pages"):
                effective_sec_router = sole_router

        annotate_inline_routers = len(block_router_states) > 1
        assembled_parts: list[str] = []
        current_router: str | None = effective_sec_router
        for b in non_empty_blocks:
            if annotate_inline_routers and b.router != current_router:
                if b.router == "app":
                    assembled_parts.append("**[App Router]**")
                elif b.router == "pages":
                    assembled_parts.append("**[Pages Router]**")
                current_router = b.router
            assembled_parts.append(b.text)

        body_text = "\n\n".join(assembled_parts).strip()
        if not body_text:
            return []

        if sec.level > 0:
            hashes = "#" * sec.level
            heading_header = f"{hashes} {sec.title}"
            if sec.paired_heading_prefix:
                heading_header = f"{sec.paired_heading_prefix}\n\n{heading_header}"
            if not body_text.startswith("#"):
                full_verbatim = f"{heading_header}\n\n{body_text}"
            else:
                full_verbatim = body_text
            part_start = min(sec.start_line, non_empty_blocks[0].start_line)
        else:
            if not body_text.startswith("#"):
                full_verbatim = f"# {sec.title}\n\n{body_text}"
            else:
                full_verbatim = body_text
            part_start = (
                sec.start_line
                if sec.start_line > 0
                else non_empty_blocks[0].start_line
            )

        part_end = max(sec.end_line, non_empty_blocks[-1].end_line, part_start)
        bc_prefix = f"[{' > '.join(effective_breadcrumbs)}]\n"

        node_type = "OVERVIEW" if (sec.level == 0 and has_children) else "SECTION"
        chunk_meta: dict[str, object] = {
            "heading": sec.title,
            "node_type": node_type,
            "framework": "nextjs",
            "has_code": "```" in full_verbatim,
            "has_table": "|" in full_verbatim,
            "ancestor_titles": effective_breadcrumbs,
        }
        if effective_sec_router in ("app", "pages"):
            chunk_meta["router"] = effective_sec_router

        return [
            ParsedChunkDraft(
                path=base_path,
                verbatim_text=full_verbatim,
                contextualized_text=f"{bc_prefix}{full_verbatim}",
                start_line=part_start,
                end_line=part_end,
                metadata=chunk_meta,
            )
        ]

    def parse_text(
        self,
        raw_content: str,
        doc_slug: str,
        title: str | None = None,
    ) -> ParsedDocumentDraft:
        """Parses raw text of Next.js documentation into ParsedDocumentDraft with Section-Level chunks."""
        slug = canonicalize_ltree_path(doc_slug)
        (
            clean_text,
            fm_title,
            fm_meta,
            line_router,
            multiline_jsx_start_map,
        ) = self._sanitize_nextjs_content(raw_content)

        total_lines = len(raw_content.splitlines())
        if not clean_text.strip():
            return ParsedDocumentDraft(
                doc_slug=slug,
                title=title or fm_title or "",
                raw_text=raw_content,
                chunks=[],
                edges=[],
                metadata={
                    "total_lines": total_lines,
                    "format_type": "nextjs_mdx",
                    "framework": "nextjs",
                    **fm_meta,
                },
            )

        tokens = self._md.parse(clean_text)
        syntax_tree = SyntaxTreeNode(tokens)

        effective_title = title or fm_title
        if not effective_title:
            for child in syntax_tree.children:
                if child.type == "heading" and child.tag in ("h1", "h2"):
                    effective_title = "".join(
                        c.content for c in child.children
                    ).strip()
                    break
        effective_title = effective_title or "Documentation"

        clean_lines = clean_text.splitlines()

        root_section = _SectionNode(
            level=0,
            title=effective_title,
            path=slug,
            breadcrumbs=[effective_title],
            start_line=0,
            end_line=0,
            router=None,
        )

        # Stack holds (level, _SectionNode, used_child_labels)
        stack: list[tuple[int, _SectionNode, set[str]]] = [
            (0, root_section, set())
        ]
        bound_primary_h1 = False

        for node in syntax_tree.children:
            if node.type == "heading":
                h_level = (
                    int(node.tag[1])
                    if len(node.tag) > 1 and node.tag[1].isdigit()
                    else 1
                )
                h_title = (
                    "".join(c.content for c in node.children).strip() or "Section"
                )
                h_start = node.map[0] + 1 if node.map else 1
                h_end = node.map[1] if node.map else h_start
                h_router = (
                    line_router[h_start - 1]
                    if 1 <= h_start <= len(line_router)
                    else None
                )

                # If a synthetic document starts with an H1 matching the document root before any children,
                # bind it to root_section so we do not duplicate the root segment.
                if (
                    h_level == 1
                    and not bound_primary_h1
                    and len(stack) == 1
                    and not root_section.children
                    and not root_section.blocks
                ):
                    bound_primary_h1 = True
                    root_section.title = h_title
                    root_section.breadcrumbs = [h_title]
                    root_section.start_line = h_start
                    root_section.end_line = max(root_section.end_line, h_end)
                    continue

                while len(stack) > 1 and stack[-1][0] >= h_level:
                    stack.pop()

                _, parent_node, child_labels = stack[-1]
                slug_label = _disambiguate_label(
                    h_title, child_labels, router=h_router
                )
                new_path = validate_ltree_path(f"{parent_node.path}.{slug_label}")

                new_breadcrumbs = list(parent_node.breadcrumbs)
                bc_label = h_title
                if (
                    h_router in ("app", "pages")
                    and parent_node.router != h_router
                ):
                    router_tag = (
                        "App Router" if h_router == "app" else "Pages Router"
                    )
                    bc_label = f"{h_title} ({router_tag})"

                # Always append one breadcrumb per ltree segment so PARENT_CHAIN virtual
                # ancestor reconstruction maps 1:1 with ltree depth.
                new_breadcrumbs.append(bc_label)

                new_section = _SectionNode(
                    level=h_level,
                    title=h_title,
                    path=new_path,
                    breadcrumbs=new_breadcrumbs,
                    start_line=h_start,
                    end_line=h_end,
                    router=h_router,
                )
                parent_node.children.append(new_section)
                stack.append((h_level, new_section, set()))
                continue

            if node.map:
                s_0, e_0 = node.map
                active_node = stack[-1][1]
                # Trim trailing blank lines included by CommonMark list tokens so end_line
                # lands on the exact last content line in raw_text.
                trimmed_e_0 = e_0
                while (
                    trimmed_e_0 > s_0 + 1
                    and not clean_lines[trimmed_e_0 - 1].strip()
                ):
                    trimmed_e_0 -= 1
                node_text = "\n".join(clean_lines[s_0:trimmed_e_0]).strip()
                if node_text:
                    true_s_0 = multiline_jsx_start_map.get(s_0, s_0)
                    block_start = true_s_0 + 1
                    block_end = trimmed_e_0
                    block_router = (
                        line_router[true_s_0]
                        if 0 <= true_s_0 < len(line_router)
                        else None
                    )
                    if (
                        not active_node.blocks
                        and active_node.level == 0
                        and active_node.start_line == 0
                    ):
                        active_node.start_line = block_start
                    active_node.blocks.append(
                        _BlockItem(
                            text=node_text,
                            start_line=block_start,
                            end_line=block_end,
                            router=block_router,
                        )
                    )
                    active_node.end_line = max(active_node.end_line, block_end)

        # Merge paired H4 (description) + H5 (`codemod-slug`) headings in codemods.mdx
        self._merge_paired_codemod_headings(root_section)

        # Traverse section tree in document order and emit atomic section chunks
        chunks: list[ParsedChunkDraft] = []
        used_paths: set[str] = set()

        def _walk(node: _SectionNode) -> None:
            chunks.extend(
                self._emit_section_chunks(
                    node,
                    has_children=bool(node.children),
                    used_paths=used_paths,
                )
            )
            for child in node.children:
                _walk(child)

        _walk(root_section)
        chunks.sort(key=lambda c: (c.start_line, c.path))

        doc_meta = dict(fm_meta)
        doc_meta["total_lines"] = total_lines
        doc_meta["format_type"] = "nextjs_mdx"
        doc_meta["framework"] = "nextjs"
        doc_meta["chunks_count"] = len(chunks)

        return ParsedDocumentDraft(
            doc_slug=slug,
            title=effective_title,
            raw_text=raw_content,
            chunks=chunks,
            edges=[],
            metadata=doc_meta,
        )
