from __future__ import annotations

import datetime
import uuid
from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rag_eval.legal.schemas import (
    FinalizationState,
    validate_ltree_path,
)


def _resolve_default_staging_dir() -> Path:
    """Resolves absolute staging directory anchored to repository root or STAGING_DIR env var."""
    import os

    env_dir = os.environ.get("STAGING_DIR")
    if env_dir:
        return Path(env_dir).resolve()
    curr = Path(__file__).resolve().parent
    for parent in [curr, *curr.parents]:
        if (parent / "pyproject.toml").exists() and (parent / "src" / "rag_eval").exists():
            return (parent / ".cache" / "stg").resolve()
    return (Path.cwd() / ".cache" / "stg").resolve()


DEFAULT_STAGING_DIR = _resolve_default_staging_dir()


def deep_merge_dict(base: dict[str, object], delta: dict[str, object]) -> dict[str, object]:
    """Recursively merges delta dictionary into base dictionary without clobbering sibling keys."""
    merged = dict(base)
    for key, value in delta.items():
        base_val = merged.get(key)
        if isinstance(base_val, dict) and isinstance(value, dict):
            merged[key] = deep_merge_dict(base_val, value)
        else:
            merged[key] = value
    return merged


class ChunkReviewStatus(str, Enum):
    """Review lifecycle status for an individual chunk within staging."""

    PENDING = "PENDING"
    REVIEWED = "REVIEWED"


class StagingStatus(str, Enum):
    """Lifecycle statuses for staging sessions."""

    DRAFT = "DRAFT"
    AGENT_COMMITTED = "AGENT_COMMITTED"
    APPROVED = "APPROVED"
    PROMOTED = "PROMOTED"
    AMENDMENT = "AMENDMENT"


class RelationType(str, Enum):
    """Canonical relation types between chunks in the knowledge graph."""

    REFERENCES = "REFERENCES"
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    DEFINES = "DEFINES"
    EXTENDS = "EXTENDS"
    EXEMPLIFIES = "EXEMPLIFIES"
    DEPENDS_ON = "DEPENDS_ON"
    SUPERSEDES = "SUPERSEDES"
    SEE_ALSO = "SEE_ALSO"


class StagingChunkDelta(BaseModel):
    """Dữ liệu cập nhật từng phần cho một chunk trong vùng đệm staging."""

    model_config = ConfigDict(extra="ignore")

    path: str = Field(
        ...,
        description="Đường dẫn phân cấp của chunk cần chỉnh sửa hoặc tạo mới.",
    )
    verbatim_text: str | None = Field(
        None,
        description="Nội dung văn bản nguyên văn mới của chunk.",
    )
    contextualized_text: str | None = Field(
        None,
        description="Nội dung ngữ cảnh đầy đủ mới sau khi ghép chuỗi phả hệ.",
    )
    lead_sentence: str | None = Field(
        None,
        description="Câu dẫn đề mới của phân vị cha.",
    )
    start_line: int | None = Field(
        None,
        ge=1,
        description="Số dòng bắt đầu trong văn bản nguồn tính từ 1.",
    )
    end_line: int | None = Field(
        None,
        ge=1,
        description="Số dòng kết thúc trong văn bản nguồn tính từ 1.",
    )
    metadata: dict[str, object] | None = Field(
        None,
        description="Siêu dữ liệu ngữ nghĩa cần cập nhật bổ sung vào chunk.",
    )
    review_status: ChunkReviewStatus | None = Field(
        None,
        description="Trạng thái tiến độ rà soát của Agent đối với chunk: PENDING hoặc REVIEWED.",
    )
    finalization_state: FinalizationState | None = Field(
        None,
        description="Trạng thái hoàn thiện của chunk trong quy trình staging và review.",
    )


class StagingDeltaReport(BaseModel):
    """Summary of applied chunk mutations and cascaded hierarchical updates."""

    model_config = ConfigDict(extra="ignore")

    doc_slug: str = Field(..., description="Document slug identifier")
    updated_count: int = Field(..., description="Count of directly patched chunks")
    cascaded_count: int = Field(..., description="Count of descendant chunks whose breadcrumbs were updated")
    removed_count: int = Field(..., description="Count of removed chunk paths")
    total_chunks: int = Field(..., description="Total chunks remaining in session")
    fields_modified: list[str] = Field(
        default_factory=list, description="Unique field names modified across all deltas"
    )


class ReparentPathMapping(BaseModel):
    """Pairwise mapping from old ltree path to new ltree path."""

    old_path: str = Field(..., description="Original ltree path before migration")
    new_path: str = Field(..., description="Transformed ltree path after migration")


class StgReparentResult(BaseModel):
    """Result returned by subtree re-parenting operation."""

    model_config = ConfigDict(extra="ignore")

    doc_slug: str = Field(..., description="Document slug identifier")
    status: str = Field("SUCCESS", description="Operation status")
    dry_run: bool = Field(False, description="Whether mutation was simulated")
    affected_chunks_count: int = Field(..., description="Total count of chunks whose path was migrated")
    affected_edges_count: int = Field(..., description="Total count of internal edges migrated")
    old_path_prefix: str = Field(..., description="Old prefix searched")
    new_path_prefix: str = Field(..., description="New target prefix")
    sample_mappings: list[ReparentPathMapping] = Field(
        default_factory=list, description="Sample of path mappings (up to 10)"
    )


class StagingMutationRecord(BaseModel):
    """Immutable audit trail entry for staging session transformations."""

    model_config = ConfigDict(extra="ignore")

    id: uuid.UUID = Field(default_factory=uuid.uuid4, description="Unique mutation record ID")
    timestamp: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC),
        description="UTC timestamp of mutation",
    )
    actor: str = Field(..., description="'SYSTEM' | 'AGENT' | 'HUMAN:<username>'")
    action_type: str = Field(..., description="Action type code")
    description: str = Field(..., description="Human-readable summary of mutation")
    diff_payload: dict[str, object] | None = Field(default=None, description="Detailed mutation payload")


class StagingSessionSummary(BaseModel):
    """Lightweight summary model for dashboard listing."""

    model_config = ConfigDict(extra="ignore")

    doc_slug: str = Field(..., description="Document slug identifier")
    title: str = Field(..., description="Document title")
    status: StagingStatus = Field(..., description="Current staging status")
    total_chunks: int = Field(..., description="Total count of staged chunks")
    total_edges: int = Field(..., description="Total count of staged edges")
    valid_from: datetime.date | None = Field(None, description="Valid from date")
    valid_to: datetime.date | None = Field(None, description="Valid to date")
    created_at: datetime.datetime = Field(..., description="Session creation timestamp")
    updated_at: datetime.datetime = Field(..., description="Session last updated timestamp")
    committed_at: datetime.datetime | None = Field(None, description="Session commit timestamp")
    promoted_at: datetime.datetime | None = Field(None, description="Session promotion timestamp")


class RawTextWindow(BaseModel):
    """Encapsulates a bounded line-window of original document source text."""

    model_config = ConfigDict(extra="ignore")

    doc_slug: str = Field(..., description="Document slug identifier")
    start_line: int = Field(..., ge=1, description="1-indexed starting line number")
    end_line: int = Field(..., ge=1, description="1-indexed ending line number")
    total_lines: int = Field(..., ge=0, description="Total line count of source raw text")
    lines: list[str] = Field(default_factory=list, description="Array of sliced raw lines")
    content: str = Field(..., description="Newline-concatenated text of the window slice")


class StagingGrepHit(BaseModel):
    """Represents a matched chunk hit from in-memory staging session grep."""

    model_config = ConfigDict(extra="ignore")

    path: str = Field(..., description="Hierarchical dot-separated ltree path")
    field_matched: str = Field(..., description="'VERBATIM' | 'CONTEXT' | 'PATH' | 'METADATA'")
    match_snippet: str = Field(..., description="Concise snippet highlighting the matched term")
    verbatim_text: str = Field(..., description="Complete verbatim text of the chunk")
    contextualized_text: str = Field(..., description="Full context text")
    char_length: int = Field(..., description="Character count of verbatim text")
    metadata: dict[str, object] = Field(default_factory=dict, description="Chunk metadata payload")


class StagingChunk(BaseModel):
    """Represents a candidate chunk within a staging session."""

    model_config = ConfigDict(extra="ignore")

    path: str = Field(..., description="Hierarchical dot-separated ltree path")
    verbatim_text: str = Field(..., description="Verbatim chunk text")
    contextualized_text: str = Field(..., description="Synthesized context text")
    start_line: int = Field(default=1, ge=1, description="1-indexed starting line number in source text")
    end_line: int = Field(default=1, ge=1, description="1-indexed ending line number in source text")
    lead_sentence: str = Field("", description="Inherited lead sentence")
    metadata: dict[str, object] = Field(default_factory=dict, description="Dynamic metadata payload")
    char_length: int = Field(default=0, description="Total character count of verbatim text")
    review_status: ChunkReviewStatus = Field(
        default=ChunkReviewStatus.PENDING,
        description="Chunk review lifecycle status ('PENDING' | 'REVIEWED')",
    )
    finalization_state: FinalizationState = Field(
        default=FinalizationState.UNFINALIZED,
        description="Semantic finalization state ('FINALIZED_*' | 'UNFINALIZED')",
    )

    @model_validator(mode="after")
    def compute_char_length(self) -> StagingChunk:
        if not self.char_length and self.verbatim_text:
            self.char_length = len(self.verbatim_text)
        return self


class StagingEdgeFilter(BaseModel):
    """Bộ lọc xác định các cạnh quan hệ đồ thị cần xóa trong vùng đệm staging."""

    model_config = ConfigDict(extra="ignore")

    source_path: str = Field(
        ...,
        description="Đường dẫn ltree của đoạn văn bản nguồn, ví dụ: 'doc_slug.sec_1.art_2.p_a'.",
    )
    target_path: str | None = Field(
        None,
        description="Đường dẫn ltree của chunk đích nội bộ cần xóa (nếu có).",
    )
    target_external_ref: str | None = Field(
        None,
        description="Chuỗi trích dẫn nguyên văn đầy đủ của văn bản bên ngoài cần xóa (nếu có).",
    )
    relation_type: RelationType | str | None = Field(
        None,
        description="Loại quan hệ cần xóa (ví dụ: 'REFERENCES', 'SUPPORTS'). Nếu để trống, sẽ khớp mọi loại quan hệ với đích đã chỉ định.",
    )
    clear_all_targets: bool = Field(
        default=False,
        description="Cờ xác nhận xóa toàn bộ các cạnh xuất phát từ source_path bất kể đích đến. Mặc định là False để phòng tránh xóa nhầm dữ liệu đồ thị.",
    )

    @model_validator(mode="after")
    def validate_target_safety(self) -> StagingEdgeFilter:

        clean_src = self.source_path.strip() if self.source_path else ""
        if not clean_src:
            raise ValueError("source_path không được để trống")
        self.source_path = validate_ltree_path(clean_src)

        clean_tgt = self.target_path.strip() if self.target_path else None
        clean_ext = self.target_external_ref.strip() if self.target_external_ref else None

        if not clean_tgt and not clean_ext and not self.clear_all_targets:
            raise ValueError(
                f"Thao tác xóa cạnh từ '{self.source_path}' yêu cầu phải chỉ định 'target_path' hoặc 'target_external_ref' "
                "để xác định đúng cạnh cần xóa. Nếu thực sự muốn xóa toàn bộ mọi cạnh xuất phát từ nút này, "
                "bắt buộc phải đặt 'clear_all_targets=True'."
            )

        if clean_tgt:
            self.target_path = validate_ltree_path(clean_tgt)
        else:
            self.target_path = None
        self.target_external_ref = clean_ext
        return self


class StagingEdge(BaseModel):
    """Represents a candidate directed relation edge within a staging session."""

    model_config = ConfigDict(extra="ignore")

    source_path: str = Field(
        ...,
        description="Đường dẫn phân cấp ltree của chunk nguồn phát sinh quan hệ.",
    )
    target_path: str | None = Field(
        None,
        description="Đường dẫn phân cấp ltree của chunk đích trong cùng văn bản hoặc văn bản đã nạp.",
    )
    target_external_ref: str | None = Field(
        None,
        description="Chuỗi viện dẫn nguyên văn đầy đủ tới tài liệu bên ngoài chưa nạp vào CSDL (ví dụ: 'Document Title, Section 5'). Tuyệt đối không tự bịa đặt mã ltree giả khi tài liệu chưa được nạp.",
    )
    relation_type: RelationType = Field(
        default=RelationType.REFERENCES,
        description="Loại quan hệ có hướng giữa hai chunk.",
    )
    citation_text: str | None = Field(
        None,
        description="Đoạn văn bản nguyên văn trích dẫn làm căn cứ xác lập quan hệ (ví dụ: 'theo quy định tại Phần 5').",
    )
    metadata: dict[str, object] = Field(
        default_factory=dict,
        description="Siêu dữ liệu ngữ nghĩa bổ trợ cho cạnh quan hệ.",
    )

    @model_validator(mode="after")
    def validate_edge_targets(self) -> StagingEdge:

        clean_src = self.source_path.strip() if self.source_path else ""
        if not clean_src:
            raise ValueError("source_path không được để trống")
        self.source_path = validate_ltree_path(clean_src)

        clean_tgt = self.target_path.strip() if self.target_path else None
        clean_ext = self.target_external_ref.strip() if self.target_external_ref else None

        if not clean_tgt and not clean_ext:
            raise ValueError(
                f"Cạnh quan hệ đồ thị xuất phát từ '{self.source_path}' bắt buộc phải có ít nhất một đích đến: "
                "'target_path' (cho liên kết nội bộ) hoặc 'target_external_ref' (cho viện dẫn văn bản ngoài)."
            )

        if clean_tgt:
            self.target_path = validate_ltree_path(clean_tgt)
        else:
            self.target_path = None

        self.target_external_ref = clean_ext
        return self


# ---------------------------------------------------------------------------
# Staging Operation Result Models (Consolidated from legacy mcp.tools.schemas)
# ---------------------------------------------------------------------------

StgGrepScope = Literal["ALL", "VERBATIM", "CONTEXT", "PATH", "METADATA"]
StagingStatusFilter = Literal[
    "DRAFT", "AGENT_COMMITTED", "APPROVED", "PROMOTED", "AMENDMENT", ""
]
RelationTypeFilter = Literal[
    "REFERENCES",
    "SUPPORTS",
    "CONTRADICTS",
    "DEFINES",
    "EXTENDS",
    "EXEMPLIFIES",
    "DEPENDS_ON",
    "SUPERSEDES",
    "SEE_ALSO",
    "",
]


class StgPreviewHit(BaseModel):
    model_config = ConfigDict(extra="ignore")

    path: str
    lead_sentence: str
    preview_text: str
    char_length: int = 0
    is_truncated: bool = False
    metadata: dict[str, object] = Field(default_factory=dict)


class StgPreviewResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    doc_slug: str
    title: str
    total_chunks: int
    total_edges: int
    total_matched: int = 0
    limit: int = 50
    offset: int = 0
    has_more: bool = False
    chunks: list[StgPreviewHit]


class StgGetChunkResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    doc_slug: str
    chunk: StagingChunk


class StgGetRawResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    doc_slug: str
    start_line: int
    end_line: int
    total_lines: int
    content: str


class StgGrepResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    doc_slug: str
    pattern: str
    is_regex: bool
    total_matches: int
    matches: list[StagingGrepHit]


class StgPatchResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    doc_slug: str
    status: str = "SUCCESS"
    updated_count: int = 0
    cascaded_count: int = 0
    removed_count: int = 0
    total_chunks_after_patch: int
    fields_modified: list[str] = Field(default_factory=list)


class StgAddEdgesResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    doc_slug: str
    status: str
    total_edges: int


class StgCommitResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    doc_slug: str
    status: str = "AGENT_COMMITTED"
    total_chunks: int
    total_edges: int
    committed_at: str
    message: str


class ChunkProgressStats(BaseModel):
    model_config = ConfigDict(extra="ignore")

    total_chunks: int = Field(..., description="Tổng số chunk trong văn bản")
    finalized_count: int = Field(..., description="Số chunk đã chốt hoàn tất")
    pending_count: int = Field(..., description="Số chunk còn chờ rà soát")
    progress_percent: float = Field(..., description="Tỷ lệ tiến độ (%)")


class StgPollPendingResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    doc_slug: str = Field(..., description="Mã định danh slug của văn bản")
    progress: ChunkProgressStats = Field(..., description="Thống kê tiến độ rà soát")
    limit: int = Field(..., description="Giới hạn số chunk trả về trong đợt này")
    has_more: bool = Field(..., description="Còn chunk chưa chốt hay không")
    chunks: list[StagingChunk] = Field(..., description="Danh sách các chunk chờ xử lý")


class ChunkFinalizeStatus(BaseModel):
    model_config = ConfigDict(extra="ignore")

    path: str = Field(..., description="Đường dẫn ltree của chunk")
    review_status: ChunkReviewStatus = Field(..., description="Trạng thái rà soát (REVIEWED)")
    finalization_state: FinalizationState = Field(
        ..., description="Trạng thái hoàn thiện được tự động suy diễn"
    )


class StgFinalizeResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    doc_slug: str = Field(..., description="Mã định danh slug của văn bản")
    status: str = Field("SUCCESS", description="Trạng thái thực thi")
    finalized_count: int = Field(..., description="Số lượng chunk vừa được chốt")
    pending_remaining: int = Field(..., description="Số lượng chunk còn lại chưa chốt")
    paths: list[str] = Field(default_factory=list, description="Danh sách các đường dẫn đã chốt")
    results: list[ChunkFinalizeStatus] = Field(
        default_factory=list,
        description="Chi tiết trạng thái được suy diễn tự động của từng chunk",
    )


class StgReopenResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    doc_slug: str = Field(..., description="Mã định danh slug của văn bản")
    status: str = Field("AMENDMENT", description="Trạng thái phiên làm việc sau khi mở lại")
    total_chunks: int = Field(..., description="Tổng số chunk trong phiên làm việc")
    reopened_at: str = Field(..., description="Thời điểm mở lại phiên làm việc (ISO 8601)")
    message: str = Field(..., description="Thông điệp kết quả")


class StgRemoveEdgeResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    doc_slug: str = Field(..., description="Mã định danh slug của văn bản")
    status: str = Field("SUCCESS", description="Trạng thái thực thi")
    removed_count: int = Field(default=1, description="Số lượng cạnh quan hệ đã xóa")
    total_edges: int = Field(..., description="Tổng số cạnh quan hệ còn lại")
    message: str = Field(..., description="Thông điệp kết quả")


class StgListSessionsResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    total_sessions: int = Field(..., description="Tổng số phiên làm việc trong staging")
    sessions: list[StagingSessionSummary] = Field(
        default_factory=list, description="Danh sách tóm tắt các phiên làm việc"
    )
