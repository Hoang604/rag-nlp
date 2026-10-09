from __future__ import annotations

import re

from rag_eval.schemas import ChunkEntity, sanitize_ltree_label
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
        sanitized_root = sanitize_ltree_label(doc_slug)
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
            current_path_accum = ""

            for idx, seg in enumerate(segments):
                current_path_accum = (
                    seg if not current_path_accum else f"{current_path_accum}.{seg}"
                )
                is_leaf = idx == len(segments) - 1

                if current_path_accum not in node_index:
                    parent_path = (
                        current_path_accum.rsplit(".", 1)[0]
                        if "." in current_path_accum
                        else sanitized_root
                    )

                    leaf_node_type = "SECTION"
                    leaf_label = seg
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
                        start_line=chunk.start_line if is_leaf else 1,
                        end_line=chunk.end_line if is_leaf else 1,
                        metadata=chunk.metadata if is_leaf else {},
                        children=[],
                    )

                    node_index[current_path_accum] = new_node
                    parent_node = node_index.get(parent_path, root_node)
                    parent_node.children.append(new_node)
                else:
                    existing = node_index[current_path_accum]
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

        def _sort_recursively(node: DocumentTreeNodeResponse) -> None:
            node.children.sort(key=lambda c: natural_path_key(c.path))
            for child in node.children:
                _sort_recursively(child)

        _sort_recursively(root_node)

        return DocumentTreeResponse(
            doc_slug=doc_slug,
            title=title,
            total_nodes=len(node_index),
            total_chunks=len(chunks),
            root=root_node,
        )
