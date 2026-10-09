from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Sequence
from pathlib import Path

import asyncpg
from pydantic import BaseModel

from rag_eval.exceptions import (
    E_AST_GROUNDING_VALIDATION,
    E_CORPUS_INTEGRITY_VIOLATION,
    CorpusDomainError,
)
from rag_eval.ingestion.staging.models import (
    DEFAULT_STAGING_DIR,
    ChunkReviewStatus,
    ContextType,
    PendingChunkGroup,
    PendingChunkLeaf,
    RelationType,
    StagingChunk,
    StagingChunkDelta,
    StagingEdge,
    StagingEdgeFilter,
    StagingEdgeInput,
    StagingGrepHit,
    StagingSessionSummary,
    StagingStatus,
    StgReparentResult,
)
from rag_eval.ingestion.staging.session import StagingDocumentSession
from rag_eval.ingestion.wal import GenesisSnapshot, WALRecord, WALSessionStore
from rag_eval.schemas import (
    sanitize_ltree_label,
    validate_ltree_path,
)

logger = logging.getLogger(__name__)


class StagingManager:
    """Manages disk-based staging sessions for two-phase document ingestion via WALSessionStore.

    Enforces strict single-path WAL directory architecture (.cache/stg/<sanitized_doc_slug>/).
    Zero defensive fallbacks, zero legacy flat file shims, and zero silent defaults.
    """

    def __init__(self, staging_dir: Path | str = DEFAULT_STAGING_DIR) -> None:
        self.staging_dir = Path(staging_dir)
        self.staging_dir.mkdir(parents=True, exist_ok=True)

    def _get_session_dir(self, doc_slug: str) -> Path:
        sanitized = sanitize_ltree_label(doc_slug)
        return self.staging_dir / sanitized

    def _get_wal_store(self, doc_slug: str) -> WALSessionStore:
        return WALSessionStore(self._get_session_dir(doc_slug))

    def create_session_from_raw(
        self,
        doc_slug: str,
        title: str,
        raw_text: str,
        metadata: dict[str, object] | None = None,
    ) -> StagingDocumentSession:
        """Initializes WAL directory session from raw text using DocumentIngestionEngine."""
        from rag_eval.ingestion.parser.engine import DocumentIngestionEngine

        engine = DocumentIngestionEngine()
        stg_chunks, stg_edges, doc_meta = engine.process_raw(
            doc_slug=doc_slug, title=title, raw_text=raw_text, metadata=metadata
        )

        wal_store = self._get_wal_store(doc_slug)
        genesis = GenesisSnapshot.create(
            doc_slug=doc_slug,
            title=title,
            raw_text=raw_text,
            metadata=doc_meta,
            initial_chunks=[c.model_dump(mode="json") for c in stg_chunks],
            initial_edges=[e.model_dump(mode="json") for e in stg_edges],
        )

        _, session = wal_store.init_genesis(genesis)
        return session

    def create_session_from_file(
        self,
        doc_slug: str,
        title: str,
        file_path: Path | str,
        metadata: dict[str, object] | None = None,
    ) -> StagingDocumentSession:
        """Initializes WAL directory session from a document file path on disk."""
        from rag_eval.ingestion.parser.engine import DocumentIngestionEngine

        engine = DocumentIngestionEngine()
        raw_text, stg_chunks, stg_edges, doc_meta = engine.process_file(
            doc_slug=doc_slug, title=title, file_path=file_path, metadata=metadata
        )

        wal_store = self._get_wal_store(doc_slug)
        genesis = GenesisSnapshot.create(
            doc_slug=doc_slug,
            title=title,
            raw_text=raw_text,
            metadata=doc_meta,
            initial_chunks=[c.model_dump(mode="json") for c in stg_chunks],
            initial_edges=[e.model_dump(mode="json") for e in stg_edges],
        )

        _, session = wal_store.init_genesis(genesis)
        return session

    def create_session_from_bytes(
        self,
        doc_slug: str,
        title: str,
        content: bytes,
        file_name: str,
        mime_type: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> StagingDocumentSession:
        """Initializes WAL directory session from binary file bytes in memory."""
        from rag_eval.ingestion.parser.engine import DocumentIngestionEngine

        engine = DocumentIngestionEngine()
        raw_text, stg_chunks, stg_edges, doc_meta = engine.process_bytes(
            doc_slug=doc_slug,
            title=title,
            content=content,
            file_name=file_name,
            mime_type=mime_type,
            metadata=metadata,
        )

        wal_store = self._get_wal_store(doc_slug)
        genesis = GenesisSnapshot.create(
            doc_slug=doc_slug,
            title=title,
            raw_text=raw_text,
            metadata=doc_meta,
            initial_chunks=[c.model_dump(mode="json") for c in stg_chunks],
            initial_edges=[e.model_dump(mode="json") for e in stg_edges],
        )

        _, session = wal_store.init_genesis(genesis)
        return session

    def session_exists(self, doc_slug: str) -> bool:
        """Returns True if local WAL session directory exists on disk."""
        return self._get_wal_store(doc_slug).exists()

    async def load_or_hydrate_session(
        self,
        doc_slug: str,
        pool: asyncpg.Pool | None = None,
    ) -> StagingDocumentSession:
        """Loads session from local disk WAL store; if missing and pool provided, hydrates from PostgreSQL."""
        wal_store = self._get_wal_store(doc_slug)
        if wal_store.exists():
            return wal_store.load_materialized_session()

        if pool is not None:
            return await self.hydrate_session_from_db(doc_slug=doc_slug, pool=pool)

        raise CorpusDomainError(
            error_code=E_CORPUS_INTEGRITY_VIOLATION,
            message=(
                f"Staging session for document '{doc_slug}' does not exist on disk at "
                f"{wal_store.session_dir} and no database pool was provided for hydration."
            ),
            data={"doc_slug": doc_slug, "staging_path": str(wal_store.session_dir)},
        )

    def load_session(self, doc_slug: str) -> StagingDocumentSession:
        """Loads an existing staging session from WAL store. Fails fast if directory does not exist."""
        wal_store = self._get_wal_store(doc_slug)
        if not wal_store.exists():
            raise CorpusDomainError(
                error_code=E_CORPUS_INTEGRITY_VIOLATION,
                message=f"Staging session for document '{doc_slug}' does not exist at {wal_store.session_dir}",
                data={"doc_slug": doc_slug, "staging_path": str(wal_store.session_dir)},
            )
        return wal_store.load_materialized_session()

    def save_session(self, session: StagingDocumentSession) -> Path:
        """Persists state.json checkpoint for fast read access."""
        wal_store = self._get_wal_store(session.doc_slug)
        return wal_store.save_checkpoint(session)

    def load_all_sessions(self) -> list[StagingDocumentSession]:
        """Loads every active WAL staging session on disk."""
        sessions: list[StagingDocumentSession] = []
        if not self.staging_dir.exists():
            return sessions

        for sub_dir in sorted(self.staging_dir.iterdir()):
            if not sub_dir.is_dir() or sub_dir.name.startswith("."):
                continue
            wal_store = WALSessionStore(sub_dir)
            if not wal_store.exists():
                continue
            try:
                sessions.append(wal_store.load_materialized_session())
            except (OSError, ValueError, CorpusDomainError):
                logger.warning("Skipping unreadable staging session at %s", sub_dir)

        return sessions

    def patch_chunks(
        self,
        doc_slug: str,
        updated_chunks: Sequence[StagingChunkDelta | StagingChunk | dict[str, object]] | None = None,
        removed_paths: list[str] | None = None,
        cascade_breadcrumbs: bool = True,
        actor: str = "AGENT",
    ) -> StagingDocumentSession:
        """Appends CHUNK_PATCHED record to WAL journal and updates materialized state."""
        wal_store = self._get_wal_store(doc_slug)
        if not wal_store.exists():
            raise CorpusDomainError(
                error_code=E_CORPUS_INTEGRITY_VIOLATION,
                message=f"Staging session for document '{doc_slug}' does not exist at {wal_store.session_dir}",
                data={"doc_slug": doc_slug},
            )

        session = wal_store.load_materialized_session()
        if session.status not in (StagingStatus.DRAFT, StagingStatus.AMENDMENT):
            raise CorpusDomainError(
                error_code=E_CORPUS_INTEGRITY_VIOLATION,
                message=f"Không thể chỉnh sửa phiên staging ở trạng thái '{session.status.value}'. Phiên làm việc phải ở trạng thái DRAFT hoặc AMENDMENT.",
                data={"doc_slug": doc_slug, "status": session.status.value},
            )

        parsed_deltas: list[StagingChunkDelta] = []
        if updated_chunks:
            for item in updated_chunks:
                if isinstance(item, StagingChunkDelta):
                    parsed_deltas.append(item)
                elif isinstance(item, StagingChunk):
                    parsed_deltas.append(
                        StagingChunkDelta(
                            path=item.path,
                            verbatim_text=item.verbatim_text,
                            contextualized_text=item.contextualized_text,
                            start_line=item.start_line,
                            end_line=item.end_line,
                            metadata=item.metadata,
                            context_type=item.context_type,
                        )
                    )
                elif isinstance(item, dict):
                    parsed_deltas.append(StagingChunkDelta.model_validate(item))

        payload = {
            "deltas": [d.model_dump(mode="json") for d in parsed_deltas],
            "removed_paths": removed_paths or [],
            "cascade_breadcrumbs": cascade_breadcrumbs,
        }
        _, session = wal_store.append_record(
            actor=actor,
            op_type="CHUNK_PATCHED",
            description=f"Patched {len(parsed_deltas)} chunks and removed {len(removed_paths or [])} paths.",
            payload=payload,
        )
        return session

    def add_edges(
        self,
        doc_slug: str,
        edges: Sequence[StagingEdge | StagingEdgeInput | dict[str, object]],
        actor: str = "AGENT",
    ) -> StagingDocumentSession:
        """Appends EDGES_ATTACHED record to WAL journal and updates materialized state."""
        wal_store = self._get_wal_store(doc_slug)
        if not wal_store.exists():
            raise CorpusDomainError(
                error_code=E_CORPUS_INTEGRITY_VIOLATION,
                message=f"Staging session for document '{doc_slug}' does not exist at {wal_store.session_dir}",
                data={"doc_slug": doc_slug},
            )

        session = wal_store.load_materialized_session()
        if session.status not in (StagingStatus.DRAFT, StagingStatus.AMENDMENT):
            raise CorpusDomainError(
                error_code=E_CORPUS_INTEGRITY_VIOLATION,
                message=f"Không thể chỉnh sửa phiên staging ở trạng thái '{session.status.value}'. Phiên làm việc phải ở trạng thái DRAFT hoặc AMENDMENT.",
                data={"doc_slug": doc_slug, "status": session.status.value},
            )

        parsed_edges: list[StagingEdge] = []
        for e in edges:
            if isinstance(e, StagingEdge):
                parsed_edges.append(e)
            elif isinstance(e, StagingEdgeInput):
                parsed_edges.append(
                    StagingEdge(
                        source_path=e.source_path,
                        target_path=e.target_path,
                        relation_type=e.relation_type,
                        anchor_text=e.anchor_text,
                    )
                )
            elif isinstance(e, dict):
                parsed_edges.append(StagingEdge.model_validate(e))
            elif isinstance(e, BaseModel):
                parsed_edges.append(StagingEdge.model_validate(e.model_dump()))

        payload = {
            "edges": [e.model_dump(mode="json") for e in parsed_edges],
        }
        _, session = wal_store.append_record(
            actor=actor,
            op_type="EDGES_ATTACHED",
            description=f"Attached {len(parsed_edges)} relation edges.",
            payload=payload,
        )
        return session

    def remove_edges(
        self,
        doc_slug: str,
        filters: Sequence[StagingEdgeFilter | dict[str, object]],
        actor: str = "AGENT",
    ) -> tuple[StagingDocumentSession, int]:
        """Appends EDGES_REMOVED record to WAL journal and updates materialized state."""
        wal_store = self._get_wal_store(doc_slug)
        if not wal_store.exists():
            raise CorpusDomainError(
                error_code=E_CORPUS_INTEGRITY_VIOLATION,
                message=f"Staging session for document '{doc_slug}' does not exist at {wal_store.session_dir}",
                data={"doc_slug": doc_slug},
            )
        session = wal_store.load_materialized_session()
        if session.status not in (StagingStatus.DRAFT, StagingStatus.AMENDMENT):
            raise CorpusDomainError(
                error_code=E_CORPUS_INTEGRITY_VIOLATION,
                message=f"Không thể chỉnh sửa phiên staging ở trạng thái '{session.status.value}'. Phiên làm việc phải ở trạng thái DRAFT hoặc AMENDMENT.",
                data={"doc_slug": doc_slug, "status": session.status.value},
            )

        from rag_eval.ingestion.staging.models import StagingEdgeFilter

        parsed_filters: list[StagingEdgeFilter] = []
        for f in filters:
            if isinstance(f, StagingEdgeFilter):
                parsed_filters.append(f)
            elif isinstance(f, dict):
                parsed_filters.append(StagingEdgeFilter.model_validate(f))

        if not parsed_filters:
            return session, 0

        initial_count = len(session.edges)
        payload = {
            "filters": [f.model_dump(mode="json") for f in parsed_filters],
        }
        _, session = wal_store.append_record(
            actor=actor,
            op_type="EDGES_REMOVED",
            description=f"Removed edges matching {len(parsed_filters)} filter(s).",
            payload=payload,
        )
        removed_count = initial_count - len(session.edges)
        return session, removed_count

    def reparent_node(
        self,
        doc_slug: str,
        old_path_prefix: str,
        new_path_prefix: str,
        dry_run: bool = False,
        actor: str = "AGENT",
    ) -> tuple[StagingDocumentSession, StgReparentResult]:
        """Validates reparenting; if not dry_run, appends SUBTREE_REPARENTED record to WAL."""
        session = self.load_session(doc_slug)
        result = session.reparent_subtree(
            old_path_prefix=old_path_prefix,
            new_path_prefix=new_path_prefix,
            dry_run=dry_run,
            actor=actor,
        )

        if not dry_run:
            wal_store = self._get_wal_store(doc_slug)
            payload = {
                "old_path_prefix": old_path_prefix,
                "new_path_prefix": new_path_prefix,
                "affected_chunks": result.affected_chunks_count,
                "affected_edges": result.affected_edges_count,
            }
            _, session = wal_store.append_record(
                actor=actor,
                op_type="SUBTREE_REPARENTED",
                description=f"Migrated subtree '{old_path_prefix}' to '{new_path_prefix}'.",
                payload=payload,
            )

        return session, result

    def list_sessions(self) -> list[StagingSessionSummary]:
        """Discovers and lists summaries of all WAL sessions in the staging directory."""
        summaries: list[StagingSessionSummary] = []
        if not self.staging_dir.exists():
            return summaries

        for sub_dir in sorted(self.staging_dir.iterdir()):
            if not sub_dir.is_dir() or sub_dir.name.startswith("."):
                continue
            wal_store = WALSessionStore(sub_dir)
            if not wal_store.exists():
                continue
            try:
                session = wal_store.load_materialized_session()
                summaries.append(
                    StagingSessionSummary(
                        doc_slug=session.doc_slug,
                        title=session.title,
                        status=session.status,
                        total_chunks=len(session.chunks),
                        total_edges=len(session.edges),
                        created_at=session.created_at,
                        updated_at=session.updated_at,
                        committed_at=session.committed_at,
                        promoted_at=session.promoted_at,
                    )
                )
            except (json.JSONDecodeError, ValueError, KeyError, OSError, CorpusDomainError) as exc:
                logger.warning("Skipping unreadable staging session directory %s: %s", sub_dir, exc)

        return summaries

    def grep_all_sessions(
        self,
        pattern: str,
        is_regex: bool = False,
        case_sensitive: bool = False,
        search_in: str = "ALL",
        limit: int = 50,
    ) -> list[StagingGrepHit]:
        """Searches across all discovered staging sessions in the staging directory."""
        all_hits: list[StagingGrepHit] = []
        for summary in self.list_sessions():
            session = self.load_session(summary.doc_slug)
            hits = session.grep(
                pattern=pattern,
                is_regex=is_regex,
                case_sensitive=case_sensitive,
                search_in=search_in,
                limit=limit - len(all_hits),
            )
            all_hits.extend(hits)
            if len(all_hits) >= limit:
                break
        return all_hits[:limit]

    def update_session_status(
        self,
        doc_slug: str,
        status: StagingStatus,
        actor: str,
        description: str,
    ) -> StagingDocumentSession:
        """Appends status transition record to WAL journal and updates materialized state."""
        wal_store = self._get_wal_store(doc_slug)
        if not wal_store.exists():
            raise CorpusDomainError(
                error_code=E_CORPUS_INTEGRITY_VIOLATION,
                message=f"Staging session for document '{doc_slug}' does not exist at {wal_store.session_dir}",
                data={"doc_slug": doc_slug},
            )

        if status in (StagingStatus.AGENT_COMMITTED, StagingStatus.APPROVED):
            current_session = wal_store.load_materialized_session()
            unreviewed = [c.path for c in current_session.chunks if c.review_status != ChunkReviewStatus.REVIEWED]
            if unreviewed:
                raise CorpusDomainError(
                    error_code=E_AST_GROUNDING_VALIDATION,
                    message=f"Cannot transition to {status.value} with {len(unreviewed)} unreviewed chunk(s). All chunks must be REVIEWED.",
                    data={"unreviewed_count": len(unreviewed), "sample_paths": unreviewed[:10]},
                )

        if status in (StagingStatus.DRAFT, StagingStatus.AMENDMENT):
            current_session = wal_store.load_materialized_session()
            if current_session.status in (StagingStatus.PROMOTED, StagingStatus.APPROVED):
                raise CorpusDomainError(
                    error_code=E_CORPUS_INTEGRITY_VIOLATION,
                    message=f"Không thể chuyển đổi trực tiếp trạng thái sang {status.value} khi phiên đang ở trạng thái '{current_session.status.value}'.",
                    data={"doc_slug": doc_slug, "current_status": current_session.status.value},
                )

        payload = {
            "new_status": status.value,
            "description": description,
        }
        _, session = wal_store.append_record(
            actor=actor,
            op_type=f"STATUS_TRANSITION_{status.value}",
            description=description or f"Transitioned status to {status.value}",
            payload=payload,
        )
        return session

    def delete_session(self, doc_slug: str) -> bool:
        """Deletes a staging session directory from disk."""
        s_dir = self._get_session_dir(doc_slug)
        if s_dir.exists() and s_dir.is_dir():
            for child in s_dir.iterdir():
                child.unlink()
            s_dir.rmdir()
            return True
        return False

    def replay_session(
        self,
        doc_slug: str,
        up_to_lsn: int | None = None,
    ) -> tuple[StagingDocumentSession, int]:
        """Deterministically replays session from genesis to up_to_lsn and returns (session, lsn)."""
        wal_store = self._get_wal_store(doc_slug)
        if not wal_store.exists():
            raise CorpusDomainError(
                error_code=E_CORPUS_INTEGRITY_VIOLATION,
                message=f"Staging session for document '{doc_slug}' does not exist at {wal_store.session_dir}",
                data={"doc_slug": doc_slug},
            )
        return wal_store.replay(up_to_lsn=up_to_lsn)

    def get_wal_records(self, doc_slug: str, since_lsn: int = 0) -> list[WALRecord]:
        """Returns full ordered WAL history for the document."""
        wal_store = self._get_wal_store(doc_slug)
        if not wal_store.exists():
            raise CorpusDomainError(
                error_code=E_CORPUS_INTEGRITY_VIOLATION,
                message=f"Staging session for document '{doc_slug}' does not exist at {wal_store.session_dir}",
                data={"doc_slug": doc_slug},
            )
        return wal_store.read_wal(since_lsn=since_lsn)

    def finalize_chunks(
        self,
        doc_slug: str,
        paths: Sequence[str],
        actor: str = "AGENT",
    ) -> tuple[StagingDocumentSession, int, list[dict[str, object]]]:
        """Atomically locks candidate chunks as FINALIZED via WAL append."""
        wal_store = self._get_wal_store(doc_slug)
        if not wal_store.exists():
            raise CorpusDomainError(
                error_code=E_CORPUS_INTEGRITY_VIOLATION,
                message=f"Staging session for document '{doc_slug}' does not exist at {wal_store.session_dir}",
                data={"doc_slug": doc_slug},
            )
        session = self.load_session(doc_slug)
        if session.status not in (StagingStatus.DRAFT, StagingStatus.AMENDMENT):
            raise CorpusDomainError(
                error_code=E_CORPUS_INTEGRITY_VIOLATION,
                message=f"Không thể chỉnh sửa phiên staging ở trạng thái '{session.status.value}'. Phiên làm việc phải ở trạng thái DRAFT hoặc AMENDMENT.",
                data={"doc_slug": doc_slug, "status": session.status.value},
            )
        clean_paths = [validate_ltree_path(p) for p in paths]
        payload = {
            "paths": clean_paths,
            "inspected_paths": list(session.inspected_paths),
        }
        _, session = wal_store.append_record(
            actor=actor,
            op_type="CHUNKS_FINALIZED",
            description=f"Finalized {len(clean_paths)} chunks.",
            payload=payload,
        )
        results: list[dict[str, object]] = [
            {
                "path": c.path,
                "review_status": c.review_status,
                "finalization_state": c.finalization_state,
                "context_type": c.context_type,
            }
            for c in session.chunks
            if c.path in clean_paths and c.review_status == ChunkReviewStatus.REVIEWED
        ]
        return session, len(results), results

    def unfinalize_chunks(
        self,
        doc_slug: str,
        paths: Sequence[str],
        actor: str = "AGENT",
    ) -> tuple[StagingDocumentSession, int, list[dict[str, object]]]:
        """Atomically reverts chunks to PENDING via WAL append with strict integrity checks."""
        wal_store = self._get_wal_store(doc_slug)
        if not wal_store.exists():
            raise CorpusDomainError(
                error_code=E_CORPUS_INTEGRITY_VIOLATION,
                message=f"Staging session for document '{doc_slug}' does not exist at {wal_store.session_dir}",
                data={"doc_slug": doc_slug},
            )
        session = self.load_session(doc_slug)
        if session.status not in (StagingStatus.DRAFT, StagingStatus.AMENDMENT):
            raise CorpusDomainError(
                error_code=E_CORPUS_INTEGRITY_VIOLATION,
                message=f"Không thể chỉnh sửa phiên staging ở trạng thái '{session.status.value}'. Phiên làm việc phải ở trạng thái DRAFT hoặc AMENDMENT.",
                data={"doc_slug": doc_slug, "status": session.status.value},
            )
        clean_paths = [validate_ltree_path(p) for p in paths]
        payload = {
            "paths": clean_paths,
        }
        _, session = wal_store.append_record(
            actor=actor,
            op_type="CHUNKS_UNFINALIZED",
            description=f"Unfinalized {len(clean_paths)} chunks.",
            payload=payload,
        )
        results: list[dict[str, object]] = [
            {
                "path": c.path,
                "review_status": c.review_status,
                "finalization_state": c.finalization_state,
                "context_type": c.context_type,
            }
            for c in session.chunks
            if c.path in clean_paths and c.review_status == ChunkReviewStatus.PENDING
        ]
        return session, len(results), results

    def poll_pending_chunks(
        self,
        doc_slug: str,
        limit: int = 10,
        path_prefix: str | None = None,
    ) -> tuple[list[StagingChunk], dict[str, object]]:
        """Queries pending chunks and calculates progress statistics."""
        session = self.load_session(doc_slug)
        target_pool = session.chunks
        if path_prefix:
            clean_pre = validate_ltree_path(path_prefix)
            target_pool = [
                c
                for c in session.chunks
                if c.path == clean_pre or c.path.startswith(f"{clean_pre}.")
            ]

        total_chunks = len(target_pool)
        finalized_count = sum(
            1 for c in target_pool if c.review_status != ChunkReviewStatus.PENDING
        )
        pending_chunks = [
            c for c in target_pool if c.review_status == ChunkReviewStatus.PENDING
        ]

        stats = {
            "total_chunks": total_chunks,
            "finalized_count": finalized_count,
            "pending_count": total_chunks - finalized_count,
            "progress_percent": (
                round((finalized_count / total_chunks * 100.0), 1)
                if total_chunks > 0
                else 0.0
            ),
        }
        clamped_limit = max(1, min(limit, 15))
        return pending_chunks[:clamped_limit], stats

    def reopen_session_for_amendment(
        self,
        doc_slug: str,
        actor: str = "AGENT",
        reason: str = "",
    ) -> StagingDocumentSession:
        """Reopens a PROMOTED document session into AMENDMENT status."""
        wal_store = self._get_wal_store(doc_slug)
        if not wal_store.exists():
            raise CorpusDomainError(
                error_code=E_CORPUS_INTEGRITY_VIOLATION,
                message=f"Staging session for document '{doc_slug}' does not exist at {wal_store.session_dir}",
                data={"doc_slug": doc_slug},
            )

        session = wal_store.load_materialized_session()
        if session.status == StagingStatus.AMENDMENT:
            return session
        if session.status != StagingStatus.PROMOTED:
            raise CorpusDomainError(
                error_code=E_CORPUS_INTEGRITY_VIOLATION,
                message=f"Chỉ phiên ở trạng thái PROMOTED mới có thể mở lại để sửa đổi bổ sung (AMENDMENT). Hiện tại: '{session.status.value}'.",
                data={"doc_slug": doc_slug, "status": session.status.value},
            )

        snapshot = [c.model_dump(mode="json") for c in session.chunks]
        edges_snapshot = [e.model_dump(mode="json") for e in session.edges]
        session.metadata["amendment_baseline_snapshot"] = snapshot
        session.metadata["amendment_baseline_edges_snapshot"] = edges_snapshot
        payload = {
            "previous_status": session.status.value,
            "new_status": StagingStatus.AMENDMENT.value,
            "reason": reason or "Opened errata / amendment session",
            "amendment_baseline_snapshot": snapshot,
            "amendment_baseline_edges_snapshot": edges_snapshot,
        }
        _, session = wal_store.append_record(
            actor=actor,
            op_type="STATUS_TRANSITION_AMENDMENT",
            description=reason or f"Reopened session for '{doc_slug}' into AMENDMENT status.",
            payload=payload,
        )
        return session

    def commit_session(
        self,
        doc_slug: str,
        actor: str = "AGENT",
        reason: str = "",
    ) -> StagingDocumentSession:
        """Validates 100% chunk review gate and graph referential integrity, then commits session to AGENT_COMMITTED."""
        wal_store = self._get_wal_store(doc_slug)
        if not wal_store.exists():
            raise CorpusDomainError(
                error_code=E_CORPUS_INTEGRITY_VIOLATION,
                message=f"Staging session for document '{doc_slug}' does not exist at {wal_store.session_dir}",
                data={"doc_slug": doc_slug},
            )

        session = wal_store.load_materialized_session()
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

        return self.update_session_status(
            doc_slug=doc_slug,
            status=StagingStatus.AGENT_COMMITTED,
            actor=actor,
            description=reason or f"Agent completed staging session review and committed for {doc_slug}.",
        )

    def uncommit_session(
        self,
        doc_slug: str,
        actor: str = "AGENT",
        reason: str = "",
    ) -> StagingDocumentSession:
        """Reopens an AGENT_COMMITTED staging session back into DRAFT or AMENDMENT status (Origin-Aware)."""
        wal_store = self._get_wal_store(doc_slug)
        if not wal_store.exists():
            raise CorpusDomainError(
                error_code=E_CORPUS_INTEGRITY_VIOLATION,
                message=f"Staging session for document '{doc_slug}' does not exist at {wal_store.session_dir}",
                data={"doc_slug": doc_slug},
            )

        session = wal_store.load_materialized_session()
        if session.status in (StagingStatus.DRAFT, StagingStatus.AMENDMENT):
            return session
        if session.status != StagingStatus.AGENT_COMMITTED:
            raise CorpusDomainError(
                error_code=E_CORPUS_INTEGRITY_VIOLATION,
                message=f"Chỉ phiên ở trạng thái AGENT_COMMITTED mới có thể mở lại để tiếp tục hiệu chỉnh. Hiện tại: '{session.status.value}'.",
                data={"doc_slug": doc_slug, "status": session.status.value},
            )

        has_amendment = bool(session.metadata.get("amendment_baseline_snapshot"))
        target_status = StagingStatus.AMENDMENT if has_amendment else StagingStatus.DRAFT

        payload = {
            "previous_status": session.status.value,
            "new_status": target_status.value,
            "reason": reason or f"Uncommitted session back to {target_status.value}",
        }
        _, session = wal_store.append_record(
            actor=actor,
            op_type=f"STATUS_TRANSITION_{target_status.value}",
            description=reason or f"Uncommitted session for '{doc_slug}' back to {target_status.value}.",
            payload=payload,
        )
        return session

    async def hydrate_session_from_db(
        self,
        doc_slug: str,
        pool: asyncpg.Pool,
    ) -> StagingDocumentSession:
        """Reconstructs genesis.json, wal.jsonl, and state.json directly from PostgreSQL production tables."""
        from rag_eval.db.repositories import CorpusRepository
        from rag_eval.schemas import FinalizationState

        wal_store = self._get_wal_store(doc_slug)
        if wal_store.exists():
            return wal_store.load_materialized_session()

        corpus_repo = CorpusRepository(pool)
        doc = await corpus_repo.documents.get_by_slug(doc_slug)
        if not doc:
            raise CorpusDomainError(
                error_code=E_CORPUS_INTEGRITY_VIOLATION,
                message=f"Không tìm thấy tài liệu '{doc_slug}' trong cơ sở dữ liệu để hydrate.",
                data={"doc_slug": doc_slug},
            )

        doc_id: uuid.UUID = doc.id
        title: str = doc.title
        metadata: dict[str, object] = dict(doc.metadata or {})
        raw_text: str = doc.raw_text or ""

        chunks = await corpus_repo.chunks.list_by_document(doc_id)
        chunk_ids = [c.id for c in chunks]

        stg_chunks: list[StagingChunk] = []
        chunk_uuid_to_path: dict[uuid.UUID, str] = {}
        for c in chunks:
            chunk_uuid_to_path[c.id] = c.path
            f_state = (
                FinalizationState.FINALIZED_SELF_CONTAINED
                if c.context_type == "SELF_CONTAINED"
                else (
                    FinalizationState.FINALIZED_FULLY_LINKED
                    if c.is_all_refs_resolved
                    else FinalizationState.UNFINALIZED
                )
            )

            stg_chunks.append(
                StagingChunk(
                    path=c.path,
                    verbatim_text=c.verbatim_text,
                    contextualized_text=c.contextualized_text,
                    start_line=c.start_line,
                    end_line=c.end_line,
                    metadata=dict(c.metadata or {}),
                    review_status=ChunkReviewStatus.REVIEWED,
                    finalization_state=f_state,
                    context_type=ContextType(c.context_type) if c.context_type else None,
                )
            )

        if not raw_text:
            raw_text = "\n\n".join(c.verbatim_text for c in stg_chunks)

        edges = await corpus_repo.graph.list_edges_for_chunks(chunk_ids)
        external_target_ids = [
            e.target_chunk_id
            for e in edges
            if e.target_chunk_id not in chunk_uuid_to_path
        ]
        external_target_map: dict[uuid.UUID, str] = {}
        if external_target_ids:
            external_target_map = await corpus_repo.chunks.resolve_ids_batch(external_target_ids)

        stg_edges: list[StagingEdge] = []
        for e in edges:
            src_path = chunk_uuid_to_path.get(e.source_chunk_id)
            tgt_path = chunk_uuid_to_path.get(e.target_chunk_id) or external_target_map.get(e.target_chunk_id)
            if not src_path or not tgt_path:
                continue
            stg_edges.append(
                StagingEdge(
                    source_path=src_path,
                    target_path=tgt_path,
                    relation_type=RelationType(e.relation_type) if e.relation_type in RelationType.__members__ else RelationType.REFERENCES,
                )
            )

        # DEF-INGEST-012: Hydrate unresolved external references from chunk_context_refs
        async with pool.acquire() as conn:
            unresolved_refs = await conn.fetch(
                """
                SELECT c.path AS source_path, cr.target_path
                FROM chunk_context_refs cr
                JOIN chunks c ON c.id = cr.chunk_id
                WHERE cr.chunk_id = ANY($1::uuid[]) AND cr.target_path IS NOT NULL;
                """,
                chunk_ids,
            )
            for r in unresolved_refs:
                stg_edges.append(
                    StagingEdge(
                        source_path=r["source_path"],
                        target_path=r["target_path"],
                        relation_type=RelationType.REFERENCES,
                    )
                )

        genesis = GenesisSnapshot.create(
            doc_slug=doc_slug,
            title=title,
            raw_text=raw_text,
            metadata=metadata | {"hydrated_from_db": True},
            initial_chunks=[c.model_dump(mode="json") for c in stg_chunks],
            initial_edges=[e.model_dump(mode="json") for e in stg_edges],
        )
        _, session = wal_store.init_genesis(genesis)

        _, session = wal_store.append_record(
            actor="SYSTEM:hydrator",
            op_type="PROMOTED_TO_PRODUCTION",
            description=f"Hydrated baseline from production PostgreSQL for {doc_slug}.",
            payload={"doc_id": str(doc_id), "source": "DATABASE_HYDRATION"},
        )
        session.status = StagingStatus.PROMOTED
        return session


def group_pending_chunks(
    chunks: list[StagingChunk],
    session: StagingDocumentSession,
) -> list[PendingChunkGroup]:
    """Groups sibling pending leaf chunks under their immediate ancestor heading.

    Uses non-mutating session.lookup_chunk so that queue polling never marks chunks as inspected.
    """
    groups_map: dict[str, list[PendingChunkLeaf]] = {}
    order: list[str] = []

    for c in chunks:
        if "." in c.path:
            parent_path = c.path.rsplit(".", 1)[0]
        else:
            parent_path = session.doc_slug

        if parent_path not in groups_map:
            groups_map[parent_path] = []
            order.append(parent_path)

        justification_val: str | None = None
        just_attr = getattr(c, "justification", None)
        if isinstance(just_attr, str):
            justification_val = just_attr
        elif isinstance(c.metadata, dict) and "justification" in c.metadata:
            justification_val = str(c.metadata["justification"])

        leaf = PendingChunkLeaf(
            path=c.path,
            verbatim_text=c.verbatim_text,
            start_line=c.start_line,
            end_line=c.end_line,
            context_type=c.context_type,
            justification=justification_val,
        )
        groups_map[parent_path].append(leaf)

    result: list[PendingChunkGroup] = []
    for parent_path in order:
        if parent_path == session.doc_slug:
            parent_context = session.title or session.doc_slug
        else:
            parent_chunk = session.lookup_chunk(parent_path)
            if parent_chunk is not None:
                parent_context = (
                    parent_chunk.contextualized_text
                    or parent_chunk.verbatim_text
                    or parent_path
                )
            else:
                parent_context = parent_path

        result.append(
            PendingChunkGroup(
                parent_path=parent_path,
                parent_context=parent_context,
                chunks=groups_map[parent_path],
            )
        )

    return result

