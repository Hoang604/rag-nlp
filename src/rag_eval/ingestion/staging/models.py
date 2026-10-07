from __future__ import annotations

import datetime
import uuid
from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rag_eval.schemas import (
    ContextType,
    FinalizationState,
    validate_ltree_path,
)


def _resolve_default_staging_dir() -> Path:
    """Resolves absolute staging directory anchored to repository root or STAGING_DIR env var."""
    import os

    curr = Path(__file__).resolve().parent
    repo_root = Path.cwd()
    for parent in [curr, *curr.parents]:
        if (parent / "pyproject.toml").exists() and (parent / "src" / "rag_eval").exists():
            repo_root = parent
            break

    env_dir = os.environ.get("STAGING_DIR")
    if env_dir:
        p = Path(env_dir)
        if not p.is_absolute():
            return (repo_root / p).resolve()
        return p.resolve()
    return (repo_root / ".cache" / "stg").resolve()



DEFAULT_STAGING_DIR = _resolve_default_staging_dir()


def get_staging_poll_limit() -> int:
    """Reads STAGING_POLL_LIMIT (or STAGING_BATCH_SIZE) from env, bounded to [1, 50], default 5."""
    import os

    raw = os.environ.get("STAGING_POLL_LIMIT") or os.environ.get("STAGING_BATCH_SIZE")
    if raw:
        try:
            return max(1, min(int(raw), 50))
        except ValueError:
            pass
    return 5


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


class StagingViolationCode(str, Enum):
    UNINSPECTED_CHUNK = "UNINSPECTED_CHUNK"
    UNCLASSIFIED_CHUNK = "UNCLASSIFIED_CHUNK"
    MISSING_RELATION_EDGE = "MISSING_RELATION_EDGE"
    INVALID_RELATION_ON_SELF_CONTAINED = "INVALID_RELATION_ON_SELF_CONTAINED"
    BATCH_LIMIT_EXCEEDED = "BATCH_LIMIT_EXCEEDED"


class StagingViolationData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    violation_code: StagingViolationCode = Field(..., description="Mã lỗi máy đọc được.")
    path: str = Field(..., description="Đường dẫn phân cấp của chunk vi phạm.")
    doc_slug: str = Field(..., description="Mã định danh tài liệu.")
    message: str = Field(..., description="Mô tả chi tiết nguyên nhân vi phạm.")
    remediation_hint: str = Field(
        ...,
        description="Chỉ dẫn nghĩa vụ nhận thức để tự sửa sai tuân thủ nguyên tắc chống gian lận.",
    )


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

    model_config = ConfigDict(extra="forbid")

    path: str = Field(
        ...,
        description="Đường dẫn phân cấp của chunk cần chỉnh sửa hoặc tạo mới.",
    )
    verbatim_text: str | None = Field(
        None,
        description="Nội dung nguyên văn mới của chunk.",
    )
    contextualized_text: str | None = Field(
        None,
        description="Nội dung ngữ cảnh đầy đủ mới sau khi ghép chuỗi phả hệ.",
    )
    start_line: int | None = Field(
        None,
        ge=1,
        description="Số dòng bắt đầu trong tài liệu nguồn tính từ 1.",
    )
    end_line: int | None = Field(
        None,
        ge=1,
        description="Số dòng kết thúc trong tài liệu nguồn tính từ 1.",
    )
    metadata: dict[str, object] | None = Field(
        None,
        description="Siêu dữ liệu ngữ nghĩa cần cập nhật bổ sung vào chunk.",
    )
    context_type: ContextType | None = Field(
        None,
        description="Phân loại ngữ nghĩa: SELF_CONTAINED (tự chứa) hoặc REQUIRES_EXTERNAL_CONTEXT (cần liên kết ngoài).",
    )
    justification: str | None = Field(
        None,
        description="Căn cứ thẩm định: giải trình vì sao tự chứa hoặc tóm tắt các điểm cần liên kết.",
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
    """Pairwise mapping from old path to new path."""

    old_path: str = Field(..., description="Original hierarchical path before migration")
    new_path: str = Field(..., description="Transformed hierarchical path after migration")


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

    model_config = ConfigDict(extra="forbid")

    doc_slug: str = Field(..., description="Mã định danh doc_slug của tài liệu")
    path: str = Field(..., description="Đường dẫn phân cấp phân cách bằng dấu chấm (hierarchical dot-separated path)")
    field_matched: str = Field(..., description="'VERBATIM' | 'CONTEXT' | 'PATH' | 'METADATA'")
    match_snippet: str = Field(..., description="Concise snippet highlighting the matched term")
    verbatim_text: str = Field(..., description="Complete verbatim text of the chunk")
    contextualized_text: str = Field(..., description="Full context text")
    start_line: int = Field(..., ge=1, description="Dòng bắt đầu trong văn bản nguồn")
    end_line: int = Field(..., ge=1, description="Dòng kết thúc trong văn bản nguồn")
    char_length: int = Field(..., ge=0, description="Character count of verbatim text")
    metadata: dict[str, object] = Field(default_factory=dict, description="Chunk metadata payload")


class StagingChunk(BaseModel):
    """Represents a candidate chunk within a staging session."""

    model_config = ConfigDict(extra="ignore")

    path: str = Field(..., description="Đường dẫn phân cấp phân cách bằng dấu chấm (hierarchical dot-separated path)")
    node_type: str = Field(
        default="PARAGRAPH",
        description="AST node type ('SECTION' | 'PARAGRAPH' | 'TABLE' | 'LIST' | 'CODE')",
    )
    verbatim_text: str = Field(..., description="Verbatim chunk text")
    contextualized_text: str = Field(..., description="Synthesized context text")
    start_line: int = Field(default=1, ge=1, description="1-indexed starting line number in source text")
    end_line: int = Field(default=1, ge=1, description="1-indexed ending line number in source text")
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
    context_type: ContextType | None = Field(
        default=None,
        description="Semantic context classification ('SELF_CONTAINED' | 'REQUIRES_EXTERNAL_CONTEXT')",
    )

    @model_validator(mode="after")
    def compute_char_length(self) -> StagingChunk:
        if not self.char_length and self.verbatim_text:
            self.char_length = len(self.verbatim_text)
        return self


class StagingEdgeFilter(BaseModel):
    """Bộ lọc xác định các cạnh quan hệ đồ thị cần xóa trong vùng đệm staging."""

    model_config = ConfigDict(extra="forbid")

    source_path: str = Field(
        ...,
        description="Đường dẫn phân cấp của chunk nguồn cần lọc xóa.",
    )
    target_path: str | None = Field(
        None,
        description="Đường dẫn phân cấp của chunk đích nội bộ cần lọc xóa (nếu có).",
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

        if not clean_tgt and not self.clear_all_targets:
            raise ValueError(
                f"Thao tác xóa cạnh từ '{self.source_path}' yêu cầu phải chỉ định 'target_path' "
                "để xác định đúng cạnh cần xóa. Nếu thực sự muốn xóa toàn bộ mọi cạnh xuất phát từ nút này, "
                "bắt buộc phải đặt 'clear_all_targets=True'."
            )

        if clean_tgt:
            self.target_path = validate_ltree_path(clean_tgt)
        else:
            self.target_path = None
        return self


class StagingEdgeInput(BaseModel):
    """Thông tin cạnh quan hệ đồ thị giữa hai chunk."""

    model_config = ConfigDict(extra="ignore")

    source_path: str = Field(
        ...,
        description="Đường dẫn phân cấp của chunk nguồn phát sinh quan hệ.",
    )
    target_path: str = Field(
        ...,
        description="Đường dẫn phân cấp của chunk đích trong cùng tài liệu hoặc tài liệu đã nạp.",
    )
    relation_type: RelationType = Field(
        default=RelationType.REFERENCES,
        description="Loại quan hệ có hướng giữa hai chunk.",
    )
    anchor_text: str | None = Field(
        default=None,
        description="Đoạn văn bản trích dẫn nguyên văn câu/cụm từ viện dẫn trong nội dung chunk nguồn làm căn cứ kết nối.",
    )

    @model_validator(mode="after")
    def validate_edge_targets(self) -> StagingEdgeInput:
        clean_src = self.source_path.strip() if self.source_path else ""
        clean_tgt = self.target_path.strip() if self.target_path else ""

        if not clean_src:
            raise ValueError("source_path không được để trống")
        if not clean_tgt:
            raise ValueError("target_path không được để trống")

        self.source_path = validate_ltree_path(clean_src)
        self.target_path = validate_ltree_path(clean_tgt)

        if self.source_path == self.target_path:
            raise ValueError(f"Self-referencing edge loop detected on '{self.source_path}'.")

        if self.anchor_text is not None:
            clean_anchor = self.anchor_text.strip()
            self.anchor_text = clean_anchor if clean_anchor else None

        return self


class StagingEdge(BaseModel):
    """Represents a candidate directed relation edge within a staging session."""

    model_config = ConfigDict(extra="ignore")

    source_path: str = Field(
        ...,
        description="Đường dẫn phân cấp của chunk nguồn phát sinh quan hệ.",
    )
    target_path: str = Field(
        ...,
        description="Đường dẫn phân cấp của chunk đích trong cùng tài liệu hoặc tài liệu đã nạp.",
    )
    relation_type: RelationType = Field(
        default=RelationType.REFERENCES,
        description="Loại quan hệ có hướng giữa hai chunk.",
    )
    anchor_text: str | None = Field(
        default=None,
        description="Đoạn văn bản trích dẫn nguyên văn câu/cụm từ viện dẫn trong nội dung chunk nguồn làm căn cứ kết nối.",
    )
    char_start: int | None = Field(
        default=None,
        description="Vị trí ký tự bắt đầu của tham chiếu trong verbatim_text.",
    )
    char_end: int | None = Field(
        default=None,
        description="Vị trí ký tự kết thúc của tham chiếu trong verbatim_text.",
    )

    @model_validator(mode="after")
    def validate_edge_targets(self) -> StagingEdge:
        clean_src = self.source_path.strip() if self.source_path else ""
        clean_tgt = self.target_path.strip() if self.target_path else ""

        if not clean_src:
            raise ValueError("source_path không được để trống")
        if not clean_tgt:
            raise ValueError("target_path không được để trống")

        self.source_path = validate_ltree_path(clean_src)
        self.target_path = validate_ltree_path(clean_tgt)

        if self.source_path == self.target_path:
            raise ValueError(f"Self-referencing edge loop detected on '{self.source_path}'.")

        if self.anchor_text is not None:
            clean_anchor = self.anchor_text.strip()
            self.anchor_text = clean_anchor if clean_anchor else None

        # Khớp với ràng buộc PostgreSQL chk_ref_span_geometry
        if (self.char_start is None and self.char_end is not None) or (
            self.char_start is not None and self.char_end is None
        ):
            raise ValueError("char_start và char_end phải cùng có giá trị hoặc cùng là None.")

        if (
            self.char_start is not None
            and self.char_end is not None
            and (self.char_start < 0 or self.char_end <= self.char_start)
        ):
            raise ValueError("char_end phải lớn hơn char_start và char_start >= 0.")

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


class GrepHit(BaseModel):
    """Targeted search hit highlighting matched terms in context without dumping entire provisions."""

    model_config = ConfigDict(extra="forbid")

    rank: int = Field(..., ge=1, description="Thứ tự kết quả khớp")
    path: str = Field(..., description="Đường dẫn phân cấp của chunk")
    doc_slug: str = Field(..., description="Mã tài liệu")
    snippet: str = Field(..., description="Trích đoạn chứa từ khóa được bôi đậm")
    field_matched: str = Field(..., description="Trường dữ liệu khớp ('VERBATIM' | 'CONTEXT' | 'PATH' | 'METADATA')")
    start_line: int = Field(..., ge=1, description="Dòng bắt đầu")
    end_line: int = Field(..., ge=1, description="Dòng kết thúc")


class StgGrepResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_slug: str | None = Field(None, description="Mã định danh doc_slug (hoặc None nếu quét toàn cục)")
    pattern: str = Field(..., description="Cụm từ tìm kiếm hoặc Regex")
    is_regex: bool = Field(False, description="Cờ Regex")
    total_matches: int = Field(..., description="Tổng số kết quả khớp")
    hits: list[GrepHit] = Field(default_factory=list, description="Danh sách kết quả khớp dạng snippet")


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

    total_chunks: int = Field(..., description="Tổng số chunk trong tài liệu")
    finalized_count: int = Field(..., description="Số chunk đã chốt hoàn tất")
    pending_count: int = Field(..., description="Số chunk còn chờ rà soát")
    progress_percent: float = Field(..., description="Tỷ lệ tiến độ (%)")


class PendingChunkLeaf(BaseModel):
    """Lightweight leaf provision node for staging review stripped of redundant parent strings."""

    model_config = ConfigDict(extra="forbid")

    path: str = Field(..., description="Đường dẫn phân cấp ltree đầy đủ của đoạn quy phạm")
    verbatim_text: str = Field(..., description="Nội dung nguyên văn của đoạn quy phạm")
    start_line: int = Field(..., ge=1, description="Dòng bắt đầu trong văn bản nguồn")
    end_line: int = Field(..., ge=1, description="Dòng kết thúc trong văn bản nguồn")
    context_type: ContextType | None = Field(
        default=None,
        description="Phân loại ngữ nghĩa: SELF_CONTAINED hoặc REQUIRES_EXTERNAL_CONTEXT",
    )
    justification: str | None = Field(
        default=None,
        description="Căn cứ thẩm định giải trình tính tự chứa hoặc tóm tắt phụ thuộc",
    )


class PendingChunkGroup(BaseModel):
    """Group of leaf provisions sharing an immediate parent hierarchical context."""

    model_config = ConfigDict(extra="forbid")

    parent_path: str = Field(..., description="Đường dẫn phân cấp ltree của cấp cha")
    parent_context: str = Field(..., description="Tiêu đề và ngữ cảnh cha dùng chung cho cả nhóm")
    chunks: list[PendingChunkLeaf] = Field(..., description="Danh sách các đoạn con trong nhóm")


class StgPollPendingResult(BaseModel):
    """Hierarchically grouped pending chunks queue polling result."""

    model_config = ConfigDict(extra="forbid")

    doc_slug: str = Field(..., description="Mã định danh slug của tài liệu")
    progress: ChunkProgressStats = Field(..., description="Thống kê tiến độ rà soát")
    limit: int = Field(..., description="Giới hạn số chunk trả về trong đợt này")
    has_more: bool = Field(..., description="Còn chunk chưa chốt hay không")
    returned_chunks: int = Field(..., ge=0, description="Tổng số chunk con được trả về trong đợt này")
    groups: list[PendingChunkGroup] = Field(..., description="Các nhóm chunk kèm ngữ cảnh cha dùng chung")


class ChunkFinalizeStatus(BaseModel):
    model_config = ConfigDict(extra="ignore")

    path: str = Field(..., description="Đường dẫn phân cấp của chunk")
    review_status: ChunkReviewStatus = Field(..., description="Trạng thái rà soát (REVIEWED)")
    finalization_state: FinalizationState = Field(
        ..., description="Trạng thái hoàn thiện được tự động suy diễn"
    )
    context_type: ContextType | None = Field(
        None,
        description="Phân loại ngữ nghĩa: SELF_CONTAINED hoặc REQUIRES_EXTERNAL_CONTEXT",
    )


class StgFinalizeResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    doc_slug: str = Field(..., description="Mã định danh slug của tài liệu")
    status: str = Field("SUCCESS", description="Trạng thái thực thi")
    finalized_count: int = Field(..., description="Số lượng chunk vừa được chốt")
    pending_remaining: int = Field(..., description="Số lượng chunk còn lại chưa chốt")
    paths: list[str] = Field(default_factory=list, description="Danh sách các đường dẫn đã chốt")
    results: list[ChunkFinalizeStatus] = Field(
        default_factory=list,
        description="Chi tiết trạng thái được suy diễn tự động của từng chunk",
    )


class StgUnfinalizeResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    doc_slug: str = Field(..., description="Mã định danh slug của tài liệu")
    status: str = Field("SUCCESS", description="Trạng thái thực thi")
    unfinalized_count: int = Field(..., description="Số lượng chunk vừa được mở lại về PENDING")
    pending_remaining: int = Field(..., description="Số lượng chunk còn lại chưa chốt")
    paths: list[str] = Field(default_factory=list, description="Danh sách các đường dẫn đã mở lại")
    results: list[ChunkFinalizeStatus] = Field(
        default_factory=list,
        description="Chi tiết trạng thái của từng chunk sau khi mở lại",
    )


class StgReopenResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    doc_slug: str = Field(..., description="Mã định danh slug của tài liệu")
    status: str = Field("AMENDMENT", description="Trạng thái phiên làm việc sau khi mở lại")
    total_chunks: int = Field(..., description="Tổng số chunk trong phiên làm việc")
    reopened_at: str = Field(..., description="Thời điểm mở lại phiên làm việc (ISO 8601)")
    message: str = Field(..., description="Thông điệp kết quả")


class StgRemoveEdgesResult(BaseModel):
    """Kết quả phản hồi của thao tác xóa cạnh quan hệ đồ thị staging."""

    model_config = ConfigDict(extra="forbid")

    doc_slug: str = Field(..., description="Mã định danh slug của tài liệu")
    status: str = Field("SUCCESS", description="Trạng thái thực thi")
    removed_count: int = Field(..., ge=0, description="Số lượng cạnh quan hệ đã xóa")
    total_edges: int = Field(..., ge=0, description="Tổng số cạnh quan hệ còn lại")
    message: str = Field(..., description="Thông điệp kết quả")


class StgListSessionsResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    total_sessions: int = Field(..., description="Tổng số phiên làm việc trong staging")
    sessions: list[StagingSessionSummary] = Field(
        default_factory=list, description="Danh sách tóm tắt các phiên làm việc"
    )
