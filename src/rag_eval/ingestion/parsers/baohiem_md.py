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

_TOP_LEVEL_YAML_KEY_REGEX = re.compile(r"^([a-zA-Z0-9_-]+)\s*:\s*(.*)$")
_CHAPTER_HEADING_REGEX = re.compile(r"^(Chương\s+[IVXLCDM0-9]+)\b", re.IGNORECASE)
_SECTION_HEADING_REGEX = re.compile(r"^(Mục\s+\d+)\b", re.IGNORECASE)
_SUBSECTION_HEADING_REGEX = re.compile(r"^(Tiểu\s+mục\s+\d+)\b", re.IGNORECASE)
_ARTICLE_HEADING_REGEX = re.compile(r"^(Điều\s+\d+[a-zđ]?)\b", re.IGNORECASE)
_BARE_SUBSECTION_LINE_REGEX = re.compile(
    r"^Tiểu\s+mục\s+(\d+)\b(?:\s*[:.]?\s*(.*))?$",
    re.IGNORECASE,
)

BAOHIEM_CONTENT_MARKER_REGEX = re.compile(
    r"(?:\A---\s*\n(?:[^\n]*\n)*?doc_code\s*:)|(?:^##\s+Chương\s+[IVXLCDM0-9]+\b.*?\n[\s\S]*?^####\s+Điều\s+\d+\.)",
    re.MULTILINE,
)


def _disambiguate_label(candidate: str, used_labels: set[str]) -> str:
    """Ensures ltree segment label is valid and unique among sibling nodes under the same parent."""
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


def _classify_statutory_heading(h_level: int, h_title: str) -> tuple[int, str, str]:
    """Maps a Vietnamese legal heading to (semantic_level, canonical_label_candidate, statutory_kind).

    Statutory hierarchy:
    - Chương (Chapter): semantic_level = 1, label = 'chuong_<roman>'
    - Mục (Section): semantic_level = 2, label = 'muc_<num>'
    - Tiểu mục (Sub-section): semantic_level = 3, label = 'tieu_muc_<num>'
    - Điều (Article): semantic_level = 4, label = 'dieu_<num>'
    """
    s = h_title.strip()
    m_chap = _CHAPTER_HEADING_REGEX.match(s)
    if m_chap:
        return 1, m_chap.group(1), "CHAPTER"

    m_sec = _SECTION_HEADING_REGEX.match(s)
    if m_sec:
        return 2, m_sec.group(1), "SECTION"

    m_sub = _SUBSECTION_HEADING_REGEX.match(s)
    if m_sub:
        return 3, m_sub.group(1), "SUBSECTION"

    m_art = _ARTICLE_HEADING_REGEX.match(s)
    if m_art:
        return 4, m_art.group(1), "ARTICLE"

    return h_level, s, "SECTION"


def _is_statutory_heading(h_title: str) -> bool:
    """Returns True if the heading is a statutory container or provision (Chương, Mục, Tiểu mục, Điều)."""
    s = h_title.strip()
    return bool(
        _CHAPTER_HEADING_REGEX.match(s)
        or _SECTION_HEADING_REGEX.match(s)
        or _SUBSECTION_HEADING_REGEX.match(s)
        or _ARTICLE_HEADING_REGEX.match(s)
    )


@dataclass
class _BlockItem:
    text: str
    start_line: int
    end_line: int


@dataclass
class _SectionNode:
    level: int
    raw_h_level: int
    title: str
    path: str
    breadcrumbs: list[str]
    statutory_kind: str
    start_line: int
    end_line: int
    blocks: list[_BlockItem] = field(default_factory=list)
    children: list[_SectionNode] = field(default_factory=list)

    def has_meaningful_prose(self) -> bool:
        return any(b.text.strip() for b in self.blocks)


class BaoHiemMarkdownParser(BaseCodingParser):
    """Dedicated parser for Vietnamese Insurance Law technical & regulatory documentation (.md).

    Enforces:
    1. Framework Namespace Isolation: Canonicalizes document slugs under 'baohiem.*'.
    2. Exact 1:1 Line Preservation: Extracts YAML frontmatter ('title', 'doc_code',
       'issued_date', 'source') and normalizes bare 'Tiểu mục <N>' headings in place
       without altering line counts or [start_line, end_line] spans against documents.raw_text.
    3. Statutory Hierarchy AST Decomposition:
       - Maps Chương (L1) -> Mục (L2) -> Tiểu mục (L3) -> Điều (L4) with canonical
         ltree segment labels ('chuong_i', 'muc_1', 'tieu_muc_1', 'dieu_1') while
         preserving full Vietnamese titles in breadcrumbs and metadata.
       - Suppresses empty structural containers (Chương, Mục, Tiểu mục) from emitting
         junk chunks while keeping their hierarchy intact for CHILDREN/SUBTREE/PARENT_CHAIN.
       - Emits one cohesive chunk per Điều (containing all internal Khoản and Điểm).
    """

    name: str = "baohiem_md"
    framework_prefix: str = "baohiem"

    def __init__(self) -> None:
        self._md = MarkdownIt("commonmark").enable("table")

    def can_handle(self, file_path: Path, raw_text: str = "") -> bool:
        """Matches Vietnamese Insurance Law Markdown files by corpus path or statutory markers."""
        suffix = Path(file_path).suffix.lower()
        if suffix not in (".md", ".markdown"):
            return False

        parts_lower = {p.lower() for p in Path(file_path).parts}
        if "baohiem" in parts_lower or "bao_hiem" in parts_lower:
            return True

        return bool(raw_text and BAOHIEM_CONTENT_MARKER_REGEX.search(raw_text))

    def _sanitize_baohiem_content(
        self, content: str
    ) -> tuple[str, str, dict[str, object]]:
        """Extracts YAML frontmatter and normalizes bare 'Tiểu mục <N>' headings while preserving 1:1 line count."""
        title = ""
        meta: dict[str, object] = {}
        raw_lines = content.splitlines()
        if not raw_lines:
            return "", "", meta

        lines = list(raw_lines)

        # 1. Extract top-level YAML frontmatter and blank frontmatter lines in place
        close_idx: int | None = None
        if lines and lines[0].strip() == "---":
            for i in range(1, len(lines)):
                if lines[i].strip() == "---":
                    close_idx = i
                    break
            if close_idx is not None:
                for line in lines[1:close_idx]:
                    top_m = _TOP_LEVEL_YAML_KEY_REGEX.match(line)
                    if top_m:
                        k_clean = top_m.group(1).strip().lower()
                        v_clean = top_m.group(2).strip().strip("\"'")
                        meta[k_clean] = v_clean
                        if k_clean == "title" and not title:
                            title = v_clean
                for i in range(close_idx + 1):
                    lines[i] = " "

        # 2. Convert bare "Tiểu mục <N>" (+ optional following ALL-CAPS title line) into ### headings in place
        in_code_fence = False
        i = 0
        while i < len(lines):
            stripped = lines[i].strip()
            if stripped.startswith("```"):
                in_code_fence = not in_code_fence
                i += 1
                continue
            if in_code_fence or not stripped:
                i += 1
                continue

            m_sub = _BARE_SUBSECTION_LINE_REGEX.match(stripped)
            if m_sub:
                sub_num = m_sub.group(1)
                inline_title = (m_sub.group(2) or "").strip()
                if inline_title:
                    lines[i] = f"### Tiểu mục {sub_num}: {inline_title}"
                    i += 1
                    continue

                # Look ahead across blank lines for an ALL-CAPS continuation title line
                look_idx = i + 1
                while look_idx < len(lines) and not lines[look_idx].strip():
                    look_idx += 1
                if look_idx < len(lines):
                    cand = lines[look_idx].strip()
                    if (
                        cand
                        and not cand.startswith("#")
                        and not _is_statutory_heading(cand)
                        and any(c.isalpha() for c in cand)
                        and cand == cand.upper()
                    ):
                        lines[i] = f"### Tiểu mục {sub_num}: {cand}"
                        lines[look_idx] = " "
                        i = look_idx + 1
                        continue

                lines[i] = f"### Tiểu mục {sub_num}"
            i += 1

        clean_lines = [line if line.strip() else " " for line in lines]
        clean_text = "\n".join(clean_lines)

        assert len(clean_text.splitlines()) == len(raw_lines), (
            f"Line count invariant violation: clean_text has {len(clean_text.splitlines())} lines, "
            f"raw_content has {len(raw_lines)} lines."
        )

        return clean_text, title, meta

    def _prune_empty_containers(self, node: _SectionNode) -> None:
        """Removes empty leaf nodes and clears metadata-only blocks on internal container nodes."""
        kept_children: list[_SectionNode] = []
        for child in node.children:
            self._prune_empty_containers(child)
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
        doc_meta: dict[str, object],
    ) -> list[ParsedChunkDraft]:
        """Emits one cohesive chunk per statutory provision or overview section."""
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

        body_text = "\n\n".join(b.text for b in non_empty_blocks).strip()
        if not body_text:
            return []

        if sec.level > 0:
            hashes = "#" * max(1, min(sec.raw_h_level, 6))
            heading_header = f"{hashes} {sec.title}"
            if not body_text.startswith("#"):
                full_verbatim = f"{heading_header}\n\n{body_text}"
            else:
                full_verbatim = body_text
            part_start = (
                min(sec.start_line, non_empty_blocks[0].start_line)
                if sec.start_line > 0
                else non_empty_blocks[0].start_line
            )
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
            "title": sec.title,
            "node_type": node_type,
            "statutory_unit": sec.statutory_kind,
            "framework": "baohiem",
            "has_code": "```" in full_verbatim,
            "has_table": "|" in full_verbatim,
            "ancestor_titles": effective_breadcrumbs,
        }
        if "doc_code" in doc_meta:
            chunk_meta["doc_code"] = doc_meta["doc_code"]

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

    def parse(
        self,
        file_path: Path,
        doc_slug: str | None = None,
        corpus_root: Path | None = None,
    ) -> ParsedDocumentDraft:
        """Parses a Vietnamese Insurance Law Markdown file into a ParsedDocumentDraft."""
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

    def parse_text(
        self,
        raw_content: str,
        doc_slug: str,
        title: str | None = None,
    ) -> ParsedDocumentDraft:
        """Parses raw text of Vietnamese Insurance Law Markdown into ParsedDocumentDraft."""
        slug = canonicalize_ltree_path(doc_slug)
        clean_text, fm_title, fm_meta = self._sanitize_baohiem_content(raw_content)

        raw_lines = raw_content.splitlines()
        total_lines = len(raw_lines)
        if not clean_text.strip():
            return ParsedDocumentDraft(
                doc_slug=slug,
                title=title or fm_title or "",
                raw_text=raw_content,
                chunks=[],
                edges=[],
                metadata={
                    "total_lines": total_lines,
                    "format_type": "baohiem_md",
                    "framework": "baohiem",
                    **fm_meta,
                },
            )

        tokens = self._md.parse(clean_text)
        syntax_tree = SyntaxTreeNode(tokens)

        effective_title = title or fm_title
        if not effective_title:
            for child in syntax_tree.children:
                if child.type == "heading" and child.tag in ("h1", "h2"):
                    effective_title = "".join(c.content for c in child.children).strip()
                    break
        effective_title = effective_title or "Văn bản pháp luật bảo hiểm"

        root_section = _SectionNode(
            level=0,
            raw_h_level=1,
            title=effective_title,
            path=slug,
            breadcrumbs=[effective_title],
            statutory_kind="DOCUMENT",
            start_line=0,
            end_line=0,
        )

        # Stack holds (semantic_level, _SectionNode, used_child_labels)
        stack: list[tuple[int, _SectionNode, set[str]]] = [(0, root_section, set())]
        bound_primary_h1 = False

        for node in syntax_tree.children:
            if node.type == "heading":
                h_level = (
                    int(node.tag[1])
                    if len(node.tag) > 1 and node.tag[1].isdigit()
                    else 1
                )
                h_title = "".join(c.content for c in node.children).strip() or "Section"
                h_start = node.map[0] + 1 if node.map else 1
                h_end = node.map[1] if node.map else h_start

                # Bind primary H1 to root_section to avoid duplicating the document root segment
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

                # Keep non-statutory sub-headings inside an enclosing ARTICLE node intact
                _, active_parent, _ = stack[-1]
                if (
                    active_parent.statutory_kind == "ARTICLE"
                    and not active_parent.children
                    and not _is_statutory_heading(h_title)
                ):
                    sub_prefix = "#" * min(h_level, 6)
                    active_parent.blocks.append(
                        _BlockItem(
                            text=f"{sub_prefix} {h_title}",
                            start_line=h_start,
                            end_line=h_end,
                        )
                    )
                    active_parent.end_line = max(active_parent.end_line, h_end)
                    continue

                sem_level, label_candidate, statutory_kind = _classify_statutory_heading(
                    h_level, h_title
                )

                while len(stack) > 1 and stack[-1][0] >= sem_level:
                    stack.pop()

                _, parent_node, child_labels = stack[-1]
                slug_label = _disambiguate_label(label_candidate, child_labels)
                new_path = validate_ltree_path(f"{parent_node.path}.{slug_label}")

                # Always append exactly one breadcrumb per ltree segment so PARENT_CHAIN
                # reconstruction in ChunkRepository maps 1:1 with ltree depth.
                new_breadcrumbs = [*parent_node.breadcrumbs, h_title]

                new_section = _SectionNode(
                    level=sem_level,
                    raw_h_level=h_level,
                    title=h_title,
                    path=new_path,
                    breadcrumbs=new_breadcrumbs,
                    statutory_kind=statutory_kind,
                    start_line=h_start,
                    end_line=h_end,
                )
                parent_node.children.append(new_section)
                stack.append((sem_level, new_section, set()))
                continue

            if node.map:
                s_0, e_0 = node.map
                active_node = stack[-1][1]
                # Trim trailing blank lines included by CommonMark ordered_list / bullet_list tokens
                # so end_line matches the exact last line of text in documents.raw_text.
                trimmed_e_0 = e_0
                while (
                    trimmed_e_0 > s_0 + 1
                    and not raw_lines[trimmed_e_0 - 1].strip()
                ):
                    trimmed_e_0 -= 1
                node_text = "\n".join(raw_lines[s_0:trimmed_e_0]).strip()
                if node_text:
                    block_start = s_0 + 1
                    block_end = trimmed_e_0
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
                        )
                    )
                    active_node.end_line = max(active_node.end_line, block_end)

        self._prune_empty_containers(root_section)

        chunks: list[ParsedChunkDraft] = []
        used_paths: set[str] = set()

        def _walk(node: _SectionNode) -> None:
            chunks.extend(
                self._emit_section_chunks(
                    node,
                    has_children=bool(node.children),
                    used_paths=used_paths,
                    doc_meta=fm_meta,
                )
            )
            for child in node.children:
                _walk(child)

        _walk(root_section)
        chunks.sort(key=lambda c: (c.start_line, c.path))

        doc_meta = dict(fm_meta)
        doc_meta["total_lines"] = total_lines
        doc_meta["format_type"] = "baohiem_md"
        doc_meta["framework"] = "baohiem"
        doc_meta["chunks_count"] = len(chunks)

        return ParsedDocumentDraft(
            doc_slug=slug,
            title=effective_title,
            raw_text=raw_content,
            chunks=chunks,
            edges=[],
            metadata=doc_meta,
        )
