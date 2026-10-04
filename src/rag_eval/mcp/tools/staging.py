from __future__ import annotations

import datetime
from collections.abc import Sequence

import asyncpg
from pydantic import BaseModel

from rag_eval.exceptions import (
    E_AST_GROUNDING_VALIDATION,
    E_INVALID_DOCUMENT_HIERARCHY,
    CorpusDomainError,
)
from rag_eval.ingestion.staging.manager import StagingManager
from rag_eval.ingestion.staging.models import (
    ChunkFinalizeStatus,
    ChunkProgressStats,
    ChunkReviewStatus,
    RelationTypeFilter,
    StagingChunk,
    StagingChunkDelta,
    StagingEdge,
    StagingEdgeFilter,
    StagingStatus,
    StagingStatusFilter,
    StgAddEdgesResult,
    StgCommitResult,
    StgFinalizeResult,
    StgGetChunkResult,
    StgGetRawResult,
    StgGrepResult,
    StgGrepScope,
    StgListSessionsResult,
    StgPatchResult,
    StgPollPendingResult,
    StgPreviewHit,
    StgPreviewResult,
    StgRemoveEdgeResult,
    StgReopenResult,
    StgReparentResult,
    get_staging_poll_limit,
)
from rag_eval.ingestion.staging.session import StagingDocumentSession
from rag_eval.schemas import (
    sanitize_ltree_label,
    validate_ltree_path,
)


class CorpusStagingTools:
    """Encapsulates local staging session operations on disk (.cache/stg) with transparent database hydration."""

    def __init__(
        self,
        staging_manager: StagingManager | None = None,
        pool: asyncpg.Pool | None = None,
    ) -> None:
        self._staging = staging_manager or StagingManager()
        self._pool = pool

    async def _get_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            from rag_eval.db.connection import get_db_pool

            self._pool = await get_db_pool()
        return self._pool

    async def _ensure_session(self, doc_slug: str) -> StagingDocumentSession:
        if self._staging.session_exists(doc_slug):
            return self._staging.load_session(doc_slug)
        return await self._staging.load_or_hydrate_session(
            doc_slug=doc_slug, pool=await self._get_pool()
        )

    async def stg_preview(
        self,
        doc_slug: str,
        path_prefix: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> StgPreviewResult:
        session = await self._ensure_session(doc_slug)
        chunks = session.chunks
        if path_prefix:
            clean_pre = validate_ltree_path(path_prefix)
            chunks = [c for c in chunks if c.path.startswith(clean_pre)]

        total_matched = len(chunks)
        windowed_chunks = chunks[offset : offset + limit]
        has_more = (offset + limit) < total_matched

        preview_hits = [
            StgPreviewHit(
                path=c.path,
                preview_text=c.verbatim_text[:120] + ("..." if len(c.verbatim_text) > 120 else ""),
                char_length=c.char_length or len(c.verbatim_text),
                is_truncated=len(c.verbatim_text) > 120,
                metadata=(c.metadata.model_dump() if isinstance(c.metadata, BaseModel) else dict(c.metadata or {})),
            )
            for c in windowed_chunks
        ]

        return StgPreviewResult(
            doc_slug=session.doc_slug,
            title=session.title,
            total_chunks=len(session.chunks),
            total_edges=len(session.edges),
            total_matched=total_matched,
            limit=limit,
            offset=offset,
            has_more=has_more,
            chunks=preview_hits,
        )

    async def stg_get_chunk(self, doc_slug: str, path: str) -> StgGetChunkResult:
        session = await self._ensure_session(doc_slug)
        clean_path = validate_ltree_path(path)
        chunk = session.get_chunk(clean_path)
        if chunk is None:
            raise CorpusDomainError(
                error_code=E_INVALID_DOCUMENT_HIERARCHY,
                message=f"Chunk '{clean_path}' không tồn tại trong phiên làm việc cho tài liệu '{doc_slug}'.",
                data={"doc_slug": doc_slug, "path": clean_path},
            )
        self._staging.save_session(session)
        return StgGetChunkResult(doc_slug=doc_slug, chunk=chunk)

    async def stg_get_raw(
        self, doc_slug: str, start_line: int = 1, end_line: int = 100
    ) -> StgGetRawResult:
        session = await self._ensure_session(doc_slug)
        window = session.get_raw_window(start_line=start_line, end_line=end_line)
        self._staging.save_session(session)
        return StgGetRawResult(
            doc_slug=window.doc_slug,
            start_line=window.start_line,
            end_line=window.end_line,
            total_lines=window.total_lines,
            content=window.content,
        )

    async def stg_grep(
        self,
        doc_slug: str,
        pattern: str,
        is_regex: bool = False,
        case_sensitive: bool = False,
        search_in: StgGrepScope = "ALL",
        limit: int = 50,
    ) -> StgGrepResult:
        session = await self._ensure_session(doc_slug)
        matches = session.grep(
            pattern=pattern,
            is_regex=is_regex,
            case_sensitive=case_sensitive,
            search_in=search_in,
            limit=limit,
        )
        return StgGrepResult(
            doc_slug=doc_slug,
            pattern=pattern,
            is_regex=is_regex,
            total_matches=len(matches),
            matches=matches,
        )

    async def stg_patch(
        self,
        doc_slug: str,
        updated_chunks: Sequence[StagingChunkDelta | StagingChunk | dict[str, object]] | None = None,
        removed_paths: list[str] | None = None,
        cascade_breadcrumbs: bool = True,
    ) -> StgPatchResult:
        await self._ensure_session(doc_slug)
        session = self._staging.patch_chunks(
            doc_slug=doc_slug,
            updated_chunks=updated_chunks,
            removed_paths=removed_paths,
            cascade_breadcrumbs=cascade_breadcrumbs,
            actor="AGENT",
        )
        last_diff = (
            session.mutation_history[-1].diff_payload
            if session.mutation_history and session.mutation_history[-1].diff_payload
            else {}
        )
        raw_fields = last_diff.get("fields_modified")
        return StgPatchResult(
            doc_slug=doc_slug,
            status="SUCCESS",
            updated_count=int(str(last_diff.get("updated_count") or len(updated_chunks or []))),
            cascaded_count=int(str(last_diff.get("cascaded_count") or 0)),
            removed_count=int(str(last_diff.get("removed_count") or len(removed_paths or []))),
            total_chunks_after_patch=len(session.chunks),
            fields_modified=[str(f) for f in raw_fields] if isinstance(raw_fields, list) else [],
        )

    async def stg_add_edges(
        self,
        doc_slug: str,
        edges: Sequence[StagingEdge | dict[str, object]],
    ) -> StgAddEdgesResult:
        await self._ensure_session(doc_slug)
        session = self._staging.add_edges(
            doc_slug=doc_slug,
            edges=edges,
            actor="AGENT",
        )
        return StgAddEdgesResult(
            doc_slug=doc_slug,
            status="SUCCESS",
            total_edges=len(session.edges),
        )

    async def stg_reparent(
        self,
        doc_slug: str,
        old_path_prefix: str,
        new_path_prefix: str,
        dry_run: bool = False,
    ) -> StgReparentResult:
        await self._ensure_session(doc_slug)
        _session, result = self._staging.reparent_node(
            doc_slug=doc_slug,
            old_path_prefix=old_path_prefix,
            new_path_prefix=new_path_prefix,
            dry_run=dry_run,
            actor="AGENT",
        )
        return result

    async def stg_commit(self, doc_slug: str) -> StgCommitResult:
        session = await self._ensure_session(doc_slug)

        unreviewed = [
            c.path
            for c in session.chunks
            if c.review_status == ChunkReviewStatus.PENDING
        ]
        if unreviewed:
            raise CorpusDomainError(
                error_code=E_AST_GROUNDING_VALIDATION,
                message=(
                    f"Không thể commit tài liệu '{doc_slug}': còn {len(unreviewed)}/{len(session.chunks)} "
                    "chunk ở trạng thái PENDING. Reviewer/Agent bắt buộc phải rà soát "
                    "100% các chunk trước khi phiên làm việc được phép cam kết."
                ),
                data={
                    "doc_slug": doc_slug,
                    "unreviewed_count": len(unreviewed),
                    "total_chunks": len(session.chunks),
                    "unreviewed_sample": unreviewed[:5],
                },
            )

        chunk_paths = {c.path for c in session.chunks}
        sanitized_slug = sanitize_ltree_label(doc_slug)
        for edge in session.edges:
            if edge.source_path not in chunk_paths:
                raise CorpusDomainError(
                    error_code=E_AST_GROUNDING_VALIDATION,
                    message=f"Invalid edge source path '{edge.source_path}': chunk path does not exist in document '{doc_slug}'.",
                    data={"doc_slug": doc_slug, "source_path": edge.source_path},
                )
            if (
                edge.target_path
                and (
                    edge.target_path.startswith(f"{sanitized_slug}.")
                    or edge.target_path.startswith(f"{doc_slug}.")
                )
                and edge.target_path not in chunk_paths
            ):
                raise CorpusDomainError(
                    error_code=E_AST_GROUNDING_VALIDATION,
                    message=f"Invalid edge target path '{edge.target_path}': internal chunk path does not exist in document '{doc_slug}'.",
                    data={"doc_slug": doc_slug, "target_path": edge.target_path},
                )

        now = datetime.datetime.now(datetime.UTC)
        session = self._staging.update_session_status(
            doc_slug=doc_slug,
            status=StagingStatus.AGENT_COMMITTED,
            actor="AGENT",
            description=f"Agent completed staging session review and committed for {doc_slug}.",
        )

        return StgCommitResult(
            doc_slug=session.doc_slug,
            status=StagingStatus.AGENT_COMMITTED.value,
            total_chunks=len(session.chunks),
            total_edges=len(session.edges),
            committed_at=now.isoformat(),
            message=f"Phiên làm việc cho tài liệu '{doc_slug}' đã được chuyển sang trạng thái AGENT_COMMITTED. Dữ liệu được ghi vào WAL và sẵn sàng cho rà soát, lưu trữ.",
        )

    async def stg_poll_pending_chunks(
        self,
        doc_slug: str,
        limit: int = 5,
        path_prefix: str | None = None,
    ) -> StgPollPendingResult:
        await self._ensure_session(doc_slug)
        configured_limit = get_staging_poll_limit()
        clamped_limit = min(limit or configured_limit, configured_limit)
        chunks, stats = self._staging.poll_pending_chunks(
            doc_slug=doc_slug, limit=clamped_limit, path_prefix=path_prefix
        )
        stats_dict = dict(stats)
        progress_stats = ChunkProgressStats.model_validate(stats_dict)
        pending_val = int(str(stats.get("pending_count", 0)))
        return StgPollPendingResult(
            doc_slug=doc_slug,
            progress=progress_stats,
            limit=clamped_limit,
            has_more=pending_val > len(chunks),
            chunks=chunks,
        )

    async def stg_finalize_chunks(
        self,
        doc_slug: str,
        paths: list[str],
    ) -> StgFinalizeResult:
        await self._ensure_session(doc_slug)
        session, finalized_count, raw_results = self._staging.finalize_chunks(
            doc_slug=doc_slug, paths=paths, actor="AGENT"
        )
        pending_remaining = sum(
            1 for c in session.chunks if c.review_status == ChunkReviewStatus.PENDING
        )
        results = [
            ChunkFinalizeStatus.model_validate(r)
            for r in raw_results
        ]
        return StgFinalizeResult(
            doc_slug=doc_slug,
            status="SUCCESS",
            finalized_count=finalized_count,
            pending_remaining=pending_remaining,
            paths=paths,
            results=results,
        )

    async def stg_list_sessions(
        self, status: StagingStatusFilter | None = None
    ) -> StgListSessionsResult:
        summaries = self._staging.list_sessions()
        if status:
            clean_status = status.strip().upper()
            summaries = [
                s
                for s in summaries
                if s.status.value.upper() == clean_status
                or s.status.name.upper() == clean_status
            ]
        return StgListSessionsResult(
            total_sessions=len(summaries),
            sessions=summaries,
        )

    async def stg_reopen_session(
        self,
        doc_slug: str,
        reason: str = "",
    ) -> StgReopenResult:
        """Reopens a PROMOTED document session into AMENDMENT status for patching and linkage."""
        now = datetime.datetime.now(datetime.UTC)
        await self._ensure_session(doc_slug)
        session = self._staging.reopen_session_for_amendment(
            doc_slug=doc_slug,
            actor="AGENT",
            reason=reason or "Agent reopened session for amendment / errata",
        )
        return StgReopenResult(
            doc_slug=doc_slug,
            status=session.status.value,
            total_chunks=len(session.chunks),
            reopened_at=now.isoformat(),
            message=f"Phiên làm việc cho tài liệu '{doc_slug}' đã được mở lại ở trạng thái AMENDMENT. Các công cụ stg_patch, stg_add_edges, stg_finalize_chunks đã sẵn sàng.",
        )

    async def stg_remove_edge(
        self,
        doc_slug: str,
        source_path: str = "",
        target_path: str | None = None,
        relation_type: RelationTypeFilter | None = None,
        clear_all_targets: bool = False,
        edges: Sequence[StagingEdgeFilter | dict[str, object]] | None = None,
    ) -> StgRemoveEdgeResult:
        """Removes relational graph edge(s) from the staging session."""
        await self._ensure_session(doc_slug)

        if edges:
            session, removed_count = self._staging.remove_edges(
                doc_slug=doc_slug,
                filters=edges,
                actor="AGENT",
            )
            target_repr = f"{len(edges)} edge filter(s)"
        else:
            if not source_path:
                raise CorpusDomainError(
                    error_code=E_AST_GROUNDING_VALIDATION,
                    message="Bắt buộc phải cung cấp 'source_path' hoặc danh sách 'edges' khi xóa cạnh quan hệ đồ thị.",
                    data={"doc_slug": doc_slug},
                )
            if not target_path and not clear_all_targets:
                raise CorpusDomainError(
                    error_code=E_AST_GROUNDING_VALIDATION,
                    message=(
                        f"Thao tác xóa cạnh từ '{source_path}' yêu cầu phải chỉ định 'target_path' "
                        "để xác định đúng cạnh cần xóa. Nếu thực sự muốn xóa toàn bộ mọi cạnh xuất phát từ nút này, "
                        "bắt buộc phải đặt 'clear_all_targets=True'."
                    ),
                    data={"doc_slug": doc_slug, "source_path": source_path},
                )
            flt = StagingEdgeFilter(
                source_path=source_path,
                target_path=target_path,
                relation_type=relation_type,
                clear_all_targets=clear_all_targets,
            )
            session, removed_count = self._staging.remove_edges(
                doc_slug=doc_slug,
                filters=[flt],
                actor="AGENT",
            )
            target_repr = target_path or ("all targets" if clear_all_targets else "unknown")

        return StgRemoveEdgeResult(
            doc_slug=doc_slug,
            status="SUCCESS",
            removed_count=removed_count,
            total_edges=len(session.edges),
            message=f"Removed {removed_count} edge(s) from '{source_path or 'batch'}' to '{target_repr}' ({relation_type or 'ANY'}).",
        )

    async def stg_validate(self, doc_slug: str) -> dict[str, object]:
        """Runs pre-flight validation rules on the staging session and returns evaluation report."""
        session = await self._ensure_session(doc_slug)
        from rag_eval.web.services.validation import PreFlightValidator

        validator = PreFlightValidator()
        result = validator.validate(session)
        return result.model_dump(mode="json")
