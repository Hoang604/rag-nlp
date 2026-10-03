from __future__ import annotations

from rag_eval.ingestion.staging.models import (
    StagingChunk,
    StagingEdge,
    StagingStatus,
)
from rag_eval.ingestion.staging.session import StagingDocumentSession
from rag_eval.web.schemas import (
    AuditDiffEntry,
    SessionDiffResponse,
)


class DiffCalculator:
    """Calculates 4-stage version mutation differences between initial AST baseline and current state."""

    def compute_diff(self, session: StagingDocumentSession) -> SessionDiffResponse:
        """Computes added, modified, deleted chunks and detailed diff entries."""
        initial_map: dict[str, dict[str, object]] = {}
        has_amendment_baseline = bool(session.metadata.get("amendment_baseline_snapshot"))
        is_amendment_lifecycle = session.status in (
            StagingStatus.AMENDMENT,
            StagingStatus.APPROVED,
            StagingStatus.AGENT_COMMITTED,
        )
        baseline_snapshot = (
            session.metadata.get("amendment_baseline_snapshot")
            if is_amendment_lifecycle and has_amendment_baseline
            else session.raw_ast_snapshot
        )
        if isinstance(baseline_snapshot, list):
            for item in baseline_snapshot:
                if isinstance(item, dict) and "path" in item and isinstance(item["path"], str):
                    initial_map[item["path"]] = item

        current_map: dict[str, StagingChunk] = {c.path: c for c in session.chunks}

        added_chunks: list[StagingChunk] = []
        deleted_chunks: list[dict[str, object]] = []
        modified_chunks: list[dict[str, object]] = []
        diff_entries: list[AuditDiffEntry] = []

        for path, chunk in current_map.items():
            if path not in initial_map:
                added_chunks.append(chunk)
                diff_entries.append(
                    AuditDiffEntry(
                        path=path,
                        change_type="ADDED",
                        field_name=None,
                        old_value=None,
                        new_value=chunk.model_dump(mode="json"),
                        description=f"Chunk '{path}' was added after initial AST parse.",
                    )
                )

        for path, raw_item in initial_map.items():
            if path not in current_map:
                deleted_chunks.append(raw_item)
                diff_entries.append(
                    AuditDiffEntry(
                        path=path,
                        change_type="DELETED",
                        field_name=None,
                        old_value=raw_item,
                        new_value=None,
                        description=f"Chunk '{path}' was deleted from staging session.",
                    )
                )

        for path, chunk in current_map.items():
            if path in initial_map:
                init_item = initial_map[path]
                modified_fields: list[str] = []

                field_diffs_map: dict[str, dict[str, object]] = {}

                if chunk.verbatim_text != init_item.get("verbatim_text"):
                    modified_fields.append("verbatim_text")
                    field_diffs_map["verbatim_text"] = {
                        "old": init_item.get("verbatim_text"),
                        "new": chunk.verbatim_text,
                    }
                    diff_entries.append(
                        AuditDiffEntry(
                            path=path,
                            change_type="MODIFIED",
                            field_name="verbatim_text",
                            old_value=init_item.get("verbatim_text"),
                            new_value=chunk.verbatim_text,
                            description=f"Verbatim text updated on '{path}'.",
                        )
                    )

                if chunk.contextualized_text != init_item.get("contextualized_text"):
                    modified_fields.append("contextualized_text")
                    field_diffs_map["contextualized_text"] = {
                        "old": init_item.get("contextualized_text"),
                        "new": chunk.contextualized_text,
                    }
                    diff_entries.append(
                        AuditDiffEntry(
                            path=path,
                            change_type="MODIFIED",
                            field_name="contextualized_text",
                            old_value=init_item.get("contextualized_text"),
                            new_value=chunk.contextualized_text,
                            description=f"Contextualized text updated on '{path}'.",
                        )
                    )


                if chunk.start_line != init_item.get("start_line") or chunk.end_line != init_item.get("end_line"):
                    modified_fields.append("line_bounds")
                    field_diffs_map["line_bounds"] = {
                        "old": {"start_line": init_item.get("start_line"), "end_line": init_item.get("end_line")},
                        "new": {"start_line": chunk.start_line, "end_line": chunk.end_line},
                    }
                    diff_entries.append(
                        AuditDiffEntry(
                            path=path,
                            change_type="MODIFIED",
                            field_name="line_bounds",
                            old_value={"start_line": init_item.get("start_line"), "end_line": init_item.get("end_line")},
                            new_value={"start_line": chunk.start_line, "end_line": chunk.end_line},
                            description=f"Line bounds updated on '{path}'.",
                        )
                    )

                if chunk.metadata != init_item.get("metadata", {}):
                    modified_fields.append("metadata")
                    field_diffs_map["metadata"] = {
                        "old": init_item.get("metadata"),
                        "new": chunk.metadata,
                    }
                    diff_entries.append(
                        AuditDiffEntry(
                            path=path,
                            change_type="MODIFIED",
                            field_name="metadata",
                            old_value=init_item.get("metadata"),
                            new_value=chunk.metadata,
                            description=f"Metadata payload updated on '{path}'.",
                        )
                    )

                if modified_fields:
                    modified_chunks.append({
                        "path": path,
                        "modified_fields": modified_fields,
                        "field_diffs": field_diffs_map,
                        "current": chunk.model_dump(mode="json"),
                        "current_chunk": chunk.model_dump(mode="json"),
                        "baseline": init_item,
                        "baseline_chunk": init_item,
                    })

        # B-4: Compute edge baseline diffs for Stage 3 Knowledge Graph
        initial_edges_map: dict[tuple[str, str, str], dict[str, object]] = {}
        has_amendment_edges_baseline = bool(session.metadata.get("amendment_baseline_edges_snapshot"))
        baseline_edges_snapshot = (
            session.metadata.get("amendment_baseline_edges_snapshot")
            if is_amendment_lifecycle and has_amendment_edges_baseline
            else session.raw_edge_snapshot
        )
        if isinstance(baseline_edges_snapshot, list):
            for edge_item in baseline_edges_snapshot:
                if isinstance(edge_item, dict):
                    src = str(edge_item.get("source_path", ""))
                    tgt = str(edge_item.get("target_path", ""))
                    rel = str(edge_item.get("relation_type", ""))
                    if src and tgt:
                        initial_edges_map[(src, tgt, rel)] = edge_item

        current_edges_map: dict[tuple[str, str, str], StagingEdge] = {}
        for e in session.edges:
            rel_str = e.relation_type.value if hasattr(e.relation_type, "value") else str(e.relation_type)
            tgt_str = e.target_path or ""
            current_edges_map[(e.source_path, tgt_str, rel_str)] = e

        for key, edge in current_edges_map.items():
            if key not in initial_edges_map:
                diff_entries.append(
                    AuditDiffEntry(
                        path=f"{edge.source_path}->{edge.target_path}",
                        change_type="ADDED",
                        field_name="edge",
                        old_value=None,
                        new_value=edge.model_dump(mode="json"),
                        description=f"Quan hệ cạnh '{edge.source_path}' -> '{edge.target_path}' ({key[2]}) được thêm mới.",
                    )
                )

        for key, raw_edge in initial_edges_map.items():
            if key not in current_edges_map:
                diff_entries.append(
                    AuditDiffEntry(
                        path=f"{key[0]}->{key[1]}",
                        change_type="DELETED",
                        field_name="edge",
                        old_value=raw_edge,
                        new_value=None,
                        description=f"Quan hệ cạnh '{key[0]}' -> '{key[1]}' ({key[2]}) đã bị xóa.",
                    )
                )

        edge_diffs: list[dict[str, object]] = [e.model_dump(mode="json") for e in session.edges]

        return SessionDiffResponse(
            doc_slug=session.doc_slug,
            total_changes=len(diff_entries),
            added_chunks=added_chunks,
            modified_chunks=modified_chunks,
            deleted_chunks=deleted_chunks,
            edge_diffs=edge_diffs,
            diff_entries=diff_entries,
        )
