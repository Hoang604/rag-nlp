from __future__ import annotations

import datetime
import json
import re
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from rag_eval.exceptions import (
    E_AST_GROUNDING_VALIDATION,
    E_CORPUS_INTEGRITY_VIOLATION,
    CorpusDomainError,
)
from rag_eval.ingestion.staging.models import (
    RawTextWindow,
    StagingChunk,
    StagingChunkDelta,
    StagingDeltaReport,
    StagingEdge,
    StagingEdgeInput,
    StagingGrepHit,
    StagingMutationRecord,
    StagingStatus,
    StgReparentResult,
)
from rag_eval.ingestion.staging.operations import (
    apply_chunk_deltas_to_session,
    finalize_chunks_in_session,
    reparent_subtree_in_session,
    validate_and_attach_edges_to_session,
)


class StagingDocumentSession(BaseModel):
    """Represents an in-memory staging document session."""

    model_config = ConfigDict(extra="ignore")

    doc_slug: str = Field(..., description="Document slug identifier")
    title: str = Field(..., description="Document title")
    status: StagingStatus = Field(default=StagingStatus.DRAFT, description="Current staging status")
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC),
        description="Session creation timestamp",
    )
    updated_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC),
        description="Session last update timestamp",
    )
    committed_at: datetime.datetime | None = Field(None, description="Session commit timestamp")
    promoted_at: datetime.datetime | None = Field(None, description="Session promotion timestamp")
    raw_text: str | None = Field(default=None, description="Raw document source text")
    metadata: dict[str, object] = Field(default_factory=dict, description="Document metadata")

    @property
    def doc_metadata(self) -> dict[str, object]:
        """Backward-compatibility alias for metadata."""
        return self.metadata

    @doc_metadata.setter
    def doc_metadata(self, val: dict[str, object]) -> None:
        self.metadata = val
    chunks: list[StagingChunk] = Field(default_factory=list, description="List of staged chunks")
    edges: list[StagingEdge] = Field(default_factory=list, description="List of staged graph edges")
    raw_ast_snapshot: list[dict[str, object]] | None = Field(
        default=None, description="Initial AST baseline snapshot for version diffing"
    )
    raw_edge_snapshot: list[dict[str, object]] | None = Field(
        default=None, description="Initial graph edges baseline snapshot for version diffing"
    )
    mutation_history: list[StagingMutationRecord] = Field(
        default_factory=list, description="Audit trail of mutations"
    )
    inspected_paths: set[str] = Field(
        default_factory=set,
        description="Set of chunk dot-separated ltree paths that have been inspected via get_chunk or get_raw_window",
    )

    def is_chunk_inspected(self, path: str) -> bool:
        """Returns True if the specified chunk path was inspected during this session."""
        return path.strip() in self.inspected_paths

    def get_chunk(self, path: str) -> StagingChunk | None:
        """Looks up a single staged chunk by dot-separated ltree path."""
        clean_path = path.strip()
        for chunk in self.chunks:
            if chunk.path == clean_path:
                self.inspected_paths.add(chunk.path)
                return chunk
        return None

    def get_raw_window(self, start_line: int = 1, end_line: int = 100) -> RawTextWindow:
        """Extracts a 1-indexed bounded slice of lines from session raw_text."""
        if not self.raw_text or not self.raw_text.strip():
            raise CorpusDomainError(
                error_code=E_CORPUS_INTEGRITY_VIOLATION,
                message=f"Nội dung gốc (raw_text) cho '{self.doc_slug}' chưa được lưu hoặc đang rỗng.",
                data={"doc_slug": self.doc_slug},
            )

        lines: list[str] = []
        cur_line = 1
        total_lines = 0
        start_idx = 0
        text_len = len(self.raw_text)

        while start_idx < text_len:
            next_newline = self.raw_text.find("\n", start_idx)
            if next_newline == -1:
                line = self.raw_text[start_idx:]
                start_idx = text_len
            else:
                line = self.raw_text[start_idx:next_newline]
                line = line.removesuffix("\r")
                start_idx = next_newline + 1

            total_lines += 1
            if start_line <= cur_line <= end_line:
                lines.append(line)
            cur_line += 1

        if total_lines == 0:
            raise CorpusDomainError(
                error_code=E_CORPUS_INTEGRITY_VIOLATION,
                message=f"Nội dung gốc (raw_text) cho '{self.doc_slug}' không chứa dòng nào.",
                data={"doc_slug": self.doc_slug},
            )

        clamped_start = max(1, min(start_line, total_lines))
        clamped_end = max(clamped_start, min(end_line, total_lines))
        content = "\n".join(lines)

        for c in self.chunks:
            if max(c.start_line, clamped_start) <= min(c.end_line, clamped_end):
                self.inspected_paths.add(c.path)

        return RawTextWindow(
            doc_slug=self.doc_slug,
            start_line=clamped_start,
            end_line=clamped_end,
            total_lines=total_lines,
            lines=lines,
            content=content,
        )

    def grep(
        self,
        pattern: str,
        is_regex: bool = False,
        case_sensitive: bool = False,
        search_in: str = "ALL",
        limit: int = 50,
    ) -> list[StagingGrepHit]:
        """Searches in-memory chunks in the session using substring or regex matching."""
        if not pattern or not pattern.strip():
            return []

        clean_pattern = pattern.strip()
        search_mode = search_in.upper()
        flags = 0 if case_sensitive else re.IGNORECASE
        compiled_regex: re.Pattern[str] | None = None

        if is_regex:
            try:
                compiled_regex = re.compile(clean_pattern, flags)
            except re.error as exc:
                raise CorpusDomainError(
                    error_code=E_AST_GROUNDING_VALIDATION,
                    message=f"Biểu thức chính quy không hợp lệ '{pattern}': {exc}",
                    data={"pattern": pattern, "is_regex": is_regex},
                ) from exc

        hits: list[StagingGrepHit] = []

        def _check_match(text: str) -> tuple[bool, str]:
            if not text:
                return False, ""
            if compiled_regex is not None:
                m = compiled_regex.search(text)
                if m:
                    s_start = max(0, m.start() - 30)
                    s_end = min(len(text), m.end() + 30)
                    snippet = text[s_start:s_end].replace("\n", " ").strip()
                    return True, snippet
                return False, ""
            else:
                target_str = text if case_sensitive else text.lower()
                query_str = clean_pattern if case_sensitive else clean_pattern.lower()
                idx = target_str.find(query_str)
                if idx >= 0:
                    s_start = max(0, idx - 30)
                    s_end = min(len(text), idx + len(clean_pattern) + 30)
                    snippet = text[s_start:s_end].replace("\n", " ").strip()
                    return True, snippet
                return False, ""

        for chunk in self.chunks:
            if len(hits) >= limit:
                break

            matched_field: str | None = None
            snippet: str = ""

            if search_mode in ("ALL", "PATH"):
                matched, snip = _check_match(chunk.path)
                if matched:
                    matched_field = "PATH"
                    snippet = f"Path: {chunk.path}"

            if not matched_field and search_mode in ("ALL", "VERBATIM"):
                matched, snip = _check_match(chunk.verbatim_text)
                if matched:
                    matched_field = "VERBATIM"
                    snippet = snip

            if not matched_field and search_mode in ("ALL", "CONTEXT"):
                matched, snip = _check_match(chunk.contextualized_text)
                if matched:
                    matched_field = "CONTEXT"
                    snippet = snip

            if not matched_field and search_mode in ("ALL", "METADATA"):
                meta_str = json.dumps(chunk.metadata, ensure_ascii=False)
                matched, snip = _check_match(meta_str)
                if matched:
                    matched_field = "METADATA"
                    snippet = snip

            if matched_field:
                hits.append(
                    StagingGrepHit(
                        path=chunk.path,
                        field_matched=matched_field,
                        match_snippet=snippet,
                        verbatim_text=chunk.verbatim_text,
                        contextualized_text=chunk.contextualized_text,
                        char_length=chunk.char_length or len(chunk.verbatim_text),
                        metadata=chunk.metadata,
                    )
                )

        return hits

    def apply_chunk_deltas(
        self,
        deltas: Sequence[StagingChunkDelta],
        removed_paths: list[str] | None = None,
        cascade_breadcrumbs: bool = True,
        actor: str = "AGENT",
        applied_at: datetime.datetime | None = None,
    ) -> StagingDeltaReport:
        return apply_chunk_deltas_to_session(
            session=self,
            deltas=deltas,
            removed_paths=removed_paths,
            cascade_breadcrumbs=cascade_breadcrumbs,
            actor=actor,
            applied_at=applied_at,
        )

    def validate_and_attach_edges(
        self,
        edges: Sequence[StagingEdge | StagingEdgeInput | dict[str, object]],
        actor: str = "AGENT",
        applied_at: datetime.datetime | None = None,
    ) -> tuple[int, list[StagingEdge]]:
        return validate_and_attach_edges_to_session(
            session=self,
            edges=edges,
            actor=actor,
            applied_at=applied_at,
        )

    def reparent_subtree(
        self,
        old_path_prefix: str,
        new_path_prefix: str,
        dry_run: bool = False,
        actor: str = "AGENT",
        applied_at: datetime.datetime | None = None,
    ) -> StgReparentResult:
        return reparent_subtree_in_session(
            session=self,
            old_path_prefix=old_path_prefix,
            new_path_prefix=new_path_prefix,
            dry_run=dry_run,
            actor=actor,
            applied_at=applied_at,
        )

    def finalize_chunks(
        self,
        paths: Sequence[str],
        actor: str = "AGENT",
        applied_at: datetime.datetime | None = None,
    ) -> tuple[int, list[dict[str, object]]]:
        return finalize_chunks_in_session(
            session=self,
            paths=paths,
            actor=actor,
            applied_at=applied_at,
        )
