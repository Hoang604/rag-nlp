from __future__ import annotations

import re

from rag_eval.schemas import ChunkEntity, canonicalize_ltree_path
from rag_eval.web.schemas import (
    DocumentTreeNodeResponse,
    DocumentTreeResponse,
)


def natural_path_key(path: str) -> list[tuple[str, int, str]]:
    """Generates natural alphanumeric sort keys for LTREE paths."""
    keys: list[tuple[str, int, str]] = []
    for seg in path.split("."):
        parts = re.split(r"(\d+)", seg)
        for part in parts:
            if not part:
                continue
            if part.isdigit():
                keys.append(("", int(part), ""))
            else:
                keys.append((part.lower(), 0, part))
    return keys


def _humanize_ltree_segment(seg: str) -> str:
    """Formats a raw LTree segment (e.g. 'chuong_i', 'muc_2', 'dieu_15') into a clean label."""
    lower = seg.lower()
    if lower.startswith("chuong_"):
        suffix = seg[7:].replace("_", " ").upper()
        return f"Chương {suffix}"
    if lower.startswith("phan_"):
        suffix = seg[5:].replace("_", " ").upper()
        return f"Phần {suffix}"
    if lower.startswith("muc_"):
        suffix = seg[4:].replace("_", " ").upper()
        return f"Mục {suffix}"
    if lower.startswith("tieu_muc_"):
        suffix = seg[9:].replace("_", " ").upper()
        return f"Tiểu mục {suffix}"
    if lower.startswith("dieu_"):
        suffix = seg[5:].replace("_", " ")
        return f"Điều {suffix}"
    if lower.startswith("khoan_"):
        suffix = seg[6:].replace("_", " ")
        return f"Khoản {suffix}"
    if lower.startswith("phu_luc_"):
        suffix = seg[8:].replace("_", " ").upper()
        return f"Phụ lục {suffix}"
    return seg


class TreeHierarchyBuilder:
    """Transforms flat list of ChunkEntity models into a full nested hierarchy tree."""

    def build_tree(
        self,
        doc_slug: str,
        title: str,
        chunks: list[ChunkEntity],
        metadata: dict[str, object] | None = None,
    ) -> DocumentTreeResponse:
        """Constructs nested tree hierarchy with root node and complete children branches."""
        sanitized_root = canonicalize_ltree_path(doc_slug)
        root_segments = sanitized_root.split(".")
        root_seg_len = len(root_segments)
        doc_meta = dict(metadata or {})

        root_node = DocumentTreeNodeResponse(
            path=sanitized_root,
            label=title or doc_slug,
            node_type="DOCUMENT",
            verbatim_text="",
            contextualized_text=f"[{title or doc_slug}]",
            metadata=doc_meta,
            children=[],
        )

        node_index: dict[str, DocumentTreeNodeResponse] = {sanitized_root: root_node}
        sorted_chunks = sorted(chunks, key=lambda c: natural_path_key(c.path))

        for chunk in sorted_chunks:
            segments = chunk.path.split(".")
            raw_ancestors = chunk.metadata.get("ancestor_titles")
            ancestor_titles = (
                [str(a).strip() for a in raw_ancestors if str(a).strip()]
                if isinstance(raw_ancestors, list)
                else []
            )

            if chunk.path == sanitized_root:
                start_idx = len(segments)
                current_path_accum = sanitized_root
                raw_h = chunk.metadata.get("heading_raw") or chunk.metadata.get("title")
                if raw_h and isinstance(raw_h, str) and not title:
                    root_node.label = raw_h
                if chunk.verbatim_text and not root_node.verbatim_text:
                    root_node.verbatim_text = chunk.verbatim_text
                    root_node.start_line = chunk.start_line
                    root_node.end_line = chunk.end_line
                continue
            elif chunk.path.startswith(f"{sanitized_root}."):
                start_idx = root_seg_len
                current_path_accum = sanitized_root
            else:
                start_idx = 0
                current_path_accum = ""

            for idx in range(start_idx, len(segments)):
                seg = segments[idx]
                current_path_accum = (
                    seg if not current_path_accum else f"{current_path_accum}.{seg}"
                )
                is_leaf = idx == len(segments) - 1
                rel_depth = idx - start_idx + 1

                if current_path_accum not in node_index:
                    parent_path = (
                        current_path_accum.rsplit(".", 1)[0]
                        if "." in current_path_accum
                        else sanitized_root
                    )

                    leaf_node_type = "SECTION"
                    leaf_label = _humanize_ltree_segment(seg)
                    if 0 <= rel_depth < len(ancestor_titles):
                        leaf_label = ancestor_titles[rel_depth]

                    if is_leaf:
                        leaf_node_type = str(
                            chunk.metadata.get("node_type")
                            or ("TABLE" if chunk.metadata.get("is_table") else "PARAGRAPH")
                        )
                        raw_h = chunk.metadata.get("heading_raw") or chunk.metadata.get("title")
                        if raw_h and isinstance(raw_h, str):
                            leaf_label = raw_h

                    new_node = DocumentTreeNodeResponse(
                        path=current_path_accum,
                        label=leaf_label,
                        node_type=leaf_node_type,
                        verbatim_text=chunk.verbatim_text if is_leaf else "",
                        contextualized_text=chunk.contextualized_text if is_leaf else "",
                        start_line=chunk.start_line,
                        end_line=chunk.end_line,
                        metadata=chunk.metadata if is_leaf else {},
                        children=[],
                    )

                    node_index[current_path_accum] = new_node
                    parent_node = node_index.get(parent_path, root_node)
                    parent_node.children.append(new_node)
                else:
                    existing = node_index[current_path_accum]
                    if (
                        existing.label == seg
                        and 0 <= rel_depth < len(ancestor_titles)
                    ):
                        existing.label = ancestor_titles[rel_depth]
                    if is_leaf:
                        existing.verbatim_text = chunk.verbatim_text
                        existing.contextualized_text = chunk.contextualized_text
                        existing.start_line = chunk.start_line
                        existing.end_line = chunk.end_line
                        existing.metadata = chunk.metadata
                        leaf_node_type = str(
                            chunk.metadata.get("node_type")
                            or ("TABLE" if chunk.metadata.get("is_table") else "PARAGRAPH")
                        )
                        existing.node_type = leaf_node_type
                        raw_h = chunk.metadata.get("heading_raw") or chunk.metadata.get("title")
                        if raw_h and isinstance(raw_h, str):
                            existing.label = raw_h

        def _finalize_recursively(node: DocumentTreeNodeResponse) -> None:
            node.children.sort(key=lambda c: natural_path_key(c.path))
            for child in node.children:
                _finalize_recursively(child)
            if node.children:
                child_starts = [c.start_line for c in node.children if c.start_line >= 1]
                child_ends = [c.end_line for c in node.children if c.end_line >= 1]
                if child_starts and child_ends and not node.verbatim_text:
                    node.start_line = min(child_starts)
                    node.end_line = max(child_ends)

        _finalize_recursively(root_node)

        return DocumentTreeResponse(
            doc_slug=doc_slug,
            title=title,
            total_nodes=len(node_index),
            total_chunks=len(chunks),
            root=root_node,
        )
