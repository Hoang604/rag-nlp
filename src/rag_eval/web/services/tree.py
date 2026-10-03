from __future__ import annotations

import re

from rag_eval.ingestion.staging.models import ChunkReviewStatus
from rag_eval.ingestion.staging.session import StagingDocumentSession
from rag_eval.schemas import sanitize_ltree_label
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
    """Transforms flat list of StagingChunk models into a full nested hierarchy tree."""

    def build_tree(self, session: StagingDocumentSession) -> DocumentTreeResponse:
        """Constructs nested tree hierarchy with root node and complete children branches."""
        sanitized_root = sanitize_ltree_label(session.doc_slug)

        root_node = DocumentTreeNodeResponse(
            path=sanitized_root,
            label=session.title or session.doc_slug,
            node_type="DOCUMENT",
            verbatim_text="",
            contextualized_text=f"[{session.title or session.doc_slug}]",
            metadata=session.metadata,
            children=[],
        )

        node_index: dict[str, DocumentTreeNodeResponse] = {sanitized_root: root_node}
        sorted_chunks = sorted(session.chunks, key=lambda c: natural_path_key(c.path))

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
                        review_status=(
                            chunk.review_status.value if is_leaf else "PENDING"
                        ),
                        finalization_state=(
                            chunk.finalization_state.value if is_leaf and chunk.finalization_state else None
                        ),
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
                        existing.review_status = chunk.review_status.value
                        existing.finalization_state = (
                            chunk.finalization_state.value if chunk.finalization_state else None
                        )
                        leaf_node_type = str(
                            chunk.metadata.get("node_type")
                            or ("TABLE" if chunk.metadata.get("is_table") else "PARAGRAPH")
                        )
                        existing.node_type = leaf_node_type
                        raw_h = chunk.metadata.get("heading_raw") or chunk.metadata.get("title")
                        if raw_h and isinstance(raw_h, str):
                            existing.label = raw_h

        chunk_review_status_map = {
            c.path: (c.review_status.value if hasattr(c.review_status, "value") else str(c.review_status))
            for c in session.chunks
        }

        def _sort_and_propagate_recursively(node: DocumentTreeNodeResponse) -> None:
            node.children.sort(key=lambda c: natural_path_key(c.path))
            for child in node.children:
                _sort_and_propagate_recursively(child)
            if node.children:
                all_children_reviewed = all(child.review_status == "REVIEWED" for child in node.children)
                # B-5: Preserve explicit review status of the section chunk itself
                if node.path in chunk_review_status_map:
                    own_status = chunk_review_status_map[node.path]
                    if own_status == "REVIEWED" and all_children_reviewed:
                        node.review_status = "REVIEWED"
                    else:
                        node.review_status = own_status
                else:
                    node.review_status = "REVIEWED" if all_children_reviewed else "PENDING"

        _sort_and_propagate_recursively(root_node)

        total_finalized = sum(
            1
            for c in session.chunks
            if c.review_status == ChunkReviewStatus.REVIEWED
        )
        total_pending = len(session.chunks) - total_finalized
        progress_pct = (
            round((total_finalized / len(session.chunks) * 100.0), 1)
            if session.chunks
            else 0.0
        )

        return DocumentTreeResponse(
            doc_slug=session.doc_slug,
            title=session.title,
            total_nodes=len(node_index),
            total_finalized=total_finalized,
            total_pending=total_pending,
            progress_percent=progress_pct,
            root=root_node,
        )
