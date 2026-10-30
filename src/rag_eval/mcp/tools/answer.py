from __future__ import annotations

import json
import logging
import re
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

import asyncpg
from pydantic import BaseModel, ConfigDict, Field

from rag_eval.db.connection import get_db_pool
from rag_eval.db.repositories import CorpusRepository
from rag_eval.exceptions import (
    E_AST_GROUNDING_VALIDATION,
    CorpusDomainError,
)
from rag_eval.schemas import validate_ltree_path
from rag_eval.text import find_normalized_span

logger = logging.getLogger("rag_eval.mcp.tools.answer")

_MARKER_RE = re.compile(r"\[#(\d+)\]")


class CitationInput(BaseModel):
    """Đầu vào trích dẫn cho một chunk trong kho tài liệu."""

    model_config = ConfigDict(extra="forbid")

    path: str = Field(
        ...,
        min_length=1,
        description="Đường dẫn phân cấp LTree của chunk hoặc mục tài liệu được trích dẫn.",
    )
    citation_text: str | None = Field(
        default=None,
        description=(
            "Đoạn trích nguyên văn tùy chọn từ chunk để kiểm chứng bổ sung "
            "(để None khi chỉ cần xác thực theo đường dẫn path)."
        ),
    )


class GroundedCitationDTO(BaseModel):
    """Trích dẫn đã được xác thực và làm giàu siêu dữ liệu từ PostgreSQL."""

    model_config = ConfigDict(extra="forbid")

    index: int = Field(
        ...,
        ge=1,
        description="Số thứ tự trích dẫn 1-based tương ứng với ký hiệu [#index] trong câu trả lời.",
    )
    path: str = Field(
        ...,
        description="Đường dẫn phân cấp LTree đã xác thực trong cơ sở dữ liệu.",
    )
    doc_slug: str = Field(
        ...,
        description="Mã định danh doc_slug của tài liệu chứa chunk.",
    )
    doc_title: str = Field(
        ...,
        description="Tiêu đề tài liệu chứa chunk.",
    )
    start_line: int = Field(
        ...,
        ge=1,
        description="Dòng bắt đầu 1-indexed trong tài liệu gốc.",
    )
    end_line: int = Field(
        ...,
        ge=1,
        description="Dòng kết thúc 1-indexed trong tài liệu gốc.",
    )
    verbatim_text: str = Field(
        ...,
        description="Nội dung nguyên văn của chunk trong cơ sở dữ liệu.",
    )
    contextualized_text: str = Field(
        ...,
        description="Nội dung ngữ cảnh phả hệ đầy đủ của chunk.",
    )
    citation_text: str | None = Field(
        default=None,
        description="Đoạn trích nguyên văn tùy chọn đã kiểm chứng (None khi chỉ xác thực theo path).",
    )


class AnswerValidationViolation(BaseModel):
    """Chi tiết một lỗi vi phạm khi xác thực câu trả lời và trích dẫn."""

    model_config = ConfigDict(extra="forbid")

    violation_code: str = Field(..., description="Mã lỗi vi phạm")
    path: str | None = Field(
        default=None,
        description="Đường dẫn LTree gây lỗi (None nếu lỗi ở cấp câu trả lời chung)",
    )
    message: str = Field(..., description="Thông báo mô tả chi tiết lỗi để sửa")


class ValidatedAnswerPayload(BaseModel):
    """Kết quả đầu ra từ bộ xác thực câu trả lời."""

    model_config = ConfigDict(extra="forbid")

    answer: str
    abstained: bool = False
    citations: list[GroundedCitationDTO] = Field(default_factory=list)


class SubmitGroundedAnswerResult(BaseModel):
    """Kết quả trả về của tool MCP `submit_grounded_answer`."""

    model_config = ConfigDict(extra="forbid")

    accepted: bool = Field(
        default=True,
        description="True khi câu trả lời và toàn bộ trích dẫn đã vượt qua bước xác thực.",
    )
    answer: str = Field(
        ...,
        description="Nội dung câu trả lời đã chuẩn hóa ký hiệu trích dẫn [#1]..[#k].",
    )
    abstained: bool = Field(
        default=False,
        description="True khi kho tài liệu không có thông tin để trả lời câu hỏi.",
    )
    citations: list[GroundedCitationDTO] = Field(
        default_factory=list,
        description="Danh sách các trích dẫn đã xác thực kèm nội dung chunk từ cơ sở dữ liệu.",
    )
    message: str = Field(
        ...,
        description="Thông báo xác nhận kết quả xử lý.",
    )


CustomAnswerRule = Callable[
    [str, list[CitationInput], bool],
    list[AnswerValidationViolation],
]


@runtime_checkable
class AnswerValidator(Protocol):
    """Giao diện tách rời (decoupled interface) cho bộ kiểm tra câu trả lời có căn cứ.

    Mọi chiến lược kiểm tra tùy chỉnh (chỉ kiểm tra path, kiểm tra trích dẫn nguyên văn,
    kiểm tra độ phủ ký hiệu [#i], v.v.) đều cài đặt giao diện này mà không cần sửa đổi
    MCP server hay luồng hỏi đáp.
    """

    async def validate_and_enrich(
        self,
        repo: CorpusRepository,
        answer: str,
        citations: list[CitationInput],
        abstained: bool = False,
    ) -> ValidatedAnswerPayload: ...


@dataclass(frozen=True)
class _ChunkDocRow:
    path: str
    verbatim_text: str
    contextualized_text: str
    start_line: int
    end_line: int
    doc_slug: str
    doc_title: str


def normalize_citation_inputs(
    raw_citations: Sequence[CitationInput | str | dict[str, object]] | None,
) -> list[CitationInput]:
    """Chuẩn hóa danh sách trích dẫn đầu vào (hỗ trợ cả chuỗi path hoặc object CitationInput)."""
    if not raw_citations:
        return []
    normalized: list[CitationInput] = []
    for item in raw_citations:
        if isinstance(item, CitationInput):
            normalized.append(item)
        elif isinstance(item, str):
            clean = item.strip()
            if clean:
                normalized.append(CitationInput(path=clean))
        elif isinstance(item, dict):
            raw_path = str(item.get("path") or "").strip()
            raw_quote = item.get("citation_text")
            quote_str = str(raw_quote).strip() if isinstance(raw_quote, str) and raw_quote.strip() else None
            if raw_path:
                normalized.append(CitationInput(path=raw_path, citation_text=quote_str))
    return normalized


class DefaultPathAnswerValidator:
    """Bộ xác thực mặc định dựa trên đường dẫn LTree `path` trong PostgreSQL.

    - Kiểm tra `answer` không rỗng.
    - Khi `abstained=False`, bắt buộc có ít nhất 1 `path` trích dẫn hợp lệ.
    - Xác thực từng `path` tồn tại trong bảng `chunks` (hỗ trợ mở rộng nút cha sang chunk lá).
    - Nếu người gọi truyền kèm `citation_text` (hoặc cấu hình `require_citation_text=True`),
      đối chiếu thêm đoạn trích nguyên văn bằng `find_normalized_span`.
    - Cho phép gắn thêm các hàm kiểm tra tùy chỉnh qua `extra_rules`.
    """

    def __init__(
        self,
        *,
        require_citation_text: bool = False,
        extra_rules: list[CustomAnswerRule] | None = None,
    ) -> None:
        self.require_citation_text = require_citation_text
        self.extra_rules: list[CustomAnswerRule] = list(extra_rules or [])

    async def validate_and_enrich(
        self,
        repo: CorpusRepository,
        answer: str,
        citations: list[CitationInput],
        abstained: bool = False,
    ) -> ValidatedAnswerPayload:
        clean_answer = answer.strip()
        violations: list[AnswerValidationViolation] = []

        if not clean_answer:
            violations.append(
                AnswerValidationViolation(
                    violation_code="EMPTY_ANSWER",
                    path=None,
                    message="Nội dung `answer` không được để trống.",
                )
            )

        if abstained:
            for rule in self.extra_rules:
                violations.extend(rule(clean_answer, citations, abstained))
            if violations:
                self._raise_violations(violations)
            return ValidatedAnswerPayload(
                answer=clean_answer,
                abstained=True,
                citations=[],
            )

        if not citations:
            violations.append(
                AnswerValidationViolation(
                    violation_code="MISSING_CITATIONS",
                    path=None,
                    message=(
                        "Khi `abstained=False`, bắt buộc cung cấp ít nhất một đường dẫn `path` "
                        "trong `citations` để chứng thực câu trả lời."
                    ),
                )
            )

        valid_syntax_inputs: list[CitationInput] = []
        for c in citations:
            try:
                clean_path = validate_ltree_path(c.path)
                valid_syntax_inputs.append(
                    CitationInput(
                        path=clean_path,
                        citation_text=c.citation_text.strip() if c.citation_text else None,
                    )
                )
            except ValueError as exc:
                violations.append(
                    AnswerValidationViolation(
                        violation_code="INVALID_LTREE_PATH",
                        path=c.path,
                        message=str(exc),
                    )
                )

        for match in _MARKER_RE.finditer(clean_answer):
            marker_idx = int(match.group(1))
            if marker_idx < 1 or marker_idx > len(valid_syntax_inputs):
                violations.append(
                    AnswerValidationViolation(
                        violation_code="DANGLING_CITATION_MARKER",
                        path=None,
                        message=(
                            f"Ký hiệu trích dẫn '[#{marker_idx}]' trong câu trả lời nằm ngoài phạm vi "
                            f"danh sách `citations` (hiện có {len(valid_syntax_inputs)} mục)."
                        ),
                    )
                )

        for rule in self.extra_rules:
            violations.extend(rule(clean_answer, valid_syntax_inputs, abstained))

        if violations:
            self._raise_violations(violations)

        unique_query_paths = list(dict.fromkeys(c.path for c in valid_syntax_inputs))
        expanded_map = await repo.chunks.expand_to_leaf_paths(unique_query_paths)

        resolved_chunk_ids: list[uuid.UUID] = []
        for q_path in unique_query_paths:
            leaves = expanded_map.get(q_path, [])
            if not leaves:
                violations.append(
                    AnswerValidationViolation(
                        violation_code="PATH_NOT_FOUND",
                        path=q_path,
                        message=f"Đường dẫn '{q_path}' không tồn tại trong kho tài liệu.",
                    )
                )
            else:
                for _, cid in leaves:
                    resolved_chunk_ids.append(cid)

        if violations:
            self._raise_violations(violations)

        chunk_details = await self._fetch_chunks_with_documents(repo, resolved_chunk_ids)

        grounded_list: list[GroundedCitationDTO] = []
        seen_paths: dict[str, int] = {}
        old_to_new_index: dict[int, int] = {}

        for raw_idx, item in enumerate(valid_syntax_inputs, start=1):
            leaves = expanded_map.get(item.path, [])
            selected_row: _ChunkDocRow | None = None
            if item.citation_text:
                for _, cid in leaves:
                    candidate = chunk_details.get(cid)
                    if candidate and find_normalized_span(candidate.verbatim_text, item.citation_text) is not None:
                        selected_row = candidate
                        break
                if selected_row is None:
                    violations.append(
                        AnswerValidationViolation(
                            violation_code="UNGROUNDED_CITATION_TEXT",
                            path=item.path,
                            message=(
                                f"Đoạn trích `citation_text` không khớp nguyên văn trong chunk '{item.path}'."
                            ),
                        )
                    )
                    continue
            elif self.require_citation_text:
                violations.append(
                    AnswerValidationViolation(
                        violation_code="MISSING_CITATION_TEXT",
                        path=item.path,
                        message=f"Bắt buộc cung cấp `citation_text` nguyên văn cho đường dẫn '{item.path}'.",
                    )
                )
                continue
            else:
                first_cid = leaves[0][1]
                selected_row = chunk_details.get(first_cid)

            if selected_row is None:
                violations.append(
                    AnswerValidationViolation(
                        violation_code="PATH_NOT_FOUND",
                        path=item.path,
                        message=f"Không thể tải dữ liệu chunk cho đường dẫn '{item.path}'.",
                    )
                )
                continue

            resolved_path = selected_row.path
            if resolved_path in seen_paths:
                old_to_new_index[raw_idx] = seen_paths[resolved_path]
                continue

            new_idx = len(grounded_list) + 1
            seen_paths[resolved_path] = new_idx
            old_to_new_index[raw_idx] = new_idx

            grounded_list.append(
                GroundedCitationDTO(
                    index=new_idx,
                    path=resolved_path,
                    doc_slug=selected_row.doc_slug,
                    doc_title=selected_row.doc_title,
                    start_line=selected_row.start_line,
                    end_line=selected_row.end_line,
                    verbatim_text=selected_row.verbatim_text,
                    contextualized_text=selected_row.contextualized_text,
                    citation_text=item.citation_text,
                )
            )

        if violations:
            self._raise_violations(violations)

        normalized_answer = _normalize_answer_markers(
            clean_answer,
            old_to_new_index=old_to_new_index,
            total_citations=len(grounded_list),
        )

        return ValidatedAnswerPayload(
            answer=normalized_answer,
            abstained=False,
            citations=grounded_list,
        )

    @staticmethod
    async def _fetch_chunks_with_documents(
        repo: CorpusRepository,
        chunk_ids: list[uuid.UUID],
    ) -> dict[uuid.UUID, _ChunkDocRow]:
        if not chunk_ids:
            return {}
        query = """
        SELECT
            c.id,
            c.path::text AS path,
            c.verbatim_text,
            c.contextualized_text,
            c.start_line,
            c.end_line,
            d.doc_slug,
            d.title AS doc_title
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE c.id = ANY($1::uuid[]);
        """
        async with repo.chunks._connection_scope() as conn:
            rows = await conn.fetch(query, list(dict.fromkeys(chunk_ids)))
        result: dict[uuid.UUID, _ChunkDocRow] = {}
        for r in rows:
            cid = uuid.UUID(str(r["id"]))
            result[cid] = _ChunkDocRow(
                path=str(r["path"]),
                verbatim_text=str(r["verbatim_text"]),
                contextualized_text=str(r["contextualized_text"]),
                start_line=int(r["start_line"]),
                end_line=int(r["end_line"]),
                doc_slug=str(r["doc_slug"]),
                doc_title=str(r["doc_title"]),
            )
        return result

    @staticmethod
    def _raise_violations(violations: list[AnswerValidationViolation]) -> None:
        summary = "; ".join(
            f"[{v.violation_code}] ({v.path or 'answer'}): {v.message}" for v in violations
        )
        raise CorpusDomainError(
            error_code=E_AST_GROUNDING_VALIDATION,
            message=f"Xác thực câu trả lời thất bại ({len(violations)} lỗi): {summary}",
            data={
                "violation_code": violations[0].violation_code,
                "violations": [v.model_dump() for v in violations],
            },
        )


def _normalize_answer_markers(
    answer: str,
    *,
    old_to_new_index: dict[int, int],
    total_citations: int,
) -> str:
    """Đồng bộ ký hiệu [#i] trong câu trả lời với danh sách trích dẫn 1..total_citations."""
    if total_citations == 0:
        return _MARKER_RE.sub("", answer).strip()

    has_markers = bool(_MARKER_RE.search(answer))
    if has_markers:
        def _replace(match: re.Match[str]) -> str:
            old_idx = int(match.group(1))
            mapped = old_to_new_index.get(old_idx)
            if mapped is not None:
                return f"[#{mapped}]"
            if 1 <= old_idx <= total_citations:
                return f"[#{old_idx}]"
            return ""

        rewritten = _MARKER_RE.sub(_replace, answer).strip()
        if _MARKER_RE.search(rewritten):
            return rewritten

    markers = " ".join(f"[#{i}]" for i in range(1, total_citations + 1))
    return f"{answer} {markers}".strip()


class CorpusAnswerTools:
    """Facade thực thi tool `submit_grounded_answer` với bộ xác thực `AnswerValidator` tách rời."""

    def __init__(
        self,
        validator: AnswerValidator | None = None,
        pool: asyncpg.Pool | None = None,
        answer_output_path: str | Path | None = None,
    ) -> None:
        self._validator: AnswerValidator = (
            validator if validator is not None else DefaultPathAnswerValidator()
        )
        self._pool = pool
        self._answer_output_path = Path(answer_output_path) if answer_output_path else None

    @property
    def validator(self) -> AnswerValidator:
        return self._validator

    @validator.setter
    def validator(self, new_validator: AnswerValidator) -> None:
        self._validator = new_validator

    @property
    def answer_output_path(self) -> Path | None:
        return self._answer_output_path

    @answer_output_path.setter
    def answer_output_path(self, path: str | Path | None) -> None:
        self._answer_output_path = Path(path) if path else None

    async def _get_repo(self) -> CorpusRepository:
        import asyncio

        current_loop = asyncio.get_running_loop()
        pool_loop = getattr(self._pool, "_loop", None) if self._pool is not None else None
        if (
            self._pool is None
            or self._pool._closed
            or pool_loop is not current_loop
        ):
            self._pool = await get_db_pool()
        return CorpusRepository(self._pool)

    async def submit_grounded_answer(
        self,
        answer: str,
        citations: list[CitationInput | str] | None = None,
        abstained: bool = False,
    ) -> SubmitGroundedAnswerResult:
        """Xác thực câu trả lời kèm danh sách `path` trích dẫn và phát hành kết quả."""
        repo = await self._get_repo()
        normalized_inputs = normalize_citation_inputs(citations)
        validated = await self._validator.validate_and_enrich(
            repo=repo,
            answer=answer,
            citations=normalized_inputs,
            abstained=abstained,
        )
        result = SubmitGroundedAnswerResult(
            accepted=True,
            answer=validated.answer,
            abstained=validated.abstained,
            citations=validated.citations,
            message=(
                "Đã xác nhận câu trả lời từ chối (abstained)."
                if validated.abstained
                else f"Đã xác thực thành công câu trả lời với {len(validated.citations)} trích dẫn."
            ),
        )
        if self._answer_output_path is not None:
            try:
                self._answer_output_path.parent.mkdir(parents=True, exist_ok=True)
                self._answer_output_path.write_text(
                    json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            except OSError as exc:
                logger.warning("Không thể ghi file answer_output_path %s: %s", self._answer_output_path, exc)
        return result
