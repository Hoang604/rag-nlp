from __future__ import annotations

import datetime

import asyncpg
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from rag_eval.db.connection import check_db_health
from rag_eval.exceptions import CorpusDomainError
from rag_eval.ingestion.staging import (
    StagingChunkDelta,
    StagingEdge,
    StagingManager,
)
from rag_eval.ingestion.staging.models import ChunkReviewStatus
from rag_eval.ingestion.staging.session import StagingDocumentSession
from rag_eval.mcp.tools import CorpusMCPTools
from rag_eval.schemas import SearchHitDTO
from rag_eval.web.schemas import (
    BatchPatchRequest,
    BatchPatchResponse,
    CorpusDocumentResponse,
    CreateEdgeRequest,
    CreateSessionRequest,
    DocumentTreeResponse,
    FinalizeChunksRequest,
    FinalizeChunksResponse,
    GenericSuccessResponse,
    HealthResponse,
    PreFlightValidationResponse,
    PromoteSessionRequest,
    PromotionResultResponse,
    RawTextResponse,
    ReopenSessionRequest,
    ReparentSubtreeRequest,
    ReparentSubtreeResponse,
    ReplayVerificationResponse,
    SearchHitResponse,
    SearchRequest,
    SearchResponse,
    SessionDiffResponse,
    StagingEdgeResponse,
    StagingSessionDetailResponse,
    StagingSessionSummaryResponse,
    StatusTransitionRequest,
    WALRecordResponse,
)
from rag_eval.web.services import (
    DiffCalculator,
    HumanPromotionEngine,
    PreFlightValidator,
    TreeHierarchyBuilder,
    natural_path_key,
)

router = APIRouter(tags=["Corpus Staging Reviewer"])


def _get_staging_manager(request: Request) -> StagingManager:
    """Helper to retrieve configured StagingManager instance from app state or fallback."""
    mgr = getattr(request.app.state, "staging_manager", None)
    if isinstance(mgr, StagingManager):
        return mgr
    return StagingManager()


def _get_db_pool(request: Request) -> asyncpg.Pool | None:
    """Helper to retrieve active db pool from app state if configured."""
    pool = getattr(request.app.state, "pool", None)
    if isinstance(pool, asyncpg.Pool):
        return pool
    return None


async def _load_session_with_hydration(
    request: Request, doc_slug: str
) -> StagingDocumentSession:
    mgr = _get_staging_manager(request)
    pool = _get_db_pool(request)
    return await mgr.load_or_hydrate_session(doc_slug=doc_slug, pool=pool)


def _get_search_tools(request: Request) -> CorpusMCPTools:
    """Builds the retrieval tools once and keeps them on app state."""
    cached = getattr(request.app.state, "search_tools", None)
    if isinstance(cached, CorpusMCPTools):
        return cached

    from rag_eval.mcp.tools import SentenceTransformerQueryEmbedder
    from rag_eval.retrieval.reranker import CrossEncoderReranker

    tools = CorpusMCPTools.build(
        pool=_get_db_pool(request),
        embedding_engine=SentenceTransformerQueryEmbedder(),
        reranker=CrossEncoderReranker(),
    )
    request.app.state.search_tools = tools
    return tools


def _to_hit_responses(hits: list[SearchHitDTO]) -> list[SearchHitResponse]:
    """Shapes engine hits for the wire, once, for every endpoint that returns them."""
    responses: list[SearchHitResponse] = []
    for rank, hit in enumerate(hits, start=1):
        responses.append(
            SearchHitResponse(
                rank=rank,
                doc_slug=hit.doc_slug,
                doc_title=hit.doc_title,
                path=hit.path,
                verbatim_text=hit.verbatim_text,
                contextualized_text=hit.contextualized_text,
                score=hit.score,
                dense_similarity=hit.dense_similarity,
                keyword_matched=(hit.sparse_rank is not None and hit.sparse_rank < 999),
                rerank_score=hit.rerank_score,
                is_table=bool(hit.metadata.get("is_table")),
                table_summary=str(hit.metadata["table_summary"]) if hit.metadata.get("table_summary") else None,
            )
        )
    return responses


@router.post("/search", response_model=SearchResponse)
async def search_corpus(request: Request, payload: SearchRequest) -> SearchResponse:
    import time

    if _get_db_pool(request) is None:
        raise HTTPException(status_code=503, detail="Database is not connected.")

    tools = _get_search_tools(request)
    started = time.perf_counter()
    try:
        result = await tools.hybrid_search(
            query=payload.query,
            limit=payload.limit,
            rerank=payload.rerank,
            doc_slugs=payload.doc_slugs or None,
        )
    except CorpusDomainError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    elapsed = (time.perf_counter() - started) * 1000.0

    hits = _to_hit_responses(result.hits)

    return SearchResponse(
        query=payload.query,
        elapsed_ms=round(elapsed, 1),
        confidence=result.confidence,
        hits=hits,
    )


@router.get("/documents", response_model=list[CorpusDocumentResponse])
async def list_corpus_documents(request: Request) -> list[CorpusDocumentResponse]:
    """The promoted corpus, for scoping a query to chosen documents."""
    pool = _get_db_pool(request)
    if pool is None:
        raise HTTPException(status_code=503, detail="Database is not connected.")

    today = datetime.datetime.now(datetime.UTC).date()
    from rag_eval.db.repositories import CorpusRepository

    corpus_repo = CorpusRepository(pool)
    stats_list = await corpus_repo.documents.list_with_stats()
    return [
        CorpusDocumentResponse(
            doc_slug=r.doc_slug,
            title=r.title,
            valid_from=str(r.valid_from) if r.valid_from else None,
            valid_to=(
                str(r.valid_to) if r.valid_to else None
            ),
            in_force=(
                (r.valid_from is None or r.valid_from <= today)
                and (r.valid_to is None or r.valid_to > today)
            ),
            chunk_count=r.chunk_count,
        )
        for r in stats_list
    ]


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request) -> HealthResponse:
    """Health check endpoint probing database connectivity and service availability."""
    pool = _get_db_pool(request)
    is_healthy = await check_db_health(pool=pool)
    db_status = "CONNECTED" if is_healthy else "UNAVAILABLE"
    return HealthResponse(
        status="OK",
        database=db_status,
        timestamp=datetime.datetime.now(datetime.UTC).isoformat(),
    )


@router.get("/staging", response_model=list[StagingSessionSummaryResponse])
async def list_staging_sessions(
    request: Request,
) -> list[StagingSessionSummaryResponse]:
    """Lists summary cards for all discovered staging sessions in the staging directory."""
    mgr = _get_staging_manager(request)
    summaries = mgr.list_sessions()
    return [
        StagingSessionSummaryResponse(
            doc_slug=s.doc_slug,
            title=s.title,
            status=s.status,
            total_chunks=s.total_chunks,
            total_edges=s.total_edges,
            valid_from=s.valid_from,
            valid_to=s.valid_to,
            created_at=s.created_at,
            updated_at=s.updated_at,
            committed_at=s.committed_at,
            promoted_at=s.promoted_at,
        )
        for s in summaries
    ]


@router.post("/staging/raw", response_model=StagingSessionDetailResponse)
async def create_staging_session_from_raw(
    request: Request, payload: CreateSessionRequest
) -> StagingSessionDetailResponse:
    """Creates a fresh staging session by parsing raw text."""
    mgr = _get_staging_manager(request)
    doc_meta = (payload.metadata.model_dump() if isinstance(payload.metadata, BaseModel) else payload.metadata)
    session = mgr.create_session_from_raw(
        doc_slug=payload.doc_slug,
        title=payload.title,
        raw_text=payload.raw_text,
        valid_from=payload.valid_from,
        valid_to=payload.valid_to,
        metadata=doc_meta,
    )
    return StagingSessionDetailResponse.model_validate(session.model_dump())


# Sub-resource endpoints registered BEFORE root /staging/{doc_slug} to prevent route shadowing


@router.get("/staging/{doc_slug}/wal", response_model=list[WALRecordResponse])
async def get_staging_wal_journal(request: Request, doc_slug: str) -> list[WALRecordResponse]:
    """Returns complete ordered WAL journal entries for the document session."""
    mgr = _get_staging_manager(request)
    records = mgr.get_wal_records(doc_slug)
    return [WALRecordResponse.model_validate(r.model_dump()) for r in records]


@router.post("/staging/{doc_slug}/replay", response_model=ReplayVerificationResponse)
async def replay_staging_session(
    request: Request, doc_slug: str, up_to_lsn: int | None = Query(None)
) -> ReplayVerificationResponse:
    """Deterministically replays the staging session from genesis baseline to specified LSN."""
    mgr = _get_staging_manager(request)
    session, applied_lsn = mgr.replay_session(doc_slug, up_to_lsn=up_to_lsn)
    return ReplayVerificationResponse(
        status="SUCCESS",
        doc_slug=doc_slug,
        applied_lsn=applied_lsn,
        is_deterministic=True,
        total_chunks=len(session.chunks),
        total_edges=len(session.edges),
        message=f"Successfully replayed {applied_lsn + 1} WAL records from genesis baseline.",
    )


@router.post("/staging/{doc_slug}/reparent", response_model=ReparentSubtreeResponse)
async def reparent_staging_subtree(
    request: Request, doc_slug: str, payload: ReparentSubtreeRequest
) -> ReparentSubtreeResponse:
    """Migrates an entire subtree to a new parent prefix in the staging session."""
    mgr = _get_staging_manager(request)
    await _load_session_with_hydration(request, doc_slug)
    session, result = mgr.reparent_node(
        doc_slug=doc_slug,
        old_path_prefix=payload.old_path_prefix,
        new_path_prefix=payload.new_path_prefix,
        dry_run=payload.dry_run,
        actor=payload.actor,
    )
    return ReparentSubtreeResponse(
        status="SUCCESS",
        doc_slug=doc_slug,
        dry_run=result.dry_run,
        affected_chunks_count=result.affected_chunks_count,
        affected_edges_count=result.affected_edges_count,
        old_path_prefix=result.old_path_prefix,
        new_path_prefix=result.new_path_prefix,
        total_chunks=len(session.chunks),
    )


@router.get("/staging/{doc_slug}/tree", response_model=DocumentTreeResponse)
async def get_document_tree_hierarchy(
    request: Request, doc_slug: str
) -> DocumentTreeResponse:
    """Returns nested document hierarchy tree formatted for the interactive canvas visualizer."""
    session = await _load_session_with_hydration(request, doc_slug)
    builder = TreeHierarchyBuilder()
    return builder.build_tree(session)


@router.post("/staging/{doc_slug}/patch", response_model=BatchPatchResponse)
async def batch_patch_chunks(
    request: Request, doc_slug: str, payload: BatchPatchRequest
) -> BatchPatchResponse:
    """Applies surgical in-place chunk updates and removals to the staging session."""
    mgr = _get_staging_manager(request)
    await _load_session_with_hydration(request, doc_slug)
    updated_stg_deltas = [
        StagingChunkDelta(
            path=c.path,
            verbatim_text=c.verbatim_text,
            contextualized_text=c.contextualized_text,
            start_line=c.start_line,
            end_line=c.end_line,
            metadata=c.metadata,
            review_status=c.review_status,
        )
        for c in payload.updated_chunks
    ]
    session = mgr.patch_chunks(
        doc_slug=doc_slug,
        updated_chunks=updated_stg_deltas,
        removed_paths=payload.removed_paths,
    )
    return BatchPatchResponse(
        status="SUCCESS",
        doc_slug=doc_slug,
        updated_count=len(payload.updated_chunks),
        removed_count=len(payload.removed_paths),
        total_chunks=len(session.chunks),
    )


@router.post("/staging/{doc_slug}/finalize", response_model=FinalizeChunksResponse)
async def finalize_staging_chunks(
    request: Request, doc_slug: str, payload: FinalizeChunksRequest
) -> FinalizeChunksResponse:
    """Marks specified chunk paths as finalized in the staging session."""
    mgr = _get_staging_manager(request)
    await _load_session_with_hydration(request, doc_slug)
    session, count, _ = mgr.finalize_chunks(
        doc_slug=doc_slug, paths=payload.paths, actor="HUMAN:reviewer"
    )
    pending_rem = sum(
        1
        for c in session.chunks
        if c.review_status == ChunkReviewStatus.PENDING
    )
    return FinalizeChunksResponse(
        status="SUCCESS",
        doc_slug=doc_slug,
        finalized_count=count,
        pending_remaining=pending_rem,
    )


@router.get("/staging/{doc_slug}/edges", response_model=list[StagingEdgeResponse])
async def list_staging_edges(
    request: Request, doc_slug: str
) -> list[StagingEdgeResponse]:
    """Lists all relational graph edges attached to the staging session."""
    session = await _load_session_with_hydration(request, doc_slug)
    return [
        StagingEdgeResponse(
            source_path=e.source_path,
            target_path=e.target_path,
            relation_type=e.relation_type.value if hasattr(e.relation_type, "value") else str(e.relation_type),
        )
        for e in session.edges
    ]


@router.post("/staging/{doc_slug}/edges", response_model=StagingSessionDetailResponse)
async def add_staging_edges(
    request: Request,
    doc_slug: str,
    payload: list[CreateEdgeRequest] | CreateEdgeRequest,
) -> StagingSessionDetailResponse:
    """Adds or updates directed relationship edges in the staging session."""
    mgr = _get_staging_manager(request)
    await _load_session_with_hydration(request, doc_slug)
    items = [payload] if isinstance(payload, CreateEdgeRequest) else payload
    edges = [
        StagingEdge(
            source_path=item.source_path,
            target_path=item.target_path,
            relation_type=item.relation_type,
        )
        for item in items
    ]
    session = mgr.add_edges(doc_slug=doc_slug, edges=edges)
    return StagingSessionDetailResponse.model_validate(session.model_dump())


@router.delete("/staging/{doc_slug}/edges", response_model=GenericSuccessResponse)
async def delete_staging_edge(
    request: Request,
    doc_slug: str,
    source_path: str = Query(..., description="LTree path of source chunk"),
    relation_type: str | None = Query(None, description="Relation type code"),
    target_path: str | None = Query(None, description="LTree path of target chunk"),
    clear_all_targets: bool = Query(False, description="Clear all targets from source_path"),
) -> GenericSuccessResponse:
    """Removes a relational graph edge matching source, target, and relation type via query parameters."""
    mgr = _get_staging_manager(request)
    await _load_session_with_hydration(request, doc_slug)

    if not source_path:
        raise HTTPException(
            status_code=400,
            detail="Must provide at least source_path to delete edge.",
        )
    if not target_path and not clear_all_targets:
        raise HTTPException(
            status_code=400,
            detail="Must provide target_path to identify the edge, or set clear_all_targets=True.",
        )

    mgr.remove_edge(
        doc_slug=doc_slug,
        source_path=source_path,
        target_path=target_path,
        relation_type=relation_type,
        clear_all_targets=clear_all_targets,
        actor="HUMAN:reviewer",
    )
    return GenericSuccessResponse(
        status="SUCCESS",
        message=f"Edge '{source_path}' -> '{target_path or 'all'}' removed successfully.",
        doc_slug=doc_slug,
    )


@router.post("/staging/{doc_slug}/status", response_model=StagingSessionDetailResponse)
async def transition_staging_status(
    request: Request, doc_slug: str, payload: StatusTransitionRequest
) -> StagingSessionDetailResponse:
    """Transitions staging session lifecycle status (e.g. DRAFT -> APPROVED)."""
    mgr = _get_staging_manager(request)
    session = mgr.update_session_status(
        doc_slug=doc_slug,
        status=payload.status,
        actor=payload.actor,
        description=payload.description,
    )
    return StagingSessionDetailResponse.model_validate(session.model_dump())


@router.post("/staging/{doc_slug}/reopen", response_model=StagingSessionDetailResponse)
async def reopen_staging_session(
    request: Request, doc_slug: str, payload: ReopenSessionRequest | None = None
) -> StagingSessionDetailResponse:
    """Reopens a PROMOTED staging session into AMENDMENT status, hydrating from DB if absent."""
    mgr = _get_staging_manager(request)
    await _load_session_with_hydration(request, doc_slug)

    actor = payload.actor if payload else "HUMAN:reviewer"
    reason = payload.reason if payload else "Reopened for amendment"
    session = mgr.reopen_session_for_amendment(
        doc_slug=doc_slug, actor=actor, reason=reason
    )
    return StagingSessionDetailResponse.model_validate(session.model_dump())


@router.get("/staging/{doc_slug}/diff", response_model=SessionDiffResponse)
async def get_session_version_diff(
    request: Request, doc_slug: str
) -> SessionDiffResponse:
    """Returns version mutation differences between initial AST baseline and current state."""
    session = await _load_session_with_hydration(request, doc_slug)
    calculator = DiffCalculator()
    return calculator.compute_diff(session)


@router.get("/staging/{doc_slug}/raw", response_model=RawTextResponse)
async def get_raw_document_text(request: Request, doc_slug: str) -> RawTextResponse:
    """Returns raw source text for dual-view split screen visualizer."""
    session = await _load_session_with_hydration(request, doc_slug)
    return RawTextResponse(
        doc_slug=session.doc_slug,
        title=session.title,
        raw_text=session.raw_text or "",
        chunks_count=len(session.chunks),
    )


@router.get("/staging/{doc_slug}/validate", response_model=PreFlightValidationResponse)
@router.post("/staging/{doc_slug}/validate", response_model=PreFlightValidationResponse)
async def run_preflight_validation(
    request: Request, doc_slug: str
) -> PreFlightValidationResponse:
    """Runs automated pre-flight integrity verification checklist before promotion."""
    session = await _load_session_with_hydration(request, doc_slug)
    validator = PreFlightValidator()
    return validator.validate(session)


@router.post("/staging/{doc_slug}/promote", response_model=PromotionResultResponse)
async def execute_human_promotion(
    request: Request, doc_slug: str, payload: PromoteSessionRequest | None = None
) -> PromotionResultResponse:
    """Triggers atomic Human Promotion of approved staging session into PostgreSQL production tables."""
    mgr = _get_staging_manager(request)
    pool = _get_db_pool(request)
    engine = HumanPromotionEngine(staging_manager=mgr)

    reviewer_notes = payload.reviewer_notes if payload else None
    compute_emb = payload.compute_embeddings if payload else True

    return await engine.promote_session(
        doc_slug=doc_slug,
        reviewer_notes=reviewer_notes,
        compute_embeddings=compute_emb,
        pool=pool,
    )


@router.get("/staging/{doc_slug}", response_model=StagingSessionDetailResponse)
async def get_staging_session_detail(
    request: Request, doc_slug: str
) -> StagingSessionDetailResponse:
    """Retrieves full detail, chunks, edges, and audit history for a staging document session."""
    session = await _load_session_with_hydration(request, doc_slug)
    data = session.model_dump(mode="json")
    if "chunks" in data and isinstance(data["chunks"], list):
        data["chunks"].sort(key=lambda c: natural_path_key(c.get("path", "")))
    return StagingSessionDetailResponse.model_validate(data)


@router.delete("/staging/{doc_slug}", response_model=GenericSuccessResponse)
async def delete_staging_session(
    request: Request, doc_slug: str
) -> GenericSuccessResponse:
    """Deletes / discards a staging session file from disk."""
    mgr = _get_staging_manager(request)
    deleted = mgr.delete_session(doc_slug)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Staging session for '{doc_slug}' not found."
        )
    return GenericSuccessResponse(
        status="SUCCESS",
        message=f"Staging session for '{doc_slug}' deleted successfully.",
        doc_slug=doc_slug,
    )
