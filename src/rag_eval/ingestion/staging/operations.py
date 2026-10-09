from __future__ import annotations

import datetime
import re
from collections.abc import Sequence
from typing import TYPE_CHECKING, NoReturn

from pydantic import BaseModel

from rag_eval.ingestion.staging.models import (
    ChunkReviewStatus,
    ContextType,
    ReparentPathMapping,
    StagingChunk,
    StagingChunkDelta,
    StagingDeltaReport,
    StagingEdge,
    StagingEdgeInput,
    StagingMutationRecord,
    StagingStatus,
    StagingViolationCode,
    StagingViolationData,
    StgReparentResult,
    deep_merge_dict,
)

if TYPE_CHECKING:
    from rag_eval.ingestion.staging.session import StagingDocumentSession
from rag_eval.exceptions import (
    E_AST_GROUNDING_VALIDATION,
    E_CORPUS_INTEGRITY_VIOLATION,
    E_INVALID_DOCUMENT_HIERARCHY,
    CorpusDomainError,
)
from rag_eval.schemas import (
    FinalizationState,
    sanitize_ltree_label,
    validate_ltree_path,
)
from rag_eval.text import find_normalized_span, normalize_whitespace


def apply_chunk_deltas_to_session(
    session: StagingDocumentSession,
    deltas: Sequence[StagingChunkDelta],
    removed_paths: list[str] | None = None,
    cascade_breadcrumbs: bool = True,
    actor: str = "AGENT",
    applied_at: datetime.datetime | None = None,
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
        clean_removed: set[str] = set()
        for rp in removed_paths:
            clean_rp = validate_ltree_path(rp)
            if clean_rp in chunk_map:
                del chunk_map[clean_rp]
                clean_removed.add(clean_rp)
                removed_count += 1
            # Cascade deletion to all descendant ltree paths
            prefix = f"{clean_rp}."
            descendants = [p for p in list(chunk_map.keys()) if p.startswith(prefix)]
            for child_path in descendants:
                del chunk_map[child_path]
                clean_removed.add(child_path)
                removed_count += 1
        if clean_removed:
            session.edges = [
                e
                for e in session.edges
                if e.source_path not in clean_removed and e.target_path not in clean_removed
            ]

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
                    start_line=delta.start_line or 1,
                    end_line=delta.end_line or 1,
                    metadata=dict(delta.metadata or {}),
                    review_status=ChunkReviewStatus.PENDING,
                    finalization_state=FinalizationState.UNFINALIZED,
                    context_type=delta.context_type,
                )
                if delta.justification:
                    new_chunk.metadata["justification"] = delta.justification
                    new_chunk.metadata["finalization_justification"] = delta.justification
                chunk_map[clean_p] = new_chunk
                session.inspected_paths.add(clean_p)
                fields_modified_set.add("created")
                continue
            raise CorpusDomainError(
                error_code=E_INVALID_DOCUMENT_HIERARCHY,
                message=f"Chunk '{clean_p}' không tồn tại trong phiên làm việc cho tài liệu '{session.doc_slug}'.",
                data={"doc_slug": session.doc_slug, "path": clean_p},
            )

        if delta.verbatim_text is not None:
            old_verbatim = chunk.verbatim_text
            if delta.verbatim_text != old_verbatim:
                chunk.verbatim_text = delta.verbatim_text
                chunk.char_length = len(delta.verbatim_text)
                chunk.review_status = ChunkReviewStatus.PENDING
                chunk.finalization_state = FinalizationState.UNFINALIZED
                fields_modified_set.add("verbatim_text")
                fields_modified_set.add("review_status")

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

        if delta.context_type is not None:
            if delta.context_type != chunk.context_type:
                chunk.context_type = delta.context_type
                chunk.review_status = ChunkReviewStatus.PENDING
                chunk.finalization_state = FinalizationState.UNFINALIZED
                fields_modified_set.add("review_status")
            fields_modified_set.add("context_type")

        if delta.justification is not None:
            base_dict = (
                dict(chunk.metadata)
                if isinstance(chunk.metadata, dict)
                else dict(chunk.metadata or {})
            )
            base_dict["justification"] = delta.justification
            base_dict["finalization_justification"] = delta.justification
            chunk.metadata = base_dict
            fields_modified_set.add("metadata")

        session.inspected_paths.add(clean_p)

    if cascade_breadcrumbs and deltas:
        updated_paths = {
            validate_ltree_path(d.path)
            for d in deltas
            if validate_ltree_path(d.path) in chunk_map
        }
        explicit_context_paths = {
            validate_ltree_path(d.path)
            for d in deltas
            if d.contextualized_text is not None and validate_ltree_path(d.path) in chunk_map
        }

        def _extract_chunk_title(c: StagingChunk) -> str:
            if isinstance(c.metadata, dict):
                if c.metadata.get("heading_raw"):
                    return str(c.metadata["heading_raw"]).strip()
                if c.metadata.get("title"):
                    return str(c.metadata["title"]).strip()
            if c.verbatim_text:
                first_line = c.verbatim_text.splitlines()[0].strip()
                m = re.match(r"^#{1,6}\s+(.+)$", first_line)
                if m:
                    return m.group(1).strip()
                return first_line
            return c.path.split(".")[-1]

        cascaded_chunks: list[StagingChunk] = []
        for path_key, chunk_obj in chunk_map.items():
            if path_key in explicit_context_paths:
                continue
            is_descendant = any(
                path_key.startswith(f"{up}.") for up in updated_paths if path_key != up
            )
            if is_descendant:
                parts = path_key.split(".")
                ancestors: list[str] = []
                for idx in range(1, len(parts)):
                    prefix_p = ".".join(parts[:idx])
                    if prefix_p in chunk_map:
                        anc_t = _extract_chunk_title(chunk_map[prefix_p])
                        if anc_t:
                            ancestors.append(anc_t)

                if not ancestors and session.title:
                    ancestors.append(session.title)

                clean_verbatim = chunk_obj.verbatim_text.strip()
                if ancestors:
                    chunk_obj.contextualized_text = f"[{' > '.join(ancestors)}]\n{clean_verbatim}"
                else:
                    chunk_obj.contextualized_text = clean_verbatim

                meta_dict = (
                    dict(chunk_obj.metadata)
                    if isinstance(chunk_obj.metadata, dict)
                    else dict(chunk_obj.metadata or {})
                )
                meta_dict["ancestor_titles"] = ancestors
                chunk_obj.metadata = meta_dict
                cascaded_chunks.append(chunk_obj)

        cascaded_count = len(cascaded_chunks)

    session.chunks = sorted(chunk_map.values(), key=lambda x: x.path)
    now = applied_at or datetime.datetime.now(datetime.UTC)
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


def raise_staging_violation(
    violation_code: StagingViolationCode,
    path: str,
    doc_slug: str,
    message: str,
    remediation_hint: str,
) -> NoReturn:
    payload = StagingViolationData(
        violation_code=violation_code,
        path=path,
        doc_slug=doc_slug,
        message=message,
        remediation_hint=remediation_hint,
    )
    raise CorpusDomainError(
        error_code=E_AST_GROUNDING_VALIDATION,
        message=f"[{violation_code.value}] {message} Hướng dẫn thẩm định: {remediation_hint}",
        data=payload.model_dump(mode="json"),
    )


def finalize_chunks_in_session(
    session: StagingDocumentSession,
    paths: Sequence[str],
    actor: str = "AGENT",
    applied_at: datetime.datetime | None = None,
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

    missing_paths = [p for p in sorted(target_paths) if p not in chunk_map]
    if missing_paths:
        raise CorpusDomainError(
            error_code=E_INVALID_DOCUMENT_HIERARCHY,
            message=f"Các chunk sau không tồn tại trong phiên làm việc: {missing_paths}",
            data={"doc_slug": session.doc_slug, "missing_paths": missing_paths},
        )

    edges_by_source: dict[str, list[StagingEdge]] = {}
    for edge in session.edges:
        edges_by_source.setdefault(edge.source_path, []).append(edge)

    finalized_count = 0
    results: list[dict[str, object]] = []
    for p in sorted(target_paths):
        target_chunk = chunk_map[p]

        if not session.is_chunk_inspected(p):
            raise_staging_violation(
                violation_code=StagingViolationCode.UNINSPECTED_CHUNK,
                path=p,
                doc_slug=session.doc_slug,
                message=f"Chunk '{p}' chưa từng được đọc qua stg_get_chunk hoặc stg_get_raw trong phiên làm việc.",
                remediation_hint="Nghĩa vụ thẩm định: Bạn phải đọc và kiểm tra trực tiếp nội dung văn bản của chunk qua stg_get_chunk hoặc stg_get_raw trước khi được phép chốt nghiệm thu.",
            )

        if target_chunk.context_type is None:
            raise_staging_violation(
                violation_code=StagingViolationCode.UNCLASSIFIED_CHUNK,
                path=p,
                doc_slug=session.doc_slug,
                message=f"Chunk '{p}' chưa được phân loại context_type qua stg_patch trước khi finalize.",
                remediation_hint="Nghĩa vụ thẩm định: Hãy đối soát nội dung chunk để xác định tính tự chứa hay có căn cứ phụ thuộc, sau đó sử dụng stg_patch để thiết lập context_type kèm giải trình thực tế trước khi nghiệm thu.",
            )

        chunk_edges = edges_by_source.get(p, [])
        if target_chunk.context_type == ContextType.SELF_CONTAINED:
            if chunk_edges:
                raise_staging_violation(
                    violation_code=StagingViolationCode.INVALID_RELATION_ON_SELF_CONTAINED,
                    path=p,
                    doc_slug=session.doc_slug,
                    message=f"Chunk '{p}' được phân loại SELF_CONTAINED nhưng lại tồn tại {len(chunk_edges)} cạnh quan hệ xuất phát từ nó.",
                    remediation_hint="Xung đột trạng thái: Chunk được khai báo SELF_CONTAINED nhưng lại có cạnh phụ thuộc xuất phát từ nó. Hãy kiểm tra lại: (1) Nếu chunk thực sự độc lập, hãy xóa các cạnh thừa bằng stg_remove_edges; (2) Nếu chunk có phụ thuộc, dùng stg_patch cập nhật context_type thành REQUIRES_EXTERNAL_CONTEXT.",
                )
            target_chunk.finalization_state = FinalizationState.FINALIZED_SELF_CONTAINED
        elif target_chunk.context_type == ContextType.REQUIRES_EXTERNAL_CONTEXT:
            if not chunk_edges:
                raise_staging_violation(
                    violation_code=StagingViolationCode.MISSING_RELATION_EDGE,
                    path=p,
                    doc_slug=session.doc_slug,
                    message=f"Chunk '{p}' được gắn nhãn REQUIRES_EXTERNAL_CONTEXT nhưng chưa có cạnh quan hệ nào được liên kết.",
                    remediation_hint="Xung đột trạng thái: Chunk được gắn nhãn REQUIRES_EXTERNAL_CONTEXT nhưng đồ thị chưa có cạnh liên kết. Đối soát: (1) Nếu chunk thực sự có viện dẫn, hãy tra cứu nút đích và tạo cạnh bằng stg_add_edges; (2) Nếu đã phân loại nhầm, dùng stg_patch để đính chính lại context_type thành SELF_CONTAINED kèm lý do.",
                )
            target_chunk.finalization_state = FinalizationState.FINALIZED_FULLY_LINKED

        target_chunk.review_status = ChunkReviewStatus.REVIEWED
        finalized_count += 1
        results.append({
            "path": target_chunk.path,
            "review_status": target_chunk.review_status,
            "finalization_state": target_chunk.finalization_state,
            "context_type": target_chunk.context_type,
        })

    now = applied_at or datetime.datetime.now(datetime.UTC)
    session.updated_at = now
    session.mutation_history.append(
        StagingMutationRecord(
            actor=actor,
            action_type="CHUNKS_FINALIZED",
            description=f"Finalized {finalized_count} chunks.",
            timestamp=now,
            diff_payload={"paths": sorted(target_paths), "finalized_count": finalized_count},
        )
    )
    return finalized_count, results


def unfinalize_chunks_in_session(
    session: StagingDocumentSession,
    paths: Sequence[str],
    actor: str = "AGENT",
    applied_at: datetime.datetime | None = None,
) -> tuple[int, list[dict[str, object]]]:
    """Reverts designated chunk paths to PENDING review status and UNFINALIZED state."""
    if session.status not in (StagingStatus.DRAFT, StagingStatus.AMENDMENT):
        raise CorpusDomainError(
            error_code=E_CORPUS_INTEGRITY_VIOLATION,
            message=f"Không thể chỉnh sửa phiên staging ở trạng thái '{session.status.value}'.",
            data={"doc_slug": session.doc_slug, "status": session.status.value},
        )

    target_paths = {validate_ltree_path(p) for p in paths}
    chunk_map = {c.path: c for c in session.chunks}

    missing_paths = [p for p in sorted(target_paths) if p not in chunk_map]
    if missing_paths:
        raise CorpusDomainError(
            error_code=E_INVALID_DOCUMENT_HIERARCHY,
            message=f"Các chunk sau không tồn tại trong phiên làm việc: {missing_paths}",
            data={"doc_slug": session.doc_slug, "missing_paths": missing_paths},
        )

    unfinalized_count = 0
    results: list[dict[str, object]] = []
    for p in sorted(target_paths):
        target_chunk = chunk_map[p]
        target_chunk.review_status = ChunkReviewStatus.PENDING
        target_chunk.finalization_state = FinalizationState.UNFINALIZED
        session.inspected_paths.discard(p)
        unfinalized_count += 1
        results.append({
            "path": target_chunk.path,
            "review_status": target_chunk.review_status,
            "finalization_state": target_chunk.finalization_state,
            "context_type": target_chunk.context_type,
        })

    now = applied_at or datetime.datetime.now(datetime.UTC)
    session.updated_at = now
    session.mutation_history.append(
        StagingMutationRecord(
            actor=actor,
            action_type="CHUNKS_UNFINALIZED",
            description=f"Unfinalized {unfinalized_count} chunks.",
            timestamp=now,
            diff_payload={"paths": sorted(target_paths), "unfinalized_count": unfinalized_count},
        )
    )
    return unfinalized_count, results


def validate_and_attach_edges_to_session(
    session: StagingDocumentSession,
    edges: Sequence[StagingEdge | StagingEdgeInput | dict[str, object]],
    actor: str = "AGENT",
    applied_at: datetime.datetime | None = None,
) -> tuple[int, list[StagingEdge]]:
    """Pre-commit lints candidate relation edges and attaches valid ones to the session."""
    if session.status not in (StagingStatus.DRAFT, StagingStatus.AMENDMENT):
        raise CorpusDomainError(
            error_code=E_CORPUS_INTEGRITY_VIOLATION,
            message=f"Không thể chỉnh sửa phiên staging ở trạng thái '{session.status.value}'.",
            data={"doc_slug": session.doc_slug, "status": session.status.value},
        )

    valid_paths = {c.path for c in session.chunks}
    chunks_by_path = {c.path: c for c in session.chunks}
    doc_prefix = sanitize_ltree_label(session.doc_slug)

    existing_edges: dict[tuple[str, str, str, int | None, int | None], StagingEdge] = {
        (
            e.source_path,
            e.target_path,
            e.relation_type.value if hasattr(e.relation_type, "value") else str(e.relation_type),
            e.char_start,
            e.char_end,
        ): e
        for e in session.edges
    }

    for raw_edge in edges:
        if isinstance(raw_edge, StagingEdge):
            new_edge = raw_edge.model_copy()
        elif isinstance(raw_edge, StagingEdgeInput):
            new_edge = StagingEdge(
                source_path=raw_edge.source_path,
                target_path=raw_edge.target_path,
                relation_type=raw_edge.relation_type,
                anchor_text=raw_edge.anchor_text,
            )
        elif isinstance(raw_edge, BaseModel):
            new_edge = StagingEdge.model_validate(raw_edge.model_dump())
        elif isinstance(raw_edge, dict):
            new_edge = StagingEdge.model_validate(raw_edge)
        else:
            raise CorpusDomainError(
                error_code=E_AST_GROUNDING_VALIDATION,
                message=f"Invalid edge payload type: {type(raw_edge)}",
            )

        clean_src = validate_ltree_path(new_edge.source_path)
        clean_tgt = validate_ltree_path(new_edge.target_path)

        if not clean_tgt:
            raise CorpusDomainError(
                error_code=E_AST_GROUNDING_VALIDATION,
                message=f"Invalid edge from '{clean_src}': must specify target_path.",
                data={"doc_slug": session.doc_slug, "source_path": clean_src},
            )

        if clean_src not in valid_paths:
            raise CorpusDomainError(
                error_code=E_AST_GROUNDING_VALIDATION,
                message=f"Invalid edge source path '{clean_src}': path does not exist in staged document '{session.doc_slug}'.",
                data={"doc_slug": session.doc_slug, "source_path": clean_src},
            )

        src_chunk = chunks_by_path.get(clean_src)
        if (
            src_chunk
            and src_chunk.review_status == ChunkReviewStatus.REVIEWED
            and (
                src_chunk.context_type.value
                if hasattr(src_chunk.context_type, "value")
                else str(src_chunk.context_type)
            )
            == "SELF_CONTAINED"
        ):
            raise CorpusDomainError(
                error_code=E_AST_GROUNDING_VALIDATION,
                message=f"Không thể thêm cạnh phụ thuộc từ chunk '{clean_src}' đã hoàn thiện với trạng thái SELF_CONTAINED. Hãy dùng stg_patch cập nhật context_type trước.",
                data={"doc_slug": session.doc_slug, "source_path": clean_src},
            )

        if clean_src == clean_tgt:
            raise CorpusDomainError(
                error_code=E_AST_GROUNDING_VALIDATION,
                message=f"Self-referencing edge loop detected on '{clean_src}'.",
                data={"doc_slug": session.doc_slug, "path": clean_src},
            )

        prefix = f"{clean_tgt}."
        matching_leaves = [p for p in valid_paths if p.startswith(prefix) and p != clean_src]

        if clean_tgt not in valid_paths:
            if matching_leaves:
                resolved_targets = sorted(matching_leaves)
            elif clean_tgt.startswith(f"{doc_prefix}."):
                if any(p == clean_src for p in valid_paths if p.startswith(prefix)):
                    raise CorpusDomainError(
                        error_code=E_AST_GROUNDING_VALIDATION,
                        message=f"Self-referencing edge loop detected on '{clean_src}'.",
                        data={"doc_slug": session.doc_slug, "path": clean_src},
                    )
                raise CorpusDomainError(
                    error_code=E_AST_GROUNDING_VALIDATION,
                    message=f"Invalid edge target path '{clean_tgt}': intra-document target does not exist in staged document '{session.doc_slug}'.",
                    data={"doc_slug": session.doc_slug, "target_path": clean_tgt},
                )
            else:
                resolved_targets = [clean_tgt]
        else:
            resolved_targets = [clean_tgt]

        # Deterministic anchor text resolution
        if new_edge.anchor_text is not None and (new_edge.char_start is None or new_edge.char_end is None):
            if src_chunk is None:
                raise CorpusDomainError(
                    error_code=E_AST_GROUNDING_VALIDATION,
                    message=f"Invalid edge source path '{clean_src}': path does not exist in staged document '{session.doc_slug}'.",
                    data={"doc_slug": session.doc_slug, "source_path": clean_src},
                )
            span = find_normalized_span(src_chunk.verbatim_text, new_edge.anchor_text)
            if span is None:
                raise CorpusDomainError(
                    error_code=E_AST_GROUNDING_VALIDATION,
                    message=(
                        f"Đoạn trích viện dẫn (anchor_text) '{new_edge.anchor_text}' không tồn tại "
                        f"trong nội dung gốc của chunk nguồn '{clean_src}'."
                    ),
                    data={
                        "doc_slug": session.doc_slug,
                        "source_path": clean_src,
                        "anchor_text": new_edge.anchor_text,
                    },
                )
            new_edge.char_start, new_edge.char_end = span

        # Boundary checks when char_start and char_end are present
        if new_edge.char_start is not None and new_edge.char_end is not None:
            if src_chunk is None:
                raise CorpusDomainError(
                    error_code=E_AST_GROUNDING_VALIDATION,
                    message=f"Invalid edge source path '{clean_src}': path does not exist in staged document '{session.doc_slug}'.",
                    data={"doc_slug": session.doc_slug, "source_path": clean_src},
                )
            src_len = len(src_chunk.verbatim_text)
            if new_edge.char_end > src_len:
                raise CorpusDomainError(
                    error_code=E_AST_GROUNDING_VALIDATION,
                    message=(
                        f"Tọa độ span [char_start={new_edge.char_start}, char_end={new_edge.char_end}] "
                        f"vượt quá độ dài văn bản của chunk nguồn '{clean_src}' ({src_len} ký tự)."
                    ),
                    data={
                        "doc_slug": session.doc_slug,
                        "source_path": clean_src,
                        "char_start": new_edge.char_start,
                        "char_end": new_edge.char_end,
                        "text_len": src_len,
                    },
                )
            if new_edge.anchor_text is not None:
                actual_snippet = src_chunk.verbatim_text[new_edge.char_start : new_edge.char_end]
                if normalize_whitespace(actual_snippet) != normalize_whitespace(new_edge.anchor_text):
                    raise CorpusDomainError(
                        error_code=E_AST_GROUNDING_VALIDATION,
                        message=(
                            f"Tọa độ span [{new_edge.char_start}:{new_edge.char_end}] trích xuất chuỗi '{actual_snippet}', "
                            f"không khớp với anchor_text đã khai báo '{new_edge.anchor_text}'."
                        ),
                        data={
                            "doc_slug": session.doc_slug,
                            "source_path": clean_src,
                            "expected": new_edge.anchor_text,
                            "actual": actual_snippet,
                        },
                    )

        for tgt_path in resolved_targets:
            edge_copy = new_edge.model_copy()
            edge_copy.source_path = clean_src
            edge_copy.target_path = tgt_path
            rel_str = (
                edge_copy.relation_type.value
                if hasattr(edge_copy.relation_type, "value")
                else str(edge_copy.relation_type)
            )
            key = (clean_src, tgt_path, rel_str, edge_copy.char_start, edge_copy.char_end)
            existing_edges[key] = edge_copy

    session.edges = list(existing_edges.values())
    now = applied_at or datetime.datetime.now(datetime.UTC)
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
    applied_at: datetime.datetime | None = None,
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
            message=f"Đường dẫn cũ '{clean_old}' không thuộc tài liệu '{session.doc_slug}'.",
            data={"doc_slug": session.doc_slug, "path": clean_old},
        )

    if not (clean_new == doc_prefix or clean_new.startswith(f"{doc_prefix}.")):
        raise CorpusDomainError(
            error_code=E_INVALID_DOCUMENT_HIERARCHY,
            message=f"Đường dẫn mới '{clean_new}' không thuộc tài liệu '{session.doc_slug}'.",
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

    existing_edges: dict[tuple[str, str, str, int | None, int | None], StagingEdge] = {}
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

        rel_str = e.relation_type.value if hasattr(e.relation_type, "value") else str(e.relation_type)
        key = (e.source_path, e.target_path, rel_str, e.char_start, e.char_end)
        existing_edges[key] = e

    session.edges = list(existing_edges.values())
    session.chunks.sort(key=lambda x: x.path)

    now = applied_at or datetime.datetime.now(datetime.UTC)
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
