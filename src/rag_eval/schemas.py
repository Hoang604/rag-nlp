from __future__ import annotations

import datetime
import re
import unicodedata
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Final
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ---------------------------------------------------------------------------
# Core Enums & Domain Literals
# ---------------------------------------------------------------------------


class HierarchicalDirection(str, Enum):
    CHILDREN = "CHILDREN"
    PARENT_CHAIN = "PARENT_CHAIN"
    SIBLINGS = "SIBLINGS"


class RelationType(str, Enum):
    REFERENCES = "REFERENCES"
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    DEFINES = "DEFINES"
    EXTENDS = "EXTENDS"
    EXEMPLIFIES = "EXEMPLIFIES"
    DEPENDS_ON = "DEPENDS_ON"
    SUPERSEDES = "SUPERSEDES"
    SEE_ALSO = "SEE_ALSO"


@dataclass(frozen=True)
class ParsedChunkDraft:
    path: str
    verbatim_text: str
    contextualized_text: str
    start_line: int
    end_line: int
    metadata: dict[str, object]


@dataclass(frozen=True)
class ParsedEdgeDraft:
    source_path: str
    target_path: str
    relation_type: RelationType


@dataclass(frozen=True)
class ParsedDocumentDraft:
    doc_slug: str
    title: str
    raw_text: str
    chunks: list[ParsedChunkDraft]
    edges: list[ParsedEdgeDraft]
    metadata: dict[str, object]


@dataclass(frozen=True)
class IngestionResult:
    document_id: uuid.UUID
    doc_slug: str
    title: str
    chunks_count: int
    edges_count: int
    skipped: bool = False


_LTREE_LABEL_REGEX: Final = re.compile(r"^[A-Za-z0-9_]{1,255}$")
LTREE_PATH_REGEX: Final = re.compile(r"^[A-Za-z0-9_]+(\.[A-Za-z0-9_]+)*$")


def sanitize_ltree_label(raw: str) -> str:
    """Chuẩn hóa chuỗi nhãn phân cấp cho ltree (chỉ chữ, số, dấu gạch dưới, tối đa 250 ký tự)."""
    text = raw.replace("đ", "d").replace("Đ", "D")
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", stripped).strip("_").lower()
    bounded = cleaned[:250].strip("_")
    return bounded or "node"


def validate_ltree_path(path: str) -> str:
    """Xác thực đường dẫn phân cấp ltree theo tiêu chuẩn PostgreSQL ltree."""
    clean_path = path.strip()
    if not clean_path:
        raise ValueError("Đường dẫn ltree không được để trống.")

    labels = clean_path.split(".")
    for idx, label in enumerate(labels):
        if not label:
            raise ValueError(f"Đường dẫn ltree '{clean_path}' chứa nhãn rỗng ở vị trí {idx}.")
        if not _LTREE_LABEL_REGEX.match(label):
            raise ValueError(
                f"Nhãn '{label}' trong đường dẫn '{clean_path}' không hợp lệ. "
                "Chỉ được chứa chữ cái, chữ số và dấu gạch dưới (tối đa 255 ký tự)."
            )
    return clean_path


def is_ancestor_path(ancestor_candidate: str, path: str) -> bool:
    """Xác định liệu ancestor_candidate có phải là tiền tố phân cấp tổ tiên nghiêm ngặt của path hay không."""
    clean_anc = validate_ltree_path(ancestor_candidate)
    clean_p = validate_ltree_path(path)
    return clean_p.startswith(f"{clean_anc}.")


# ---------------------------------------------------------------------------
# Database Entities (Ánh xạ 1:1 với Schema PostgreSQL)
# ---------------------------------------------------------------------------


class DocumentEntity(BaseModel):
    """Thực thể tài liệu - Bảng `documents` (002_documents.sql)."""

    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid.uuid4, description="Khóa chính định danh tài liệu")
    doc_slug: str = Field(..., description="Mã định danh duy nhất (slug) của tài liệu")
    title: str = Field(..., description="Tiêu đề chính thức của tài liệu")
    raw_text: str | None = Field(default=None, description="Toàn văn thô của tài liệu gốc")
    metadata: dict[str, object] = Field(default_factory=dict, description="Siêu dữ liệu mở rộng dạng JSONB")
    created_at: datetime.datetime | None = Field(default=None, description="Thời điểm khởi tạo")
    updated_at: datetime.datetime | None = Field(default=None, description="Thời điểm cập nhật gần nhất")


class ChunkEntity(BaseModel):
    """Thực thể chunk tài liệu - Bảng `chunks` (003_chunks.sql)."""

    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid.uuid4, description="Khóa chính UUID của chunk")
    document_id: UUID = Field(..., description="Khoá ngoại tham chiếu documents(id)")
    path: str = Field(..., description="Đường dẫn phân cấp ltree")
    verbatim_text: str = Field(..., description="Nội dung nguyên văn của chunk")
    contextualized_text: str = Field(..., description="Nội dung ngữ cảnh đầy đủ")
    start_line: int = Field(default=1, ge=1, description="Dòng bắt đầu 1-indexed trong tài liệu gốc")
    end_line: int = Field(default=1, ge=1, description="Dòng kết thúc 1-indexed trong tài liệu gốc")
    embedding: list[float] | None = Field(default=None, description="Vector nhúng dense 512 chiều")
    metadata: dict[str, object] = Field(default_factory=dict, description="Siêu dữ liệu mở rộng dạng JSONB")
    created_at: datetime.datetime | None = Field(default=None, description="Thời điểm khởi tạo")
    updated_at: datetime.datetime | None = Field(default=None, description="Thời điểm cập nhật gần nhất")

    @field_validator("path")
    @classmethod
    def _validate_path(cls, v: str) -> str:
        return validate_ltree_path(v)


class GraphEdgeEntity(BaseModel):
    """Thực thể cạnh quan hệ tri thức - Bảng `graph_edges` (005_graph_edges.sql)."""

    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid.uuid4, description="Khóa chính định danh cạnh quan hệ")
    source_chunk_id: UUID = Field(..., description="UUID của chunk nguồn tham chiếu chunks(id)")
    target_chunk_id: UUID = Field(..., description="UUID của chunk đích tham chiếu chunks(id)")
    relation_type: str = Field(..., description="Mã quan hệ tham chiếu relation_types(code)")
    created_at: datetime.datetime | None = Field(default=None, description="Thời điểm khởi tạo")
    rationale: str | None = Field(default=None, description="Lý do / bằng chứng luận cứ kết nối hai chunk")


# ---------------------------------------------------------------------------
# Database Query DTOs (Ánh xạ 1:1 với Stored Procedures & Repo Queries)
# ---------------------------------------------------------------------------


class DocumentStatsDTO(BaseModel):
    """Thống kê tài liệu kèm số lượng chunk - Query `list_with_stats`."""

    model_config = ConfigDict(extra="ignore")

    id: UUID
    doc_slug: str
    title: str
    metadata: dict[str, object] = Field(default_factory=dict)
    chunk_count: int = 0


class RelationTypeCatalogDTO(BaseModel):
    """Danh mục loại quan hệ tri thức - Bảng `relation_types` (004_relation_types.sql)."""

    model_config = ConfigDict(extra="ignore")

    code: str
    description: str
    is_symmetric: bool


class HybridSearchQuery(BaseModel):
    """Tham số đầu vào cho stored procedure `hybrid_search`."""

    model_config = ConfigDict(extra="ignore")

    query_text: str = ""
    query_vector: list[float] | None = None
    match_limit: int = 10
    rrf_k: int = 60
    target_documents: list[str] | None = None
    path_prefix: str | None = None
    ts_config: str = "simple"


class VerbatimGrepQuery(BaseModel):
    """Tham số đầu vào cho stored procedure `verbatim_grep`."""

    model_config = ConfigDict(extra="ignore")

    query_pattern: str
    target_documents: list[str] | None = None
    path_prefix: str | None = None
    is_regex: bool = False
    case_sensitive: bool = False
    match_limit: int = 50


class SearchHitDTO(BaseModel):
    """Kết quả truy vấn hỗn hợp từ stored procedure `hybrid_search` (006_stored_procs.sql)."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: UUID
    doc_slug: str
    doc_title: str
    path: str
    start_line: int
    end_line: int
    verbatim_text: str
    contextualized_text: str
    metadata: dict[str, object] = Field(default_factory=dict)
    score: float = 0.0
    rrf_score: float = 0.0
    dense_rank: int | None = None
    sparse_rank: int | None = None
    dense_similarity: float = 0.0
    rerank_score: float | None = None

    @field_validator("chunk_id", mode="before")
    @classmethod
    def _coerce_uuid(cls, v: object) -> UUID:
        return v if isinstance(v, UUID) else UUID(str(v))

    @field_validator("score", "rrf_score", mode="before")
    @classmethod
    def _coerce_float(cls, v: object) -> float:
        if isinstance(v, (int, float, str)):
            try:
                return float(v)
            except ValueError:
                return 0.0
        return 0.0


class AgentVennHit(BaseModel):
    model_config = ConfigDict(extra="ignore")

    doc_slug: str
    doc_title: str
    path: str
    start_line: int = Field(..., ge=1, description="Số dòng bắt đầu trong tài liệu")
    end_line: int = Field(..., ge=1, description="Số dòng kết thúc trong tài liệu")
    verbatim_text: str
    contextualized_text: str
    metadata: dict[str, object] = Field(default_factory=dict)
    semantic_rank: int | None = Field(default=None, ge=1)
    verbatim_rank: int | None = Field(default=None, ge=1)
    semantic_score: float | None = None
    verbatim_score: float | None = None
    rerank_score: float | None = None


class VennSearchResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    query: str
    pattern: str
    both_hits: list[AgentVennHit] = Field(default_factory=list)
    semantic_only_hits: list[AgentVennHit] = Field(default_factory=list)
    verbatim_only_hits: list[AgentVennHit] = Field(default_factory=list)
    total_unique_hits: int = 0
    confidence: str = "high"


class HierarchyNodeDTO(BaseModel):
    """Nút duyệt cây phân cấp từ truy vấn `navigate_hierarchy`."""

    model_config = ConfigDict(extra="ignore")

    chunk_id: UUID
    path: str
    doc_slug: str
    start_line: int = 1
    end_line: int = 1
    verbatim_text: str
    contextualized_text: str
    metadata: dict[str, object] = Field(default_factory=dict)
    relative_depth: int = 0

    @field_validator("chunk_id", mode="before")
    @classmethod
    def _coerce_uuid(cls, v: object) -> UUID:
        return v if isinstance(v, UUID) else UUID(str(v))


class GraphTraversalStepDTO(BaseModel):
    """Bước duyệt đồ thị quan hệ từ stored procedure `traverse_knowledge_graph` (006_stored_procs.sql & 007_graph_traversal_enhancements.sql)."""

    model_config = ConfigDict(extra="ignore")

    edge_id: UUID
    source_chunk_id: UUID
    target_chunk_id: UUID
    relation_type: str
    depth: int
    source_path: str = Field(..., min_length=1, description="Đường dẫn LTree của chunk nguồn")
    target_path: str = Field(..., min_length=1, description="Đường dẫn LTree của chunk đích")
    target_text: str = Field(..., description="Nội dung văn bản gốc của chunk đích")
    target_contextualized_text: str = Field(..., min_length=1, description="Đoạn văn phả hệ hoàn chỉnh của chunk đích")
    target_doc_slug: str = Field(..., min_length=1, description="Mã định danh tài liệu chứa chunk đích")
    target_start_line: int = Field(..., ge=1, description="Dòng bắt đầu 1-indexed trong văn bản gốc")
    target_end_line: int = Field(..., ge=1, description="Dòng kết thúc 1-indexed trong văn bản gốc")
    rationale: str | None = Field(default=None, description="Luận cứ liên kết ngữ nghĩa giữa hai nút")

    @field_validator("edge_id", "source_chunk_id", "target_chunk_id", mode="before")
    @classmethod
    def _coerce_uuid(cls, v: object) -> UUID:
        return v if isinstance(v, UUID) else UUID(str(v))
