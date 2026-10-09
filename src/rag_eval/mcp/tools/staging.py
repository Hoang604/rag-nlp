from __future__ import annotations

import datetime
from collections.abc import Sequence

import asyncpg

from rag_eval.exceptions import (
    E_AST_GROUNDING_VALIDATION,
    E_INVALID_DOCUMENT_HIERARCHY,
    CorpusDomainError,
)
from rag_eval.ingestion.staging.manager import StagingManager, group_pending_chunks
from rag_eval.ingestion.staging.models import (
    DEFAULT_STAGING_POLL_LIMIT,
    MAX_STAGING_POLL_LIMIT,
    MIN_STAGING_POLL_LIMIT,
    ChunkFinalizeStatus,
    ChunkProgressStats,
    ChunkReviewStatus,
    GrepHit,
    StagingChunk,
    StagingChunkDelta,
    StagingEdge,
    StagingEdgeFilter,
    StagingEdgeInput,
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
    StgRemoveEdgesResult,
    StgReopenResult,
    StgReparentResult,
    StgUncommitResult,
    StgUnfinalizeResult,
)
from rag_eval.ingestion.staging.session import StagingDocumentSession
from rag_eval.schemas import (
    validate_ltree_path,
)


class CorpusStagingTools:
    """Encapsulates local staging session operations on disk with transparent database hydration."""

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
        if end_line < start_line:
            raise CorpusDomainError(
                error_code=E_AST_GROUNDING_VALIDATION,
                message=f"Dòng kết thúc end_line ({end_line}) không được nhỏ hơn dòng bắt đầu start_line ({start_line}).",
                data={"doc_slug": doc_slug, "start_line": start_line, "end_line": end_line},
            )
        window_size = end_line - start_line + 1
        if window_size > 200:
            raise CorpusDomainError(
                error_code=E_AST_GROUNDING_VALIDATION,
                message=(
                    f"Cửa sổ dòng yêu cầu ({window_size} dòng) vượt quá giới hạn tối đa cho phép "
                    f"là 200 dòng (từ dòng {start_line} đến {end_line})."
                ),
                data={
                    "doc_slug": doc_slug,
                    "start_line": start_line,
                    "end_line": end_line,
                    "window_size": window_size,
                    "max_allowed": 200,
                },
            )
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
        pattern: str,
        doc_slug: str | None = None,
        is_regex: bool = False,
        case_sensitive: bool = False,
        search_in: StgGrepScope = "ALL",
        limit: int = 50,
    ) -> StgGrepResult:
        if doc_slug:
            session = await self._ensure_session(doc_slug)
            matches = session.grep(
                pattern=pattern,
                is_regex=is_regex,
                case_sensitive=case_sensitive,
                search_in=search_in,
                limit=limit,
            )
        else:
            matches = self._staging.grep_all_sessions(
                pattern=pattern,
                is_regex=is_regex,
                case_sensitive=case_sensitive,
                search_in=search_in,
                limit=limit,
            )
        hits = [
            GrepHit(
                rank=idx,
                path=m.path,
                doc_slug=m.doc_slug,
                snippet=m.match_snippet,
                field_matched=m.field_matched,
                start_line=m.start_line,
                end_line=m.end_line,
            )
            for idx, m in enumerate(matches, start=1)
        ]
        return StgGrepResult(
            doc_slug=doc_slug,
            pattern=pattern,
            is_regex=is_regex,
            total_matches=len(hits),
            hits=hits,
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
        edges: Sequence[StagingEdge | StagingEdgeInput | dict[str, object]],
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
        now = datetime.datetime.now(datetime.UTC)
        await self._ensure_session(doc_slug)
        session = self._staging.commit_session(doc_slug=doc_slug, actor="AGENT")
        return StgCommitResult(
            doc_slug=session.doc_slug,
            status=session.status.value,
            total_chunks=len(session.chunks),
            total_edges=len(session.edges),
            committed_at=now.isoformat(),
            message=f"Phiên làm việc cho tài liệu '{doc_slug}' đã được chuyển sang trạng thái AGENT_COMMITTED. Dữ liệu đã được ghi nhận và sẵn sàng cho rà soát, lưu trữ.",
        )

    async def stg_uncommit(
        self,
        doc_slug: str,
        reason: str = "",
    ) -> StgUncommitResult:
        now = datetime.datetime.now(datetime.UTC)
        await self._ensure_session(doc_slug)
        session = self._staging.uncommit_session(
            doc_slug=doc_slug,
            actor="AGENT",
            reason=reason or "Agent uncommitted session",
        )
        return StgUncommitResult(
            doc_slug=session.doc_slug,
            status=session.status.value,
            total_chunks=len(session.chunks),
            total_edges=len(session.edges),
            uncommitted_at=now.isoformat(),
            message=f"Phiên làm việc cho tài liệu '{doc_slug}' đã được mở lại ở trạng thái {session.status.value}. Các công cụ stg_patch, stg_add_edges, stg_finalize_chunks đã sẵn sàng.",
        )

    async def stg_poll_pending_chunks(
        self,
        doc_slug: str,
        limit: int = DEFAULT_STAGING_POLL_LIMIT,
        path_prefix: str | None = None,
    ) -> StgPollPendingResult:
        session = await self._ensure_session(doc_slug)
        clamped_limit = max(MIN_STAGING_POLL_LIMIT, min(limit, MAX_STAGING_POLL_LIMIT))
        chunks, stats = self._staging.poll_pending_chunks(
            doc_slug=doc_slug, limit=clamped_limit, path_prefix=path_prefix
        )
        for c in chunks:
            session.inspected_paths.add(c.path)
        self._staging.save_session(session)
        groups = group_pending_chunks(chunks=chunks, session=session)
        stats_dict = dict(stats)
        progress_stats = ChunkProgressStats.model_validate(stats_dict)
        pending_val = int(str(stats.get("pending_count", 0)))
        return StgPollPendingResult(
            doc_slug=doc_slug,
            progress=progress_stats,
            limit=clamped_limit,
            has_more=pending_val > len(chunks),
            returned_chunks=len(chunks),
            groups=groups,
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

    async def stg_unfinalize_chunks(
        self,
        doc_slug: str,
        paths: list[str],
    ) -> StgUnfinalizeResult:
        await self._ensure_session(doc_slug)
        session, unfinalized_count, raw_results = self._staging.unfinalize_chunks(
            doc_slug=doc_slug, paths=paths, actor="AGENT"
        )
        pending_remaining = sum(
            1 for c in session.chunks if c.review_status == ChunkReviewStatus.PENDING
        )
        results = [
            ChunkFinalizeStatus.model_validate(r)
            for r in raw_results
        ]
        return StgUnfinalizeResult(
            doc_slug=doc_slug,
            status="SUCCESS",
            unfinalized_count=unfinalized_count,
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

    async def stg_remove_edges(
        self,
        doc_slug: str,
        edges: Sequence[StagingEdgeFilter | dict[str, object]],
    ) -> StgRemoveEdgesResult:
        """Removes relational graph edge(s) matching filters from the staging session."""
        await self._ensure_session(doc_slug)
        session, removed_count = self._staging.remove_edges(
            doc_slug=doc_slug,
            filters=edges,
            actor="AGENT",
        )
        return StgRemoveEdgesResult(
            doc_slug=doc_slug,
            status="SUCCESS",
            removed_count=removed_count,
            total_edges=len(session.edges),
            message=f"Removed {removed_count} edge(s) matching {len(edges)} filter(s).",
        )

    async def stg_validate(self, doc_slug: str) -> dict[str, object]:
        """Runs pre-flight validation rules on the staging session and returns evaluation report."""
        session = await self._ensure_session(doc_slug)
        from rag_eval.web.services.validation import PreFlightValidator

        validator = PreFlightValidator()
        result = validator.validate(session)
        return result.model_dump(mode="json")
