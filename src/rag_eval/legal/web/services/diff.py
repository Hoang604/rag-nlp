from __future__ import annotations

from rag_eval.legal.ingestion.staging.models import StagingChunk, StagingStatus
from rag_eval.legal.ingestion.staging.session import StagingDocumentSession
from rag_eval.legal.web.schemas import (
    AuditDiffEntry,
    SessionDiffResponse,
)


class DiffCalculator:
    """Calculates 4-stage version mutation differences between initial AST baseline and current state."""

    def compute_diff(self, session: StagingDocumentSession) -> SessionDiffResponse:
        """Computes added, modified, deleted chunks and detailed diff entries."""
        initial_map: dict[str, dict[str, object]] = {}
        baseline_snapshot = (
            session.metadata.get("amendment_baseline_snapshot")
            if session.status == StagingStatus.AMENDMENT and session.metadata.get("amendment_baseline_snapshot")
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

                if chunk.verbatim_text != init_item.get("verbatim_text"):
                    modified_fields.append("verbatim_text")
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

                if chunk.metadata != init_item.get("metadata", {}):
                    modified_fields.append("metadata")
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
                        "current": chunk.model_dump(mode="json"),
                        "baseline": init_item,
                    })

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
