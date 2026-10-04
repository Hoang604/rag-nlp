from __future__ import annotations

import datetime

from pydantic import BaseModel, ConfigDict, Field

from rag_eval.ingestion.staging import (
    ChunkReviewStatus,
    StagingChunk,
    StagingEdge,
    StagingMutationRecord,
    StagingStatus,
)
from rag_eval.schemas import FinalizationState


class StagingSessionSummaryResponse(BaseModel):
    """Summary response for staging sessions discovery listing."""

    model_config = ConfigDict(extra="ignore")

    doc_slug: str = Field(..., description="Document slug identifier")
    title: str = Field(..., description="Document title")
    status: StagingStatus = Field(..., description="Current staging lifecycle status")
    total_chunks: int = Field(..., description="Total count of candidate chunks")
    total_edges: int = Field(..., description="Total count of relational graph edges")
    created_at: datetime.datetime = Field(..., description="Session creation timestamp")
    updated_at: datetime.datetime = Field(
        ..., description="Session last updated timestamp"
    )
    committed_at: datetime.datetime | None = Field(
        None, description="Agent commit timestamp"
    )
    promoted_at: datetime.datetime | None = Field(
        None, description="Human promotion timestamp"
    )


class StagingSessionDetailResponse(BaseModel):
    """Detailed response for a staging document session."""

    model_config = ConfigDict(extra="ignore")

    doc_slug: str = Field(..., description="Document slug identifier")
    title: str = Field(..., description="Document title")
    status: StagingStatus = Field(..., description="Current staging status")
    created_at: datetime.datetime = Field(..., description="Session creation timestamp")
    updated_at: datetime.datetime = Field(
        ..., description="Session last updated timestamp"
    )
    committed_at: datetime.datetime | None = Field(
        None, description="Agent commit timestamp"
    )
    promoted_at: datetime.datetime | None = Field(
        None, description="Human promotion timestamp"
    )
    raw_text: str | None = Field(None, description="Raw source text")
    metadata: dict[str, object] = Field(
        default_factory=dict, description="Document metadata"
    )
    chunks: list[StagingChunk] = Field(
        default_factory=list, description="Candidate chunks"
    )
    edges: list[StagingEdge] = Field(
        default_factory=list, description="Relational graph edges"
    )
    raw_ast_snapshot: list[dict[str, object]] | None = Field(
        None, description="Initial AST baseline snapshot"
    )
    raw_edge_snapshot: list[dict[str, object]] | None = Field(
        None, description="Initial graph edges baseline snapshot"
    )
    mutation_history: list[StagingMutationRecord] = Field(
        default_factory=list, description="Audit log of mutations"
    )


class CreateSessionRequest(BaseModel):
    """Request payload to create a new staging session from raw text."""

    model_config = ConfigDict(extra="ignore")

    doc_slug: str = Field(..., description="Unique document slug identifier")
    title: str = Field(..., description="Full document title")
    raw_text: str = Field(..., description="Raw text of document")
    metadata: dict[str, object] = Field(
        default_factory=dict, description="Dynamic document metadata"
    )


class DocumentTreeNodeResponse(BaseModel):
    """Node representation in the document hierarchy tree canvas."""

    model_config = ConfigDict(extra="ignore")

    path: str = Field(..., description="Hierarchical dot-separated ltree path")
    label: str = Field(..., description="Human-readable node label")
    node_type: str = Field(
        default="NODE",
        description="Node division type: DOCUMENT | NODE",
    )
    verbatim_text: str = Field("", description="Raw verbatim text")
    contextualized_text: str = Field("", description="Synthesized contextual text")
    start_line: int = Field(default=1, ge=1, description="1-indexed starting line in raw text")
    end_line: int = Field(default=1, ge=1, description="1-indexed ending line in raw text")
    metadata: dict[str, object] = Field(
        default_factory=dict, description="Node semantic metadata"
    )
    review_status: str = Field(
        default="PENDING", description="Review status of node ('PENDING' | 'REVIEWED')"
    )
    finalization_state: str | None = Field(
        default=None, description="Semantic finalization state of node"
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
    total_finalized: int = Field(default=0, description="Total finalized chunks count")
    total_pending: int = Field(default=0, description="Total pending chunks count")
    progress_percent: float = Field(default=0.0, description="Overall completion progress %")
    root: DocumentTreeNodeResponse = Field(..., description="Root document node")


class FinalizeChunksRequest(BaseModel):
    """Request payload to mark candidate chunks as finalized."""

    model_config = ConfigDict(extra="ignore")

    paths: list[str] = Field(..., min_length=1, description="List of chunk paths to finalize")


class FinalizeChunksResponse(BaseModel):
    """Response returned after finalizing chunks."""

    model_config = ConfigDict(extra="ignore")

    status: str = Field("SUCCESS", description="Operation status")
    doc_slug: str = Field(..., description="Document slug")
    finalized_count: int = Field(..., description="Number of chunks finalized")
    pending_remaining: int = Field(..., description="Remaining pending chunks in session")


class ChunkPatchItem(BaseModel):
    """Single chunk payload for surgical in-place patch supporting partial delta fields."""

    model_config = ConfigDict(extra="ignore")

    path: str = Field(..., description="Dot-separated ltree path")
    verbatim_text: str | None = Field(
        None, description="Raw verbatim text (optional for deltas)"
    )
    contextualized_text: str | None = Field(
        None, description="Synthesized contextual text (optional for deltas)"
    )
    start_line: int | None = Field(
        None, ge=1, description="Optional updated starting line number"
    )
    end_line: int | None = Field(
        None, ge=1, description="Optional updated ending line number"
    )
    metadata: dict[str, object] | None = Field(
        None, description="Dynamic chunk metadata to deep-merge (optional)"
    )
    review_status: ChunkReviewStatus | None = Field(
        None, description="Optional updated review status ('PENDING' | 'REVIEWED')"
    )
    finalization_state: FinalizationState | None = Field(
        None, description="Optional updated semantic finalization state"
    )


class BatchPatchRequest(BaseModel):
    """Request payload for batch updating and removing chunks."""

    model_config = ConfigDict(extra="ignore")

    updated_chunks: list[ChunkPatchItem] = Field(
        default_factory=list, description="List of chunks to add or update"
    )
    removed_paths: list[str] = Field(
        default_factory=list, description="List of chunk paths to delete"
    )


class BatchPatchResponse(BaseModel):
    """Response returned after applying a chunk batch patch."""

    model_config = ConfigDict(extra="ignore")

    status: str = Field("SUCCESS", description="Operation status")
    doc_slug: str = Field(..., description="Document slug")
    updated_count: int = Field(..., description="Number of chunks updated")
    removed_count: int = Field(..., description="Number of chunk paths removed")
    total_chunks: int = Field(..., description="Total remaining chunks in session")


class CreateEdgeRequest(BaseModel):
    """Request payload to create or update a relational graph edge."""

    model_config = ConfigDict(extra="ignore")

    source_path: str = Field(..., description="Source chunk ltree path")
    target_path: str = Field(..., description="Target chunk ltree path")
    relation_type: str = Field(..., description="Relation type enum string")
    anchor_text: str | None = Field(None, description="Verbatim text quote from source chunk")
    char_start: int | None = Field(None, description="Start character offset in source chunk text")
    char_end: int | None = Field(None, description="End character offset in source chunk text")


class DeleteEdgeRequest(BaseModel):
    """Request payload to delete a relational graph edge."""

    model_config = ConfigDict(extra="ignore")

    source_path: str = Field(..., description="Source chunk ltree path")
    target_path: str | None = Field(None, description="Target chunk ltree path")
    relation_type: str | None = Field(None, description="Relation type enum string")
    clear_all_targets: bool = Field(
        default=False,
        description="Clear all outgoing edges from source_path regardless of target",
    )


class StagingEdgeResponse(BaseModel):
    """Response model for a relational graph edge."""

    model_config = ConfigDict(extra="ignore")

    source_path: str = Field(..., description="Source chunk ltree path")
    target_path: str = Field(..., description="Target chunk ltree path")
    relation_type: str = Field(..., description="Relation type enum string")
    anchor_text: str | None = Field(None, description="Verbatim text quote from source chunk")
    char_start: int | None = Field(None, description="Start character offset in source chunk text")
    char_end: int | None = Field(None, description="End character offset in source chunk text")


class StatusTransitionRequest(BaseModel):
    """Request payload to transition staging session status."""

    model_config = ConfigDict(extra="ignore")

    status: StagingStatus = Field(..., description="Target staging lifecycle status")
    actor: str = Field(
        "HUMAN:reviewer", description="Actor initiating status transition"
    )
    description: str = Field("", description="Reason or notes for transition")


class ReopenSessionRequest(BaseModel):
    """Request payload to reopen a promoted staging session into AMENDMENT status."""

    model_config = ConfigDict(extra="ignore")

    actor: str = Field(
        "HUMAN:reviewer", description="Actor initiating reopening"
    )
    reason: str = Field("", description="Reason or notes for reopening")


class AuditDiffEntry(BaseModel):
    """Single item representing a detected mutation difference."""

    model_config = ConfigDict(extra="ignore")

    path: str = Field(..., description="Target chunk path")
    change_type: str = Field(..., description="'ADDED' | 'MODIFIED' | 'DELETED'")
    field_name: str | None = Field(None, description="Specific field changed")
    old_value: object | None = Field(None, description="Baseline / prior value")
    new_value: object | None = Field(None, description="Current / updated value")
    description: str = Field("", description="Human-readable summary of difference")


class SessionDiffResponse(BaseModel):
    """Response payload detailing version mutation differences."""

    model_config = ConfigDict(extra="ignore")

    doc_slug: str = Field(..., description="Document slug")
    total_changes: int = Field(..., description="Total count of diff entries")
    added_chunks: list[StagingChunk] = Field(
        default_factory=list, description="Chunks added since baseline parse"
    )
    modified_chunks: list[dict[str, object]] = Field(
        default_factory=list, description="Chunks modified since baseline parse"
    )
    deleted_chunks: list[dict[str, object]] = Field(
        default_factory=list, description="Chunks removed since baseline parse"
    )
    edge_diffs: list[dict[str, object]] = Field(
        default_factory=list, description="Relational graph edge differences"
    )
    diff_entries: list[AuditDiffEntry] = Field(
        default_factory=list, description="Detailed audit diff entries"
    )


class ValidationIssue(BaseModel):
    """Represents a discrete rule check violation."""

    model_config = ConfigDict(extra="ignore")

    rule: str = Field(..., description="Rule code identifier")
    severity: str = Field("ERROR", description="'ERROR' | 'WARNING'")
    path: str | None = Field(None, description="Affected chunk path or entity")
    message: str = Field(..., description="Human-readable violation description")
    blocking: bool = Field(True, description="Whether this issue blocks promotion")


class PreFlightValidationResponse(BaseModel):
    """Automated pre-flight integrity verification checklist results."""

    model_config = ConfigDict(extra="ignore")

    status: str = Field(..., description="'PASSED' | 'FAILED'")
    passed: bool = Field(..., description="True if all blocking checks passed")
    total_checks: int = Field(..., description="Total automated integrity checks run")
    issues: list[ValidationIssue] = Field(
        default_factory=list, description="List of detected validation issues"
    )
    summary: dict[str, object] = Field(
        default_factory=dict, description="Summary breakdown of check results"
    )


class PromoteSessionRequest(BaseModel):
    """Request payload to trigger human promotion to PostgreSQL."""

    model_config = ConfigDict(extra="ignore")

    reviewer_notes: str | None = Field(
        None, description="Optional reviewer audit notes"
    )
    compute_embeddings: bool = Field(
        True, description="Whether to compute 512-dim dense vector embeddings"
    )


class PromotionResultResponse(BaseModel):
    """Result of human promotion to PostgreSQL production tables."""

    model_config = ConfigDict(extra="ignore")

    status: str = Field("SUCCESS", description="'SUCCESS' | 'FAILED'")
    doc_slug: str = Field(..., description="Promoted document slug")
    document_id: str = Field(..., description="Authoritative PostgreSQL document UUID")
    chunks_promoted: int = Field(
        ..., description="Total chunks persisted into chunks table"
    )
    edges_promoted: int = Field(
        ..., description="Total edges persisted into graph_edges table"
    )
    promoted_at: str = Field(..., description="ISO 8601 promotion timestamp")
    message: str = Field("", description="Status message")


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


class GenericSuccessResponse(BaseModel):
    """Generic status response model."""

    model_config = ConfigDict(extra="ignore")

    status: str = Field("SUCCESS", description="Operation status")
    message: str = Field("", description="Operation message")
    doc_slug: str | None = Field(None, description="Affected document slug")


class ReparentSubtreeRequest(BaseModel):
    """Request payload to migrate a subtree to a new parent ltree prefix."""

    model_config = ConfigDict(extra="ignore")

    old_path_prefix: str = Field(..., description="Existing ltree path prefix to move")
    new_path_prefix: str = Field(..., description="New target ltree path prefix")
    dry_run: bool = Field(False, description="Whether to simulate mutation")
    actor: str = Field("HUMAN:reviewer", description="Action author")


class ReparentSubtreeResponse(BaseModel):
    """Response returned after subtree re-parenting."""

    model_config = ConfigDict(extra="ignore")

    status: str = "SUCCESS"
    doc_slug: str
    dry_run: bool
    affected_chunks_count: int
    affected_edges_count: int
    old_path_prefix: str
    new_path_prefix: str
    total_chunks: int


class SearchRequest(BaseModel):
    """A retrieval query issued from the reviewer UI."""

    model_config = ConfigDict(extra="ignore")

    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=5, ge=1, le=20)
    rerank: bool | None = None
    doc_slugs: list[str] = Field(default_factory=list, max_length=32)
    path_prefix: str | None = Field(default=None, description="Optional ltree path prefix filter")
    only_resolved: bool = Field(default=False, description="Filter for chunks with all references resolved")


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
    """One promoted document, for the retrieval scope selector."""

    model_config = ConfigDict(extra="ignore")

    doc_slug: str
    title: str
    chunk_count: int


class WALRecordResponse(BaseModel):
    """Response model for a single WAL record in the audit journal."""

    model_config = ConfigDict(extra="ignore")

    lsn: int = Field(..., description="Log Sequence Number")
    timestamp: datetime.datetime = Field(..., description="UTC timestamp of entry")
    actor: str = Field(..., description="Actor who executed the operation")
    op_type: str = Field(..., description="Operation type code")
    description: str = Field(..., description="Human-readable summary")
    payload: dict[str, object] = Field(default_factory=dict, description="Operation payload")
    checksum: str = Field(..., description="SHA-256 integrity checksum")


class ReplayVerificationResponse(BaseModel):
    """Result of running deterministic replay from genesis baseline."""

    model_config = ConfigDict(extra="ignore")

    status: str = Field("SUCCESS", description="Replay status")
    doc_slug: str = Field(..., description="Document slug")
    applied_lsn: int = Field(..., description="Highest LSN applied during replay")
    is_deterministic: bool = Field(True, description="Whether replay perfectly reproduced state")
    total_chunks: int = Field(..., description="Total chunks reconstructed")
    total_edges: int = Field(..., description="Total edges reconstructed")
    message: str = Field("", description="Verification message")


class StagingGrepRequest(BaseModel):
    """Request payload for in-memory regex grep across staging chunks."""

    model_config = ConfigDict(extra="ignore")

    pattern: str = Field(..., description="Query substring or regex pattern")
    is_regex: bool = Field(False, description="Whether pattern is a regular expression")
    case_sensitive: bool = Field(False, description="Case-sensitive matching")
    search_in: str = Field("ALL", description="Target field: ALL, VERBATIM, CONTEXT, PATH, METADATA")
    limit: int = Field(50, description="Max matches to return")


class StagingGrepHitResponse(BaseModel):
    """A matched hit from in-memory grep."""

    model_config = ConfigDict(extra="ignore")

    path: str
    field_matched: str
    match_snippet: str
    verbatim_text: str
    contextualized_text: str
    char_length: int
    metadata: dict[str, object] = Field(default_factory=dict)


class StagingGrepResponse(BaseModel):
    """Response containing grep results across staging session chunks."""

    model_config = ConfigDict(extra="ignore")

    doc_slug: str
    pattern: str
    total_hits: int
    hits: list[StagingGrepHitResponse]


class UnresolvedBacklogItemResponse(BaseModel):
    """An unresolved external reference in production or staging."""

    model_config = ConfigDict(extra="ignore")

    chunk_id: str
    source_path: str
    doc_slug: str
    doc_title: str
    target_path: str
    context_type: str


class UnresolvedBacklogResponse(BaseModel):
    """List of unresolved external references."""

    model_config = ConfigDict(extra="ignore")

    doc_slug: str | None
    total_unresolved: int
    items: list[UnresolvedBacklogItemResponse]


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


class GraphTraversalStepResponse(BaseModel):
    """A single traversed edge step in knowledge graph navigation."""

    model_config = ConfigDict(extra="ignore")

    edge_id: str
    source_chunk_id: str
    target_chunk_id: str
    relation_type: str
    depth: int
    target_path: str
    target_text: str


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

