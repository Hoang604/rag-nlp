from __future__ import annotations

import re

from rag_eval.legal.ingestion.staging.models import ChunkReviewStatus
from rag_eval.legal.ingestion.staging.session import StagingDocumentSession
from rag_eval.legal.schemas import sanitize_ltree_label
from rag_eval.legal.web.schemas import (
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

                    new_node = DocumentTreeNodeResponse(
                        path=current_path_accum,
                        label=seg,
                        node_type="NODE",
                        verbatim_text=chunk.verbatim_text if is_leaf else "",
                        contextualized_text=chunk.contextualized_text if is_leaf else "",
                        start_line=chunk.start_line if is_leaf else 1,
                        end_line=chunk.end_line if is_leaf else 1,
                        metadata=chunk.metadata if is_leaf else {},
                        review_status=(
                            chunk.review_status.value if is_leaf else "PENDING"
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

        def _sort_and_propagate_recursively(node: DocumentTreeNodeResponse) -> None:
            node.children.sort(key=lambda c: natural_path_key(c.path))
            for child in node.children:
                _sort_and_propagate_recursively(child)
            if node.children:
                if all(child.review_status == "REVIEWED" for child in node.children):
                    node.review_status = "REVIEWED"
                else:
                    node.review_status = "PENDING"

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
