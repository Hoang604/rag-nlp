from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from rag_eval.schemas import (
    EdgeKey,
    EdgeProposal,
    ProvisionGroup,
    RelationType,
    SearchDocument,
    SearchProvision,
)


class CurateEdgesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    add_edges: list[EdgeProposal] | None = Field(default=None, description="Danh sách các cạnh đề xuất thêm")
    remove_edges: list[EdgeKey] | None = Field(default=None, description="Danh sách các cạnh yêu cầu gỡ bỏ")
    reason: str = Field(..., min_length=1, description="Lý do / ngữ cảnh phục vụ nhật ký kiểm toán")


class GraphVisualizerNode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str
    label: str
    node_type: str
    in_degree: int
    out_degree: int


class GraphVisualizerEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_path: str
    target_path: str
    relation_type: RelationType
    rationale: str | None = None


class GraphVisualizerResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    doc_slug: str
    nodes: list[GraphVisualizerNode]
    edges: list[GraphVisualizerEdge]


class DocumentTreeNodeResponse(BaseModel):
    """Node representation in the document hierarchy tree canvas."""

    model_config = ConfigDict(extra="ignore")

    path: str = Field(..., description="Hierarchical dot-separated ltree path")
    label: str = Field(..., description="Human-readable node label")
    node_type: str = Field(
        default="SECTION",
        description="Node division type: DOCUMENT | SECTION | PARAGRAPH | TABLE | CODE | LIST",
    )
    verbatim_text: str = Field("", description="Raw verbatim text")
    contextualized_text: str = Field("", description="Synthesized contextual text")
    start_line: int = Field(default=1, ge=1, description="1-indexed starting line in raw text")
    end_line: int = Field(default=1, ge=1, description="1-indexed ending line in raw text")
    metadata: dict[str, object] = Field(
        default_factory=dict, description="Node semantic metadata"
    )
    children: list[DocumentTreeNodeResponse] = Field(
        default_factory=list, description="Child nodes in hierarchy"
    )


class DocumentTreeResponse(BaseModel):
    """Full nested tree hierarchy for interactive visualizer canvas."""

    model_config = ConfigDict(extra="ignore")

    doc_slug: str = Field(..., description="Document slug")
    title: str = Field(..., description="Document title")
    total_nodes: int = Field(..., description="Total nodes count in hierarchy")
    total_chunks: int = Field(default=0, description="Total chunks count in document")
    root: DocumentTreeNodeResponse = Field(..., description="Root document node")


class HealthResponse(BaseModel):
    """System health probe response."""

    model_config = ConfigDict(extra="ignore")

    status: str = Field("OK", description="Service health status")
    database: str = Field("CONNECTED", description="PostgreSQL connection health")
    timestamp: str = Field(..., description="ISO 8601 timestamp")


class RawTextResponse(BaseModel):
    """Raw text payload for dual-view split screen."""

    model_config = ConfigDict(extra="ignore")

    doc_slug: str = Field(..., description="Document slug")
    title: str = Field(..., description="Document title")
    raw_text: str = Field(..., description="Full raw text")
    chunks_count: int = Field(..., description="Total parsed chunks count")


class SearchRequest(BaseModel):
    """A dual-channel Venn retrieval query issued from the reviewer UI."""

    model_config = ConfigDict(extra="ignore")

    query: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Ngữ cảnh / ý niệm cần tìm kiếm (dense vector + sparse FTS)",
    )
    pattern: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Từ khóa neo cứng, mã số hiệu cần khớp chính xác (verbatim grep)",
    )
    is_regex: bool = Field(default=False, description="Bật chế độ đánh giá biểu thức chính quy POSIX")
    case_sensitive: bool = Field(default=False, description="Phân biệt chữ hoa / chữ thường")
    order_by_reading_order: bool = Field(
        default=False,
        description="Sắp xếp kết quả verbatim theo thứ tự đọc trong tài liệu thay vì điểm tương đồng",
    )
    limit: int = Field(default=10, ge=1, le=50, description="Số lượng kết quả tối đa cho mỗi nhánh tìm kiếm")
    rerank: bool | None = Field(default=None, description="Bật hoặc tắt bước xếp hạng lại kết quả")
    doc_slugs: list[str] = Field(default_factory=list, max_length=32, description="Giới hạn phạm vi doc_slug")
    path_prefix: str | None = Field(default=None, description="Giới hạn phân cấp LTree")


class SearchResponse(BaseModel):
    """Factored search response returning deduplicated documents and reading-order context groups."""

    model_config = ConfigDict(extra="ignore")

    query: str
    pattern: str
    elapsed_ms: float
    confidence: str = "high"
    documents: dict[str, SearchDocument] = Field(default_factory=dict)
    groups: list[ProvisionGroup[SearchProvision]] = Field(default_factory=list)
    verbatim_total: int = 0
    verbatim_truncated: bool = False


class CorpusDocumentResponse(BaseModel):
    """One document in PostgreSQL, for the retrieval scope selector and dashboard catalog."""

    model_config = ConfigDict(extra="ignore")

    doc_slug: str
    title: str
    chunk_count: int


class GraphTraverseRequest(BaseModel):
    """Request payload to traverse the relational graph starting from a node."""

    model_config = ConfigDict(extra="ignore")

    source_path: str = Field(..., description="LTree path of source chunk")
    nav_direction: str = Field(
        default="OUTGOING", description="Direction: OUTGOING | INCOMING | BOTH"
    )
    depth_limit: int = Field(default=2, ge=1, le=5, description="Max traversal depth")
    filter_relations: list[str] | None = Field(
        default=None, description="Optional relation type filters"
    )
    limit: int = Field(default=20, ge=1, le=100, description="Max traversed steps")


class GraphTraversalStepResponse(BaseModel):
    """A single traversed edge step in knowledge graph navigation."""

    model_config = ConfigDict(extra="ignore")

    edge_id: str
    source_chunk_id: str
    target_chunk_id: str
    relation_type: str
    depth: int
    source_path: str
    target_path: str
    target_text: str
    target_contextualized_text: str
    target_doc_slug: str
    target_start_line: int
    target_end_line: int
    rationale: str | None = None
    citation_text: str = Field(..., description="Trích dẫn nguyên văn chứng thực quan hệ")




class RelationTypeCatalogResponse(BaseModel):
    """A catalog item of valid relation types from database."""

    model_config = ConfigDict(extra="ignore")

    code: str
    description: str
    is_symmetric: bool
