from __future__ import annotations

import datetime
import hashlib
import re
import unicodedata
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Final, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ---------------------------------------------------------------------------
# Core Enums & Domain Literals
# ---------------------------------------------------------------------------


class HierarchicalDirection(str, Enum):
    CHILDREN = "CHILDREN"
    PARENT_CHAIN = "PARENT_CHAIN"
    SIBLINGS = "SIBLINGS"
    SUBTREE = "SUBTREE"


HIERARCHICAL_DIRECTION_DESCRIPTIONS: Final[dict[HierarchicalDirection, str]] = {
    HierarchicalDirection.CHILDREN: "Lấy các nút con trực tiếp (cấp nlevel + 1).",
    HierarchicalDirection.PARENT_CHAIN: "Lấy chuỗi tổ tiên từ tài liệu gốc xuống đến nút cha trực tiếp.",
    HierarchicalDirection.SIBLINGS: "Lấy các nút anh em cùng cấp dưới cùng một nút cha.",
    HierarchicalDirection.SUBTREE: "Lấy toàn bộ cây con hậu duệ theo đúng thứ tự đọc của tài liệu (start_line ASC, path ASC).",
}

assert set(HIERARCHICAL_DIRECTION_DESCRIPTIONS) == set(HierarchicalDirection), (
    f"Thiếu description cho HierarchicalDirection: {set(HierarchicalDirection) - set(HIERARCHICAL_DIRECTION_DESCRIPTIONS)}"
)


def format_hierarchical_direction_docs() -> str:
    return "Hướng duyệt trên cây phân cấp: " + "; ".join(
        f"'{k.value}': {desc}" for k, desc in HIERARCHICAL_DIRECTION_DESCRIPTIONS.items()
    )


def format_hierarchical_direction_values() -> str:
    return ", ".join(k.value for k in HierarchicalDirection)


class GraphDirection(str, Enum):
    """Hướng duyệt liên kết trên đồ thị tri thức."""

    OUTGOING = "OUTGOING"
    INCOMING = "INCOMING"
    BOTH = "BOTH"


GRAPH_DIRECTION_DESCRIPTIONS: Final[dict[GraphDirection, str]] = {
    GraphDirection.OUTGOING: "Các liên kết xuất phát từ nút này trỏ tới các nút khác.",
    GraphDirection.INCOMING: "Các liên kết từ các nút khác trỏ về nút này.",
    GraphDirection.BOTH: "Duyệt liên kết theo cả hai chiều (cả đến và đi).",
}

assert set(GRAPH_DIRECTION_DESCRIPTIONS) == set(GraphDirection), (
    f"Thiếu description cho GraphDirection: {set(GraphDirection) - set(GRAPH_DIRECTION_DESCRIPTIONS)}"
)


def format_graph_direction_docs() -> str:
    return "Hướng duyệt đồ thị: " + "; ".join(
        f"'{k.value}': {desc}" for k, desc in GRAPH_DIRECTION_DESCRIPTIONS.items()
    )


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


RELATION_TYPE_DESCRIPTIONS: Final[dict[RelationType, str]] = {
    RelationType.REFERENCES: "Tham chiếu thông tin trung lập hoặc liên kết chung",
    RelationType.SUPPORTS: "Cung cấp dữ liệu, số liệu, củng cố ngữ cảnh cho nút đích",
    RelationType.CONTRADICTS: "Mâu thuẫn hoặc xung đột thông tin với nút đích",
    RelationType.DEFINES: "Định nghĩa thuật ngữ, khái niệm hoặc thực thể được sử dụng ở nút đích",
    RelationType.EXTENDS: "Mở rộng, bổ sung chi tiết hoặc phát triển thêm ý từ nút đích",
    RelationType.EXEMPLIFIES: "Cung cấp ví dụ thực tế hoặc ca nghiên cứu minh họa cho nút đích",
    RelationType.DEPENDS_ON: "Phụ thuộc tiên quyết logic hoặc kỹ thuật vào nút đích",
    RelationType.SUPERSEDES: "Thay thế hoặc làm lỗi thời nội dung ở nút đích",
    RelationType.SEE_ALSO: "Liên kết liên tưởng ngữ cảnh, nội dung tham khảo thêm",
}

assert set(RELATION_TYPE_DESCRIPTIONS) == set(RelationType), (
    f"Thiếu description cho RelationType: {set(RelationType) - set(RELATION_TYPE_DESCRIPTIONS)}"
)


def format_relation_type_docs() -> str:
    return "Lọc danh sách các mã quan hệ cần duyệt: " + "; ".join(
        f"'{k.value}' ({desc})" for k, desc in RELATION_TYPE_DESCRIPTIONS.items()
    ) + ". Để None để duyệt tất cả."


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
    citation_text: str


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


@dataclass(frozen=True)
class CorpusIngestionSummary:
    total_documents: int
    total_chunks: int
    total_edges: int
    skipped_documents: int


_LTREE_LABEL_REGEX: Final = re.compile(r"^[A-Za-z0-9_]{1,255}$")
LTREE_PATH_REGEX: Final = re.compile(r"^[A-Za-z0-9_]+(\.[A-Za-z0-9_]+)*$")


def sanitize_ltree_label(raw: str) -> str:
    """Universal ltree label sanitizer supporting global scripts while rejecting invalid empty inputs."""
    clean_raw = raw.strip()
    if not clean_raw:
        raise ValueError("Ltree label cannot be empty or whitespace.")
    if not any(c.isalnum() for c in clean_raw):
        raise ValueError(f"Ltree label '{raw}' contains no alphanumeric characters.")

    text = clean_raw.replace("đ", "d").replace("Đ", "D")
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", stripped).strip("_").lower()
    bounded = cleaned[:250].strip("_")
    if not bounded:
        # Valid non-Latin Unicode scripts (CJK, Arabic, Cyrillic) map to deterministic ASCII hash
        raw_hash = hashlib.md5(clean_raw.encode("utf-8")).hexdigest()[:12]
        bounded = f"u_{raw_hash}"
    return bounded


def canonicalize_ltree_path(raw: str) -> str:
    """Chuẩn hóa đường dẫn phân cấp ltree nhiều cấp bậc từ đường dẫn tệp tin hoặc slug.

    Đảm bảo mỗi phân đoạn tuân thủ nhãn ltree trong khi vẫn bảo tồn dấu chấm phân cấp ('.')
    và bảo tồn các tiền tố số thứ tự nhận diện.
    """
    clean_raw = raw.replace("/", ".").replace("\\", ".")
    raw_segments = [s.strip() for s in clean_raw.split(".") if s.strip()]
    sanitized_segments: list[str] = []
    for seg in raw_segments:
        label = sanitize_ltree_label(seg)
        if label:
            sanitized_segments.append(label)
    if not sanitized_segments:
        raise ValueError(f"Không thể tạo đường dẫn ltree hợp lệ từ '{raw}'.")
    return ".".join(sanitized_segments)


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
    citation_text: str = Field(..., min_length=1, description="Trích dẫn nguyên văn từ chunk nguồn chứng minh quan hệ")


class EdgeLogEntity(BaseModel):
    """Thực thể nhật ký kiểm toán quan hệ đồ thị - Bảng `graph_edge_log` (010_graph_edge_log_audit.sql)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID = Field(default_factory=uuid.uuid4, description="Khóa chính định danh dòng log")
    action: Literal["ADDED", "REMOVED"] = Field(..., description="Hành động: ADDED hoặc REMOVED")
    actor: str = Field(..., description="Chủ thể thực hiện (AGENT, CLI, API)")
    source_path: str = Field(..., description="Đường dẫn LTree của chunk nguồn")
    target_path: str = Field(..., description="Đường dẫn LTree của chunk đích")
    relation_type: RelationType = Field(..., description="Mã quan hệ")
    citation_text: str = Field(..., min_length=1, description="Trích dẫn nguyên văn chứng minh quan hệ")
    reason: str = Field(..., min_length=1, description="Lý do / ngữ cảnh nhiệm vụ phục vụ kiểm toán")
    created_at: datetime.datetime = Field(..., description="Thời điểm ghi nhận sự kiện")


class EdgeKey(BaseModel):
    """Định danh duy nhất một cạnh đồ thị theo bộ ba (source_path, target_path, relation_type)."""

    model_config = ConfigDict(extra="forbid")

    source_path: str = Field(..., description="Đường dẫn LTree chunk nguồn")
    target_path: str = Field(..., description="Đường dẫn LTree chunk đích (có thể là container)")
    relation_type: RelationType = Field(..., description="Mã quan hệ theo danh mục RelationType")


class EdgeProposal(EdgeKey):
    """Đề xuất thêm cạnh quan hệ tri thức từ agent với bằng chứng trích dẫn."""

    model_config = ConfigDict(extra="forbid")

    citation_text: str = Field(..., min_length=1, description="Đoạn văn trích dẫn nguyên văn từ chunk nguồn")
    rationale: str | None = Field(default=None, description="Luận cứ ngữ nghĩa kết nối hai nút")


class CurateEdgesResult(BaseModel):
    """Kết quả thực thi batch curation quan hệ đồ thị tri thức."""

    model_config = ConfigDict(extra="forbid")

    added: list[EdgeKey] = Field(default_factory=list, description="Danh sách các cạnh đã thêm mới thành công")
    existing: list[EdgeKey] = Field(default_factory=list, description="Danh sách các cạnh đã tồn tại từ trước")
    removed: list[EdgeKey] = Field(default_factory=list, description="Danh sách các cạnh đã gỡ bỏ thành công")
    not_found: list[EdgeKey] = Field(default_factory=list, description="Danh sách các cạnh yêu cầu gỡ nhưng không tồn tại")
    message: str = Field(..., description="Thông điệp tóm tắt kết quả thực thi")


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
    order_by_reading_order: bool = False


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


def split_context_and_text(contextualized_text: str, verbatim_text: str) -> tuple[str, str]:
    """Splits contextualized text into an ancestor context breadcrumb and clean chunk text.

    In the ingestion pipeline, contextualized_text is synthesized as:
        f"[{' > '.join(ancestors)}]\n{clean_verbatim}" if ancestors else clean_verbatim
    If contextualized_text matches verbatim_text (stripped), there is no ancestral context.
    """
    clean_verb = verbatim_text.strip()
    clean_ctx = contextualized_text.strip()
    if clean_ctx == clean_verb or not clean_ctx:
        return "", clean_verb

    if clean_ctx.startswith("[") and "]\n" in clean_ctx:
        idx = clean_ctx.find("]\n")
        prefix = clean_ctx[1:idx].strip()
        suffix = clean_ctx[idx + 2:].strip()
        if suffix == clean_verb or not suffix:
            return prefix, clean_verb

    return "", clean_ctx or clean_verb


# ---------------------------------------------------------------------------
# Factored Agent-First Retrieval Models & Context Groups
# ---------------------------------------------------------------------------

SearchFoundIn = Literal["both", "semantic_only", "verbatim_only"]


class SearchDocument(BaseModel):
    """Mô tả tài liệu xuất hiện trong kết quả truy xuất (được phát ra duy nhất 1 lần)."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., description="Tiêu đề tài liệu")
    doc_slug: str = Field(..., description="Mã slug định danh duy nhất của tài liệu")
    metadata: dict[str, object] = Field(default_factory=dict, description="Metadata mở rộng của tài liệu")


class ProvisionText(BaseModel):
    """Nội dung văn bản thuần của một chunk/provision (không lặp lại context cha)."""

    model_config = ConfigDict(extra="forbid")

    path: str = Field(..., description="Đường dẫn LTree phân cấp")
    text: str = Field(..., description="Nội dung văn bản thực tế của chunk")
    start_line: int = Field(..., ge=1, description="Dòng bắt đầu 1-indexed trong tài liệu gốc")
    end_line: int = Field(..., ge=1, description="Dòng kết thúc 1-indexed trong tài liệu gốc")
    metadata: dict[str, object] = Field(default_factory=dict, description="Metadata kỹ thuật sạch (node_type, is_table, v.v.)")


class SearchProvision(ProvisionText):
    """Provision trong kết quả tìm kiếm kèm phân vùng khớp và thứ hạng toàn cục 1..N."""

    model_config = ConfigDict(extra="forbid")

    found_in: SearchFoundIn = Field(..., description="Phân vùng Venn: 'both', 'semantic_only', hoặc 'verbatim_only'")
    rank: int = Field(..., ge=1, description="Thứ hạng toàn cục 1-based (both -> semantic_only -> verbatim_only)")


class ProvisionGroup[P: ProvisionText](BaseModel):
    """Nhóm các provisions trong cùng một tài liệu và chung ngữ cảnh phân cấp cha."""

    model_config = ConfigDict(extra="forbid")

    doc_slug: str = Field(..., description="Mã doc_slug của tài liệu chứa nhóm")
    context: str = Field(..., description="Ngữ cảnh tiêu đề tổ tiên (rỗng nếu nằm ngay dưới gốc tài liệu)")
    provisions: list[P] = Field(default_factory=list, description="Danh sách provisions được sắp xếp theo thứ tự đọc")


class UnifiedSearchResult(BaseModel):
    """Kết quả tìm kiếm dual-channel hợp nhất gom nhóm theo ngữ cảnh."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(..., description="Truy vấn ngữ nghĩa")
    pattern: str = Field(..., description="Từ khóa neo nguyên văn")
    documents: dict[str, SearchDocument] = Field(default_factory=dict, description="Danh mục tài liệu deduplicated")
    groups: list[ProvisionGroup[SearchProvision]] = Field(default_factory=list, description="Các nhóm kết quả theo ngữ cảnh")
    verbatim_total: int = Field(default=0, ge=0, description="Tổng số lần xuất hiện của pattern trong kho")
    verbatim_truncated: bool = Field(default=False, description="True nếu số lượng verbatim vượt quá giới hạn lấy về")
    confidence: str = Field(default="high", description="Mức độ tin cậy của kết quả: 'high', 'low', hoặc 'none'")


class UnifiedHierarchyResult(BaseModel):
    """Kết quả duyệt cây phân cấp tài liệu gom nhóm theo ngữ cảnh và thứ tự đọc."""

    model_config = ConfigDict(extra="forbid")

    anchor_path: str = Field(..., description="Đường dẫn LTree của nút mốc duyệt")
    direction: HierarchicalDirection = Field(..., description="Hướng duyệt đã thực hiện")
    documents: dict[str, SearchDocument] = Field(default_factory=dict, description="Danh mục tài liệu deduplicated")
    groups: list[ProvisionGroup[ProvisionText]] = Field(default_factory=list, description="Các nhóm provision theo thứ tự đọc")
    total: int = Field(default=0, ge=0, description="Tổng số nodes/chunks thỏa mãn hướng duyệt")
    truncated: bool = Field(default=False, description="True nếu tổng số nodes vượt quá limit an toàn")


class GraphLink(BaseModel):
    """Một liên kết trích dẫn trên đồ thị tri thức và các provisions dẫn tới."""

    model_config = ConfigDict(extra="forbid")

    from_path: str = Field(..., description="Đường dẫn LTree của chunk xuất phát")
    direction: GraphDirection = Field(..., description="Hướng duyệt: 'OUTGOING', 'INCOMING', hoặc 'BOTH'")
    relation_type: str = Field(..., description="Loại quan hệ tri thức")
    citation_text: str = Field(..., description="Đoạn văn trích dẫn chứng cứ")
    depth: int = Field(..., ge=1, description="Độ sâu bước nhảy")
    total: int = Field(default=0, ge=0, description="Tổng số provisions liên kết này dẫn tới")
    truncated: bool = Field(default=False, description="True nếu số provisions vượt quá quota limit_per_link")
    groups: list[ProvisionGroup[ProvisionText]] = Field(default_factory=list, description="Các provisions gom nhóm theo ngữ cảnh")


class UnifiedGraphTraverseResult(BaseModel):
    """Kết quả duyệt đồ thị tri thức đa tầng gom nhóm theo bằng chứng trích dẫn."""

    model_config = ConfigDict(extra="forbid")

    source_path: str = Field(..., description="Đường dẫn LTree của nút gốc bắt đầu duyệt")
    documents: dict[str, SearchDocument] = Field(default_factory=dict, description="Danh mục tài liệu deduplicated")
    links: list[GraphLink] = Field(default_factory=list, description="Danh sách các liên kết trích dẫn và các nút đích")


def group_in_reading_order(
    items: list[tuple[str, str, ProvisionText]],
) -> list[ProvisionGroup[ProvisionText]]:
    """Gom nhóm các provisions liên tiếp có chung (doc_slug, context) theo đúng thứ tự đọc."""
    groups: list[ProvisionGroup[ProvisionText]] = []
    for doc_slug, context, provision in items:
        if not groups or (groups[-1].doc_slug, groups[-1].context) != (doc_slug, context):
            groups.append(ProvisionGroup[ProvisionText](doc_slug=doc_slug, context=context, provisions=[]))
        groups[-1].provisions.append(provision)
    return groups


def group_ranked(
    matches: list[tuple[SearchFoundIn, str, str, ProvisionText]],
) -> list[ProvisionGroup[SearchProvision]]:
    """Gom nhóm các kết quả tìm kiếm đã xếp hạng toàn cục: nhóm xuất hiện theo thứ hạng provision tốt nhất;
    provisions bên trong mỗi nhóm được sắp xếp theo thứ tự đọc (start_line, path)."""
    groups_dict: dict[tuple[str, str], ProvisionGroup[SearchProvision]] = {}
    for rank, (found_in, doc_slug, context, prov) in enumerate(matches, start=1):
        key = (doc_slug, context)
        if key not in groups_dict:
            groups_dict[key] = ProvisionGroup[SearchProvision](doc_slug=doc_slug, context=context, provisions=[])
        search_prov = SearchProvision(
            path=prov.path,
            text=prov.text,
            start_line=prov.start_line,
            end_line=prov.end_line,
            metadata=prov.metadata,
            found_in=found_in,
            rank=rank,
        )
        groups_dict[key].provisions.append(search_prov)

    result_groups = list(groups_dict.values())
    for g in result_groups:
        g.provisions.sort(key=lambda p: (p.start_line, p.path))
    return result_groups


def clean_node_metadata(raw_meta: dict[str, object]) -> dict[str, object]:
    """Strips breadcrumb duplication (ancestor_titles) from chunk metadata."""
    meta = dict(raw_meta)
    meta.pop("ancestor_titles", None)
    return meta


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
    citation_text: str = Field(..., description="Trích dẫn nguyên văn chứng thực quan hệ")

    @field_validator("edge_id", "source_chunk_id", "target_chunk_id", mode="before")
    @classmethod
    def _coerce_uuid(cls, v: object) -> UUID:
        return v if isinstance(v, UUID) else UUID(str(v))


class RawDocumentSliceResult(BaseModel):
    """Container payload for MCP get_raw tool returning raw document slice."""

    model_config = ConfigDict(extra="ignore")

    doc_slug: str = Field(..., description="Mã định danh doc_slug chuẩn của tài liệu")
    title: str = Field(..., description="Tiêu đề tài liệu")
    start_line: int = Field(..., ge=1, description="Dòng bắt đầu thực tế (1-indexed)")
    end_line: int = Field(..., ge=1, description="Dòng kết thúc thực tế (1-indexed)")
    total_lines: int = Field(..., ge=0, description="Tổng số dòng trong tài liệu gốc")
    raw_text: str = Field(..., description="Nội dung văn bản gốc cắt theo phạm vi dòng yêu cầu")
