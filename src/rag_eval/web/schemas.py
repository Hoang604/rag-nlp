from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from rag_eval.schemas import RelationType


class LinkChunksInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_path: str = Field(..., description="Đường dẫn phân cấp LTree của chunk nguồn")
    target_path: str = Field(..., description="Đường dẫn phân cấp LTree của chunk đích")
    relation_type: RelationType = Field(..., description="Mã quan hệ hợp lệ trong danh mục hệ thống")
    rationale: str | None = Field(default=None, description="Lý do / bằng chứng luận cứ kết nối hai chunk")


class LinkChunksResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str = Field("SUCCESS", description="Trạng thái thao tác")
    source_path: str
    target_path: str
    relation_type: RelationType
    created: bool
    rationale: str | None = None


class UnlinkChunksInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_path: str = Field(..., description="Đường dẫn phân cấp LTree của chunk nguồn")
    target_path: str = Field(..., description="Đường dẫn phân cấp LTree của chunk đích")
    relation_type: RelationType | None = Field(
        default=None,
        description="Mã loại quan hệ cần gỡ (None khi gỡ mọi quan hệ giữa 2 chunk)",
    )


class UnlinkChunksResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str = Field("SUCCESS", description="Trạng thái thao tác")
    source_path: str
    target_path: str
    removed_edges_count: int


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
    """A retrieval query issued from the reviewer UI."""

    model_config = ConfigDict(extra="ignore")

    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=5, ge=1, le=20)
    rerank: bool | None = None
    doc_slugs: list[str] = Field(default_factory=list, max_length=32)
    path_prefix: str | None = Field(default=None, description="Optional ltree path prefix filter")


class SearchHitResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    rank: int
    doc_slug: str
    doc_title: str
    path: str
    verbatim_text: str
    contextualized_text: str
    score: float
    dense_similarity: float = 0.0
    keyword_matched: bool = True
    rerank_score: float | None = None
    is_table: bool = False
    table_summary: str | None = None


class SearchResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    query: str
    elapsed_ms: float
    confidence: str = "high"
    hits: list[SearchHitResponse]


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


class VerbatimGrepRequest(BaseModel):
    """Request payload for exact / trigram grep across production corpus."""

    model_config = ConfigDict(extra="ignore")

    pattern: str = Field(..., min_length=1, description="Text pattern to match")
    is_regex: bool = Field(default=False, description="Regex match enabled")
    case_sensitive: bool = Field(default=False, description="Case-sensitive matching")
    limit: int = Field(default=20, ge=1, le=100, description="Max matches")


class VerbatimGrepHitResponse(BaseModel):
    """A match hit from verbatim_grep stored procedure."""

    model_config = ConfigDict(extra="ignore")

    chunk_id: str
    doc_slug: str
    path: str
    start_line: int
    end_line: int
    char_offset: int
    match_snippet: str
    verbatim_text: str
    metadata: dict[str, object] = Field(default_factory=dict)


class VerbatimGrepResponse(BaseModel):
    """Response returned from verbatim grep search."""

    model_config = ConfigDict(extra="ignore")

    pattern: str
    is_regex: bool
    total_matches: int
    returned: int
    truncated: bool
    matches: list[VerbatimGrepHitResponse]


class RelationTypeCatalogResponse(BaseModel):
    """A catalog item of valid relation types from database."""

    model_config = ConfigDict(extra="ignore")

    code: str
    description: str
    is_symmetric: bool
