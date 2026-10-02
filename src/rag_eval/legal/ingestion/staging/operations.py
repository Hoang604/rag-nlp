from __future__ import annotations

import datetime
from collections.abc import Sequence
from typing import TYPE_CHECKING

from rag_eval.legal.ingestion.staging.models import (
    ChunkReviewStatus,
    ReparentPathMapping,
    StagingChunk,
    StagingChunkDelta,
    StagingDeltaReport,
    StagingEdge,
    StagingMutationRecord,
    StagingStatus,
    StgReparentResult,
    deep_merge_dict,
)

if TYPE_CHECKING:
    from rag_eval.legal.ingestion.staging.session import StagingDocumentSession
from rag_eval.legal.exceptions import (
    E_AST_GROUNDING_VALIDATION,
    E_CORPUS_INTEGRITY_VIOLATION,
    E_INVALID_DOCUMENT_HIERARCHY,
    CorpusDomainError,
)
from rag_eval.legal.schemas import (
    FinalizationState,
    sanitize_ltree_label,
    validate_ltree_path,
)


def apply_chunk_deltas_to_session(
    session: StagingDocumentSession,
    deltas: Sequence[StagingChunkDelta],
    removed_paths: list[str] | None = None,
    cascade_breadcrumbs: bool = True,
    actor: str = "AGENT",
) -> StagingDeltaReport:
    """Applies surgical field-level updates and removals to chunks in the session."""
    if session.status not in (StagingStatus.DRAFT, StagingStatus.AMENDMENT):
        raise CorpusDomainError(
            error_code=E_CORPUS_INTEGRITY_VIOLATION,
            message=f"Không thể chỉnh sửa phiên staging ở trạng thái '{session.status.value}'.",
            data={"doc_slug": session.doc_slug, "status": session.status.value},
        )

    chunk_map: dict[str, StagingChunk] = {c.path: c for c in session.chunks}
    removed_count = 0
    if removed_paths:
        for rp in removed_paths:
            clean_rp = validate_ltree_path(rp)
            if clean_rp in chunk_map:
                del chunk_map[clean_rp]
                removed_count += 1

    fields_modified_set: set[str] = set()
    cascaded_count = 0

    for delta in deltas:
        clean_p = validate_ltree_path(delta.path)
        chunk = chunk_map.get(clean_p)
        if chunk is None:
            if delta.verbatim_text is not None:
                new_chunk = StagingChunk(
                    path=clean_p,
                    verbatim_text=delta.verbatim_text,
                    contextualized_text=delta.contextualized_text or delta.verbatim_text,
                    lead_sentence=delta.lead_sentence or "",
                    start_line=delta.start_line or 1,
                    end_line=delta.end_line or 1,
                    metadata=delta.metadata or {},
                    review_status=delta.review_status or ChunkReviewStatus.PENDING,
                    finalization_state=delta.finalization_state or FinalizationState.UNFINALIZED,
                )
                chunk_map[clean_p] = new_chunk
                fields_modified_set.add("created")
                continue
            raise CorpusDomainError(
                error_code=E_INVALID_DOCUMENT_HIERARCHY,
                message=f"Chunk '{clean_p}' không tồn tại trong phiên làm việc cho văn bản '{session.doc_slug}'.",
                data={"doc_slug": session.doc_slug, "path": clean_p},
            )

        if delta.verbatim_text is not None:
            old_verbatim = chunk.verbatim_text
            chunk.verbatim_text = delta.verbatim_text
            chunk.char_length = len(delta.verbatim_text)
            fields_modified_set.add("verbatim_text")

            if delta.contextualized_text is None:
                if old_verbatim and old_verbatim in chunk.contextualized_text:
                    chunk.contextualized_text = chunk.contextualized_text.replace(
                        old_verbatim, delta.verbatim_text
                    )
                elif not chunk.contextualized_text:
                    chunk.contextualized_text = delta.verbatim_text
                fields_modified_set.add("contextualized_text")

        if delta.contextualized_text is not None:
            chunk.contextualized_text = delta.contextualized_text
            fields_modified_set.add("contextualized_text")

        if delta.start_line is not None:
            chunk.start_line = delta.start_line
            fields_modified_set.add("start_line")

        if delta.end_line is not None:
            chunk.end_line = delta.end_line
            fields_modified_set.add("end_line")

        if delta.metadata is not None:
            base_dict = (
                dict(chunk.metadata)
                if isinstance(chunk.metadata, dict)
                else dict(chunk.metadata or {})
            )
            delta_dict = (
                dict(delta.metadata)
                if isinstance(delta.metadata, dict)
                else dict(delta.metadata or {})
            )
            merged_dict = deep_merge_dict(base_dict, delta_dict)
            chunk.metadata = merged_dict
            fields_modified_set.add("metadata")

        if delta.review_status is not None:
            chunk.review_status = delta.review_status
            fields_modified_set.add("review_status")

        if delta.finalization_state is not None:
            chunk.finalization_state = delta.finalization_state
            fields_modified_set.add("finalization_state")

        if delta.lead_sentence is not None and delta.lead_sentence != chunk.lead_sentence:
            old_lead = chunk.lead_sentence
            chunk.lead_sentence = delta.lead_sentence
            fields_modified_set.add("lead_sentence")

            if cascade_breadcrumbs:
                child_prefix = f"{clean_p}."
                for other_p, other_c in chunk_map.items():
                    if other_p.startswith(child_prefix):
                        other_c.lead_sentence = delta.lead_sentence
                        if old_lead and old_lead in other_c.contextualized_text:
                            other_c.contextualized_text = other_c.contextualized_text.replace(
                                old_lead, delta.lead_sentence
                            )
                        elif delta.lead_sentence not in other_c.contextualized_text:
                            other_c.contextualized_text = (
                                f"{other_c.contextualized_text}\n{delta.lead_sentence}"
                            )
                        cascaded_count += 1

    session.chunks = sorted(chunk_map.values(), key=lambda x: x.path)
    now = datetime.datetime.now(datetime.UTC)
    session.updated_at = now
    session.mutation_history.append(
        StagingMutationRecord(
            actor=actor,
            action_type="CHUNK_PATCHED",
            description=f"Patched {len(deltas)} chunks (cascaded {cascaded_count} children) and removed {removed_count} paths.",
            timestamp=now,
            diff_payload={
                "updated_count": len(deltas),
                "cascaded_count": cascaded_count,
                "removed_count": removed_count,
                "fields_modified": sorted(fields_modified_set),
                "removed_paths": removed_paths or [],
            },
        )
    )

    return StagingDeltaReport(
        doc_slug=session.doc_slug,
        updated_count=len(deltas),
        cascaded_count=cascaded_count,
        removed_count=removed_count,
        total_chunks=len(session.chunks),
        fields_modified=sorted(fields_modified_set),
    )


def finalize_chunks_in_session(
    session: StagingDocumentSession,
    paths: Sequence[str],
    actor: str = "AGENT",
) -> tuple[int, list[dict[str, object]]]:
    """Marks designated chunk paths as FINALIZED and records CHUNKS_FINALIZED mutation."""
    if session.status not in (StagingStatus.DRAFT, StagingStatus.AMENDMENT):
        raise CorpusDomainError(
            error_code=E_CORPUS_INTEGRITY_VIOLATION,
            message=f"Không thể chỉnh sửa phiên staging ở trạng thái '{session.status.value}'.",
            data={"doc_slug": session.doc_slug, "status": session.status.value},
        )

    target_paths = {validate_ltree_path(p) for p in paths}
    chunk_map = {c.path: c for c in session.chunks}
    edges_by_source: dict[str, list[StagingEdge]] = {}
    for edge in session.edges:
        edges_by_source.setdefault(edge.source_path, []).append(edge)

    finalized_count = 0
    results: list[dict[str, object]] = []
    for p in sorted(target_paths):
        if p in chunk_map:
            target_chunk = chunk_map[p]
            target_chunk.review_status = ChunkReviewStatus.REVIEWED
            chunk_edges = edges_by_source.get(p, [])
            if not chunk_edges:
                target_chunk.finalization_state = FinalizationState.FINALIZED_SELF_CONTAINED
            else:
                has_unattached = any(e.target_path is None for e in chunk_edges)
                if has_unattached:
                    target_chunk.finalization_state = FinalizationState.UNFINALIZED
                else:
                    target_chunk.finalization_state = FinalizationState.FINALIZED_FULLY_LINKED
            finalized_count += 1
            results.append({
                "path": target_chunk.path,
                "review_status": target_chunk.review_status,
                "finalization_state": target_chunk.finalization_state,
            })

    now = datetime.datetime.now(datetime.UTC)
    session.updated_at = now
    session.mutation_history.append(
        StagingMutationRecord(
            actor=actor,
            action_type="CHUNKS_REVIEWED",
            description=f"Marked {finalized_count} chunks as REVIEWED.",
            timestamp=now,
            diff_payload={"paths": sorted(target_paths), "finalized_count": finalized_count},
        )
    )
    return finalized_count, results


def validate_and_attach_edges_to_session(
    session: StagingDocumentSession,
    edges: Sequence[StagingEdge],
    actor: str = "AGENT",
) -> tuple[int, list[StagingEdge]]:
    """Pre-commit lints candidate relation edges and attaches valid ones to the session."""
    if session.status not in (StagingStatus.DRAFT, StagingStatus.AMENDMENT):
        raise CorpusDomainError(
            error_code=E_CORPUS_INTEGRITY_VIOLATION,
            message=f"Không thể chỉnh sửa phiên staging ở trạng thái '{session.status.value}'.",
            data={"doc_slug": session.doc_slug, "status": session.status.value},
        )

    valid_paths = {c.path for c in session.chunks}
    doc_prefix = sanitize_ltree_label(session.doc_slug)

    existing_edges: dict[tuple[str, str | None, str], StagingEdge] = {
        (e.source_path, e.target_path, e.relation_type): e for e in session.edges
    }

    for new_edge in edges:
        clean_src = validate_ltree_path(new_edge.source_path)
        clean_tgt = validate_ltree_path(new_edge.target_path) if new_edge.target_path else None
        clean_ext = new_edge.target_external_ref.strip() if new_edge.target_external_ref else None

        if not clean_tgt and not clean_ext:
            raise CorpusDomainError(
                error_code=E_AST_GROUNDING_VALIDATION,
                message=f"Invalid edge from '{clean_src}': must specify either target_path or target_external_ref.",
                data={"doc_slug": session.doc_slug, "source_path": clean_src},
            )

        if clean_src not in valid_paths:
            raise CorpusDomainError(
                error_code=E_AST_GROUNDING_VALIDATION,
                message=f"Invalid edge source path '{clean_src}': path does not exist in staged document '{session.doc_slug}'.",
                data={"doc_slug": session.doc_slug, "source_path": clean_src},
            )

        if clean_tgt and clean_src == clean_tgt:
            raise CorpusDomainError(
                error_code=E_AST_GROUNDING_VALIDATION,
                message=f"Self-referencing edge loop detected on '{clean_src}'.",
                data={"doc_slug": session.doc_slug, "path": clean_src},
            )

        if clean_tgt and clean_tgt.startswith(f"{doc_prefix}.") and clean_tgt not in valid_paths:
            raise CorpusDomainError(
                error_code=E_AST_GROUNDING_VALIDATION,
                message=f"Invalid edge target path '{clean_tgt}': intra-document target does not exist in staged document '{session.doc_slug}'.",
                data={"doc_slug": session.doc_slug, "target_path": clean_tgt},
            )

        new_edge.source_path = clean_src
        new_edge.target_path = clean_tgt
        key = (clean_src, clean_tgt, new_edge.relation_type)
        existing_edges[key] = new_edge
        if clean_tgt is not None:
            existing_edges.pop((clean_src, None, new_edge.relation_type), None)

    session.edges = list(existing_edges.values())
    now = datetime.datetime.now(datetime.UTC)
    session.updated_at = now
    session.mutation_history.append(
        StagingMutationRecord(
            actor=actor,
            action_type="EDGES_ADDED",
            description=f"Added or updated {len(edges)} relation edges.",
            timestamp=now,
            diff_payload={"edges_count": len(edges)},
        )
    )

    return len(session.edges), session.edges


def reparent_subtree_in_session(
    session: StagingDocumentSession,
    old_path_prefix: str,
    new_path_prefix: str,
    dry_run: bool = False,
    actor: str = "AGENT",
) -> StgReparentResult:
    """Atomically migrates an entire subtree and its graph edges to a new parent prefix."""
    if session.status not in (StagingStatus.DRAFT, StagingStatus.AMENDMENT):
        raise CorpusDomainError(
            error_code=E_CORPUS_INTEGRITY_VIOLATION,
            message=f"Không thể tái cấu trúc phiên staging ở trạng thái '{session.status.value}'.",
            data={"doc_slug": session.doc_slug, "status": session.status.value},
        )

    clean_old = validate_ltree_path(old_path_prefix)
    clean_new = validate_ltree_path(new_path_prefix)
    doc_prefix = sanitize_ltree_label(session.doc_slug)

    if not (clean_old == doc_prefix or clean_old.startswith(f"{doc_prefix}.")):
        raise CorpusDomainError(
            error_code=E_INVALID_DOCUMENT_HIERARCHY,
            message=f"Đường dẫn cũ '{clean_old}' không thuộc văn bản '{session.doc_slug}'.",
            data={"doc_slug": session.doc_slug, "path": clean_old},
        )

    if not (clean_new == doc_prefix or clean_new.startswith(f"{doc_prefix}.")):
        raise CorpusDomainError(
            error_code=E_INVALID_DOCUMENT_HIERARCHY,
            message=f"Đường dẫn mới '{clean_new}' không thuộc văn bản '{session.doc_slug}'.",
            data={"doc_slug": session.doc_slug, "path": clean_new},
        )

    if clean_new == clean_old or clean_new.startswith(f"{clean_old}."):
        raise CorpusDomainError(
            error_code=E_INVALID_DOCUMENT_HIERARCHY,
            message=f"Không thể di dời nút cha '{clean_old}' vào trong chính nó hoặc con cháu của nó '{clean_new}'.",
            data={"old_path_prefix": clean_old, "new_path_prefix": clean_new},
        )

    old_dot = f"{clean_old}."
    target_chunks: list[StagingChunk] = [
        c for c in session.chunks if c.path == clean_old or c.path.startswith(old_dot)
    ]
    if not target_chunks:
        raise CorpusDomainError(
            error_code=E_INVALID_DOCUMENT_HIERARCHY,
            message=f"Không tìm thấy chunk nào khớp với tiền tố '{clean_old}'.",
            data={"doc_slug": session.doc_slug, "path_prefix": clean_old},
        )

    new_dot = f"{clean_new}."
    collision_chunks = [
        c for c in session.chunks if c.path == clean_new or c.path.startswith(new_dot)
    ]
    if collision_chunks:
        raise CorpusDomainError(
            error_code=E_INVALID_DOCUMENT_HIERARCHY,
            message=f"Tiền tố đích '{clean_new}' bị xung đột với {len(collision_chunks)} chunk đã tồn tại.",
            data={"doc_slug": session.doc_slug, "colliding_path": collision_chunks[0].path},
        )

    sample_mappings: list[ReparentPathMapping] = []
    path_rename_map: dict[str, str] = {}
    for c in target_chunks:
        if c.path == clean_old:
            new_p = clean_new
        else:
            suffix = c.path[len(clean_old) :]
            new_p = f"{clean_new}{suffix}"
        path_rename_map[c.path] = new_p
        if len(sample_mappings) < 10:
            sample_mappings.append(ReparentPathMapping(old_path=c.path, new_path=new_p))

    affected_edges_count = 0
    for e in session.edges:
        if (
            e.source_path in path_rename_map
            or e.source_path.startswith(old_dot)
            or (e.target_path and (e.target_path in path_rename_map or e.target_path.startswith(old_dot)))
        ):
            affected_edges_count += 1

    result = StgReparentResult(
        doc_slug=session.doc_slug,
        status="SUCCESS",
        dry_run=dry_run,
        affected_chunks_count=len(target_chunks),
        affected_edges_count=affected_edges_count,
        old_path_prefix=clean_old,
        new_path_prefix=clean_new,
        sample_mappings=sample_mappings,
    )

    if dry_run:
        return result

    for c in target_chunks:
        c.path = path_rename_map[c.path]

    existing_edges: dict[tuple[str, str | None, str], StagingEdge] = {}
    for e in session.edges:
        new_src = path_rename_map.get(e.source_path)
        if new_src is None and e.source_path.startswith(old_dot):
            new_src = f"{clean_new}{e.source_path[len(clean_old):]}"
        if new_src:
            e.source_path = new_src

        if e.target_path:
            new_tgt = path_rename_map.get(e.target_path)
            if new_tgt is None and e.target_path.startswith(old_dot):
                new_tgt = f"{clean_new}{e.target_path[len(clean_old):]}"
            if new_tgt:
                e.target_path = new_tgt

        key = (e.source_path, e.target_path, e.relation_type)
        existing_edges[key] = e

    session.edges = list(existing_edges.values())
    session.chunks.sort(key=lambda x: x.path)

    now = datetime.datetime.now(datetime.UTC)
    session.updated_at = now
    session.mutation_history.append(
        StagingMutationRecord(
            actor=actor,
            action_type="SUBTREE_REPARENTED",
            description=f"Migrated subtree '{clean_old}' to '{clean_new}' ({len(target_chunks)} chunks, {affected_edges_count} edges).",
            timestamp=now,
            diff_payload={
                "old_path_prefix": clean_old,
                "new_path_prefix": clean_new,
                "affected_chunks": len(target_chunks),
                "affected_edges": affected_edges_count,
                "sample_mappings": [m.model_dump() for m in sample_mappings],
            },
        )
    )

    return result
