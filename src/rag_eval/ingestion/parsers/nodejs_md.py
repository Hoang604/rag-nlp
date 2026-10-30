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

NODEJS_CONTENT_MARKER_REGEX = re.compile(
    r"<!--\s*(?:YAML\b|introduced_in=|source_link=|name=|type=|STABILITY_OVERVIEW)|^>\s*Stability:\s*\d",
    re.MULTILINE,
)

_INTRODUCED_IN_REGEX = re.compile(r"<!--\s*introduced_in\s*=\s*([^\s>-]+)\s*-->")
_SOURCE_LINK_REGEX = re.compile(r"<!--\s*source_link\s*=\s*([^\s>-]+)\s*-->")
_MODULE_NAME_REGEX = re.compile(r"<!--\s*name\s*=\s*([^\s>-]+)\s*-->")
_STABILITY_LINE_REGEX = re.compile(
    r"^>\s*Stability:\s*([0-9]+(?:\.[0-9]+)?)\s*(?:-\s*(.+))?$",
    re.MULTILINE,
)
_EMPTY_ANCHOR_TAG_REGEX = re.compile(
    r"<a\b[^>]*\b(?:id|name)\s*=\s*[\"'][^\"']*[\"'][^>]*>\s*</a>",
    re.IGNORECASE | re.DOTALL,
)


_SYMBOLIC_LABEL_MAP: dict[str, str] = {
    "-": "dash",
    "--": "double_dash",
}


def _disambiguate_label(candidate: str, used_labels: set[str]) -> str:
    """Ensures label is unique among sibling nodes under the same parent."""
    unquoted = candidate.strip().strip("`").strip()
    if unquoted in _SYMBOLIC_LABEL_MAP:
        clean = _SYMBOLIC_LABEL_MAP[unquoted]
    else:
        try:
            clean = sanitize_ltree_label(candidate)
        except ValueError:
            clean = "section"
    if clean not in used_labels:
        used_labels.add(clean)
        return clean

    counter = 1
    while f"{clean}_{counter}" in used_labels:
        counter += 1
    unique_label = f"{clean}_{counter}"
    used_labels.add(unique_label)
    return unique_label


def _extract_yaml_versions(yaml_block: str, key: str) -> str:
    """Extracts version scalar or list for 'added' or 'deprecated' from a Node.js YAML comment block."""
    pattern = re.compile(
        rf"^{key}:[ \t]*(?:([^-\s\n][^\n]*)|(?:\n((?:[ \t]*-[ \t]*[^\n]+\n?)+)))",
        re.MULTILINE,
    )
    match = pattern.search(yaml_block)
    if not match:
        return ""
    inline_val = (match.group(1) or "").strip()
    if inline_val:
        return inline_val
    list_block = match.group(2) or ""
    versions = [
        line.strip().lstrip("-").strip()
        for line in list_block.splitlines()
        if line.strip().startswith("-")
    ]
    return ", ".join(v for v in versions if v)


def _strip_metadata_lines(text: str) -> str:
    """Returns text with headings, Added/Deprecated badges, multi-line Stability callouts, and bare Extends removed."""
    meaningful: list[str] = []
    in_stability_blockquote = False
    for raw_line in text.splitlines():
        s = raw_line.strip()
        if not s:
            in_stability_blockquote = False
            continue
        if s.startswith("> Stability:"):
            in_stability_blockquote = True
            continue
        if in_stability_blockquote and s.startswith(">"):
            continue
        in_stability_blockquote = False
        if s.startswith(("#", "*Added in:", "*Deprecated in:", "* Extends:")):
            continue
        meaningful.append(s)
    return "\n".join(meaningful).strip()


_CALLABLE_NAME_REGEX = re.compile(
    r"^(?:`(?:Static method:\s*)?(new\s+[A-Za-z0-9_.$]+|[A-Za-z0-9_.$]+)\s*\(|(?:Static method:\s*`?)?(new\s+[A-Za-z0-9_.$]+)\s*\(|Static method:\s*`?([A-Za-z0-9_.$]+)\s*\()"
)
_CALLABLE_PARAM_TOKEN_REGEX = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")
_STANDALONE_CODE_HEADING_REGEX = re.compile(r"^`[^`]+`(?:\s*,\s*`[^`]+`)*(?:\s+and\s+`[^`]+`)?$")


def _extract_callable_name(title: str) -> str | None:
    """Extracts the canonical callable name from a function, method, or constructor heading."""
    m = _CALLABLE_NAME_REGEX.match(title.strip())
    if not m:
        return None
    raw_name = m.group(1) or m.group(2) or m.group(3) or ""
    return re.sub(r"\s+", " ", raw_name.strip())


def _extract_callable_params(title: str) -> set[str]:
    """Extracts parameter identifier names from inside the parentheses of a callable heading."""
    s = title.strip()
    open_idx = s.find("(")
    close_idx = s.rfind(")")
    if open_idx == -1 or close_idx <= open_idx:
        return set()
    params_str = s[open_idx + 1 : close_idx]
    return set(_CALLABLE_PARAM_TOKEN_REGEX.findall(params_str))


def _is_leaf_api_entry_heading(title: str) -> bool:
    """Returns True if a heading represents a concrete API entry (callable, event, or non-constants property)
    whose prose/parameter sub-headings belong inside the entry's own chunk.
    """
    s = title.strip()
    if s.startswith(("Class:", "Class ")) or " extends `" in s:
        return False
    if s.startswith(("Event:", "Static method:")):
        return True
    if _extract_callable_name(s) is not None:
        return True
    if _STANDALONE_CODE_HEADING_REGEX.match(s):
        unquoted = s.strip("`").strip()
        # '*.constants' objects (e.g. fs.constants, sqlite.constants) act as containers for constant tables
        return not unquoted.endswith(".constants")
    return False


def _is_independent_api_child_heading(child_title: str, parent_api_title: str) -> bool:
    """Determines whether a heading nested under an API entry is itself an independent API unit
    (e.g., `util.inspect.custom` under `util.inspect(...)`, `server.listen(path...)` under `server.listen()`)
    rather than an internal parameter explanation or prose caveat/example sub-section.
    """
    s = child_title.strip()
    if s.startswith(("Class:", "Class ", "Event:", "Static method:", "DEP0", "ERR_", "`ERR_", "`-")):
        return True
    if _extract_callable_name(s) is not None:
        return True
    if _STANDALONE_CODE_HEADING_REGEX.match(s):
        symbol = s.strip("`").strip()
        # Check if symbol is just documenting a parameter (or field of a parameter) of parent_api_title
        # e.g. `type`, `triggerAsyncId` under `init(asyncId, type, triggerAsyncId, resource)`
        # or `options.detached`, `options.stdio` under `child_process.spawn(command[, args][, options])`
        parent_params = _extract_callable_params(parent_api_title)
        root_ident = symbol.split(".", 1)[0].split("[", 1)[0]
        return root_ident not in parent_params
    return False


class _BlockItem:
    """Represents an atomic AST block with 1-indexed line bounds."""

    __slots__ = ("end_line", "start_line", "text")

    def __init__(self, start_line: int, end_line: int, text: str) -> None:
        self.start_line = start_line
        self.end_line = end_line
        self.text = text


class _SectionNode:
    """Hierarchical section builder node for Node.js Markdown AST."""

    def __init__(
        self,
        level: int,
        title: str,
        path: str,
        breadcrumbs: list[str],
        start_line: int,
        end_line: int,
        parent: _SectionNode | None = None,
    ) -> None:
        self.level = level
        self.title = title
        self.path = path
        self.breadcrumbs = breadcrumbs
        self.start_line = start_line
        self.end_line = end_line
        self.parent = parent
        self.blocks: list[_BlockItem] = []
        self.overloaded_headings: list[str] = []
        self.children: list[_SectionNode] = []
        self.stability: str | None = None

    def has_meaningful_prose(self) -> bool:
        body = "\n\n".join(b.text for b in self.blocks if b.text.strip()).strip()
        return bool(_strip_metadata_lines(body))


class NodeJSMarkdownParser(BaseCodingParser):
    """Dedicated Section-Level parser for Node.js official API technical documentation (.md).

    Enforces:
    1. Framework Namespace Isolation: Canonicalizes document slugs under 'nodejs.*'
       and prefixes contextualized breadcrumbs with 'Node.js'.
    2. YAML Comment Metadata Synthesis & Anchor Cleanup: Extracts 'added', 'deprecated',
       'introduced_in', 'source_link', and 'stability' metadata while stripping empty
       HTML anchor tags (<a id="..."></a>) and preserving exact 1:1 line mapping.
    3. Pure Semantic AST Chunking:
       - Binds primary H1 to the document root (preventing duplicate 'nodejs.mod.mod' paths).
       - Merges consecutive empty same-level headings only when they are overloaded signatures
         of the same callable, discarding empty placeholder/flag headings.
       - Keeps internal parameter/caveat/example sub-headings inside their parent API entry while
         preserving independent child APIs at any heading depth (H2..H6).
       - Suppresses metadata-only container nodes from emitting empty chunks.
    """

    name: str = "nodejs_md"
    framework_prefix: str = "nodejs"

    def __init__(self) -> None:
        self._md = MarkdownIt("commonmark").enable("table")

    def can_handle(self, file_path: Path, raw_text: str = "") -> bool:
        """Matches Node.js Markdown documentation files by corpus path or Node.js API markers."""
        suffix = Path(file_path).suffix.lower()
        if suffix not in (".md", ".markdown"):
            return False

        parts_lower = {p.lower() for p in Path(file_path).parts}
        if "nodejs" in parts_lower or "node_docs" in parts_lower:
            return True

        return bool(raw_text and NODEJS_CONTENT_MARKER_REGEX.search(raw_text))

    def _sanitize_nodejs_content(self, content: str) -> tuple[str, dict[str, object]]:
        """Extracts Node.js HTML comment metadata and normalizes YAML blocks preserving 1:1 line count."""
        meta: dict[str, object] = {}

        intro_m = _INTRODUCED_IN_REGEX.search(content)
        if intro_m:
            meta["introduced_in"] = intro_m.group(1)

        src_m = _SOURCE_LINK_REGEX.search(content)
        if src_m:
            meta["source_link"] = src_m.group(1)

        name_m = _MODULE_NAME_REGEX.search(content)
        if name_m:
            meta["module_name"] = name_m.group(1)

        lines = content.splitlines()
        if not lines:
            return "", meta

        # Mask code fences to avoid touching HTML comments or tags inside code examples
        code_blocks: list[str] = []

        def _mask_code(m: re.Match[str]) -> str:
            idx = len(code_blocks)
            code_blocks.append(m.group(0))
            nl_count = m.group(0).count("\n")
            return f"__MASKED_NODE_CODE_{idx}__" + ("\n" * nl_count)

        masked_body = re.compile(r"(?ms)^```[^\n]*\n.*?^```(?:\n|$)").sub(_mask_code, content)

        # Convert <!-- YAML ... --> blocks into concise version line + blank lines preserving exact line count
        def _replace_yaml_comment(m: re.Match[str]) -> str:
            full_comment = m.group(0)
            inner_yaml = m.group(1)
            nl_count = full_comment.count("\n")

            added_str = _extract_yaml_versions(inner_yaml, "added")
            deprecated_str = _extract_yaml_versions(inner_yaml, "deprecated")

            badges: list[str] = []
            if added_str:
                badges.append(f"Added in: {added_str}")
            if deprecated_str:
                badges.append(f"Deprecated in: {deprecated_str}")

            first_line = f"*{' — '.join(badges)}*" if badges else " "
            return first_line + ("\n " * nl_count)

        masked_body = re.sub(
            r"<!--\s*YAML\s*\n(.*?)-->",
            _replace_yaml_comment,
            masked_body,
            flags=re.DOTALL,
        )

        # Blank all remaining HTML comments (linter directives, slot markers, etc.) preserving line count
        def _blank_span(m: re.Match[str]) -> str:
            nl_count = m.group(0).count("\n")
            return " " + ("\n " * nl_count)

        masked_body = re.sub(r"<!--.*?-->", _blank_span, masked_body, flags=re.DOTALL)

        # Blank standalone empty HTML anchor tags (<a id="..."></a>) so they don't bleed into preceding chunks
        masked_body = _EMPTY_ANCHOR_TAG_REGEX.sub(_blank_span, masked_body)

        # Restore code blocks verbatim
        for idx, block in enumerate(code_blocks):
            nl_count = block.count("\n")
            masked_body = masked_body.replace(
                f"__MASKED_NODE_CODE_{idx}__" + ("\n" * nl_count),
                block,
            )

        clean_lines = [line if line.strip() else " " for line in masked_body.splitlines()]
        clean_text = "\n".join(clean_lines)

        assert len(clean_text.splitlines()) == len(lines), (
            f"Line count invariant violation: clean_text has {len(clean_text.splitlines())} lines, "
            f"raw content has {len(lines)} lines."
        )

        return clean_text, meta

    def parse(
        self,
        file_path: Path,
        doc_slug: str | None = None,
        corpus_root: Path | None = None,
    ) -> ParsedDocumentDraft:
        """Parses Node.js Markdown documentation file into ParsedDocumentDraft with Section-Level chunks."""
        resolved_path = Path(file_path).resolve()
        if not resolved_path.exists() or not resolved_path.is_file():
            raise CorpusDomainError(
                error_code=E_CORPUS_INTEGRITY_VIOLATION,
                message=f"File '{file_path}' does not exist or is not a readable file.",
                data={"path": str(file_path)},
            )

        raw_content = resolved_path.read_text("utf-8", errors="replace")
        slug = self.resolve_doc_slug(resolved_path, doc_slug=doc_slug, corpus_root=corpus_root)
        return self.parse_text(raw_content, doc_slug=slug)

    def _prune_metadata_only_containers_and_empty_leaves(
        self,
        node: _SectionNode,
        inherited_stability: str | None = None,
    ) -> None:
        """Propagates stability down the section tree, removes empty leaf headings,
        and clears metadata-only blocks on internal container nodes.
        """
        own_body = "\n\n".join(b.text for b in node.blocks if b.text.strip())
        stab_m = _STABILITY_LINE_REGEX.search(own_body)
        node.stability = stab_m.group(1) if stab_m else inherited_stability

        kept_children: list[_SectionNode] = []
        for child in node.children:
            self._prune_metadata_only_containers_and_empty_leaves(
                child,
                inherited_stability=node.stability,
            )
            if not child.children and not child.has_meaningful_prose():
                continue
            kept_children.append(child)
        node.children = kept_children

        if node.children and not node.has_meaningful_prose():
            node.blocks = []

    def _emit_section_chunks(
        self,
        sec: _SectionNode,
        has_children: bool,
        used_paths: set[str],
    ) -> list[ParsedChunkDraft]:
        """Emits one atomic cohesive chunk per heading section."""
        non_empty_blocks = [b for b in sec.blocks if b.text.strip()]
        if not non_empty_blocks:
            return []

        base_path = sec.path
        if sec.level == 0 and has_children:
            overview_candidate = validate_ltree_path(f"{sec.path}.overview")
            child_paths = {c.path for c in sec.children}
            if overview_candidate in child_paths or overview_candidate in used_paths:
                base_path = validate_ltree_path(f"{sec.path}.intro")
            else:
                base_path = overview_candidate

        while base_path in used_paths:
            base_path = validate_ltree_path(f"{base_path}_2")
        used_paths.add(base_path)

        body_text = "\n\n".join(b.text for b in non_empty_blocks).strip()
        if not body_text:
            return []

        if not body_text.startswith("#"):
            heading_lines = [f"## {ov}" for ov in sec.overloaded_headings]
            heading_lines.append(f"## {sec.title}")
            full_verbatim = "\n".join(heading_lines) + f"\n\n{body_text}"
        else:
            full_verbatim = body_text

        bc_prefix = f"[{' > '.join(sec.breadcrumbs)}]\n"
        part_start = sec.start_line if sec.start_line > 0 else non_empty_blocks[0].start_line
        part_end = max(sec.end_line, non_empty_blocks[-1].end_line, part_start)

        chunk_meta: dict[str, object] = {
            "heading": sec.title,
            "node_type": "SECTION",
            "framework": "nodejs",
            "has_code": "```" in full_verbatim,
            "has_table": "|" in full_verbatim,
            "ancestor_titles": sec.breadcrumbs,
        }
        stab_m = _STABILITY_LINE_REGEX.search(full_verbatim)
        effective_stability = stab_m.group(1) if stab_m else sec.stability
        if effective_stability:
            chunk_meta["stability"] = effective_stability

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
        """Parses raw text of Node.js documentation into ParsedDocumentDraft with Section-Level chunks."""
        slug = canonicalize_ltree_path(doc_slug)
        clean_text, doc_comment_meta = self._sanitize_nodejs_content(raw_content)

        if not clean_text.strip():
            return ParsedDocumentDraft(
                doc_slug=slug,
                title=title or "",
                raw_text=raw_content,
                chunks=[],
                edges=[],
                metadata={
                    "total_lines": len(raw_content.splitlines()),
                    "format_type": "nodejs_md",
                    "framework": "nodejs",
                    **doc_comment_meta,
                },
            )

        tokens = self._md.parse(clean_text)
        syntax_tree = SyntaxTreeNode(tokens)

        effective_title = title or ""
        if not effective_title:
            for child in syntax_tree.children:
                if child.type == "heading" and child.tag in ("h1", "h2"):
                    effective_title = "".join(c.content for c in child.children).strip()
                    break
        effective_title = effective_title or "Node.js Documentation"

        raw_lines = clean_text.splitlines()

        root_breadcrumbs = ["Node.js"]
        if effective_title.lower() != "node.js":
            root_breadcrumbs.append(effective_title)

        root_section = _SectionNode(
            level=0,
            title=effective_title,
            path=slug,
            breadcrumbs=root_breadcrumbs,
            start_line=1,
            end_line=1,
        )

        # Stack holds (level, _SectionNode, used_child_labels)
        stack: list[tuple[int, _SectionNode, set[str]]] = [(0, root_section, set())]
        bound_primary_h1 = False

        for node in syntax_tree.children:
            if node.type == "heading":
                h_level = int(node.tag[1]) if len(node.tag) > 1 and node.tag[1].isdigit() else 1
                h_title = "".join(c.content for c in node.children).strip() or "Section"
                h_start = node.map[0] + 1 if node.map else 1
                h_end = node.map[1] if node.map else h_start

                # Bind the primary H1 heading directly to root_section to avoid duplicate H1 paths (e.g. nodejs.zlib.zlib)
                if h_level == 1 and not bound_primary_h1 and len(stack) == 1 and not root_section.children:
                    bound_primary_h1 = True
                    root_section.title = h_title
                    root_section.start_line = h_start
                    root_section.end_line = max(root_section.end_line, h_end)
                    continue

                # Check if top of stack is an empty section at the exact same level:
                # Merge as overloaded heading ONLY when both share the same callable name;
                # otherwise discard the empty leaf heading (e.g. empty V8 flag headings in cli.md).
                carried_overloads: list[str] = []
                carried_start_line: int | None = None
                if (
                    len(stack) > 1
                    and stack[-1][0] == h_level
                    and not stack[-1][1].blocks
                    and not stack[-1][1].children
                ):
                    _, empty_same_lvl, _ = stack.pop()
                    if empty_same_lvl.parent and empty_same_lvl in empty_same_lvl.parent.children:
                        empty_same_lvl.parent.children.remove(empty_same_lvl)
                    prev_callable = _extract_callable_name(empty_same_lvl.title)
                    curr_callable = _extract_callable_name(h_title)
                    if prev_callable is not None and prev_callable == curr_callable:
                        carried_overloads = [*empty_same_lvl.overloaded_headings, empty_same_lvl.title]
                        carried_start_line = empty_same_lvl.start_line

                while len(stack) > 1 and stack[-1][0] >= h_level:
                    stack.pop()

                # If the parent section on the stack is a concrete API entry (callable, event, or non-constants property)
                # and this sub-heading is an internal parameter/caveat/example sub-section rather than an independent API unit,
                # keep it inside the parent API entry only when the parent has not already emitted independent child sections.
                _, parent_sec, child_labels = stack[-1]
                if (
                    parent_sec.level > 0
                    and not parent_sec.children
                    and _is_leaf_api_entry_heading(parent_sec.title)
                    and not _is_independent_api_child_heading(h_title, parent_sec.title)
                ):
                    sub_h_prefix = "#" * min(h_level, 6)
                    parent_sec.blocks.append(_BlockItem(h_start, h_end, f"{sub_h_prefix} {h_title}"))
                    parent_sec.end_line = max(parent_sec.end_line, h_end)
                    continue
                slug_label = _disambiguate_label(h_title, child_labels)
                new_path = validate_ltree_path(f"{parent_sec.path}.{slug_label}")
                new_breadcrumbs = list(parent_sec.breadcrumbs)
                if not new_breadcrumbs or new_breadcrumbs[-1].lower() != h_title.lower():
                    new_breadcrumbs.append(h_title)

                new_section = _SectionNode(
                    level=h_level,
                    title=h_title,
                    path=new_path,
                    breadcrumbs=new_breadcrumbs,
                    start_line=carried_start_line if carried_start_line is not None else h_start,
                    end_line=h_end,
                    parent=parent_sec,
                )
                new_section.overloaded_headings = carried_overloads
                parent_sec.children.append(new_section)
                stack.append((h_level, new_section, set()))
                continue

            if node.map:
                s_0, e_0 = node.map
                active_sec = stack[-1][1]
                node_text = "\n".join(raw_lines[s_0:e_0]).strip()
                if node_text:
                    if not active_sec.blocks and active_sec.level == 0 and not bound_primary_h1:
                        active_sec.start_line = s_0 + 1
                    active_sec.blocks.append(_BlockItem(s_0 + 1, e_0, node_text))
                    active_sec.end_line = max(active_sec.end_line, e_0)

        # Remove empty leaf headings and suppress metadata-only container nodes from emitting empty chunks
        self._prune_metadata_only_containers_and_empty_leaves(root_section)

        # Traverse section tree in pre-order (reading order) and emit chunks
        chunks: list[ParsedChunkDraft] = []
        used_paths: set[str] = set()

        def _walk(sec: _SectionNode) -> None:
            chunks.extend(self._emit_section_chunks(sec, has_children=bool(sec.children), used_paths=used_paths))
            for child in sec.children:
                _walk(child)

        _walk(root_section)
        chunks.sort(key=lambda c: (c.start_line, c.path))

        doc_meta = dict(doc_comment_meta)
        doc_meta["total_lines"] = len(raw_content.splitlines())
        doc_meta["format_type"] = "nodejs_md"
        doc_meta["framework"] = "nodejs"
        doc_meta["chunks_count"] = len(chunks)

        return ParsedDocumentDraft(
            doc_slug=slug,
            title=effective_title,
            raw_text=raw_content,
            chunks=chunks,
            edges=[],
            metadata=doc_meta,
        )
