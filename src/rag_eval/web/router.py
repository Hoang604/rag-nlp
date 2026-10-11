from __future__ import annotations

import datetime
import logging
import uuid

import asyncpg
from fastapi import APIRouter, HTTPException, Request

from rag_eval.db.connection import check_db_health
from rag_eval.db.repositories import CorpusRepository
from rag_eval.exceptions import CorpusDomainError
from rag_eval.retrieval.embedder import SentenceTransformerQueryEmbedder
from rag_eval.retrieval.engine import RetrievalEngine
from rag_eval.retrieval.enrichment import KnowledgeEnrichmentService
from rag_eval.retrieval.reranker import CrossEncoderReranker
from rag_eval.schemas import CurateEdgesResult, RelationType
from rag_eval.web.schemas import (
    CorpusDocumentResponse,
    CurateEdgesRequest,
    DocumentTreeResponse,
    GraphTraversalStepResponse,
    GraphTraverseRequest,
    GraphVisualizerEdge,
    GraphVisualizerNode,
    GraphVisualizerResponse,
    HealthResponse,
    RawTextResponse,
    RelationTypeCatalogResponse,
    SearchRequest,
    SearchResponse,
)
from rag_eval.web.services import (
    TreeHierarchyBuilder,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Corpus Knowledge Observatory"])


def _get_db_pool(request: Request) -> asyncpg.Pool | None:
    """Helper to retrieve active db pool from app state if configured."""
    pool = getattr(request.app.state, "pool", None)
    if isinstance(pool, asyncpg.Pool):
        return pool
    return None


def _get_retrieval_engine(request: Request) -> RetrievalEngine:
    """Retrieves or initializes the shared RetrievalEngine on app state."""
    engine = getattr(request.app.state, "retrieval_engine", None)
    if isinstance(engine, RetrievalEngine):
        return engine
    pool = _get_db_pool(request)
    if pool is None:
        raise HTTPException(status_code=503, detail="Database is not connected.")
    embedder = SentenceTransformerQueryEmbedder()
    reranker = CrossEncoderReranker()
    engine = RetrievalEngine(pool=pool, embedder=embedder, reranker=reranker)
    request.app.state.retrieval_engine = engine
    return engine





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


@router.get("/documents", response_model=list[CorpusDocumentResponse])
async def list_corpus_documents(request: Request) -> list[CorpusDocumentResponse]:
    """Corpus documents catalog in PostgreSQL production."""
    pool = _get_db_pool(request)
    if pool is None:
        raise HTTPException(status_code=503, detail="Database is not connected.")

    corpus_repo = CorpusRepository(pool)
    stats_list = await corpus_repo.documents.list_with_stats()
    return [
        CorpusDocumentResponse(
            doc_slug=r.doc_slug,
            title=r.title,
            chunk_count=r.chunk_count,
        )
        for r in stats_list
    ]


@router.get("/documents/{doc_slug}/tree", response_model=DocumentTreeResponse)
async def get_document_tree_hierarchy(
    request: Request, doc_slug: str
) -> DocumentTreeResponse:
    """Returns nested document hierarchy tree formatted for the interactive canvas visualizer."""
    pool = _get_db_pool(request)
    if pool is None:
        raise HTTPException(status_code=503, detail="Database is not connected.")

    repo = CorpusRepository(pool)
    doc = await repo.documents.get_by_slug(doc_slug)
    if doc is None:
        raise HTTPException(
            status_code=404, detail=f"Document '{doc_slug}' not found in database."
        )

    chunks = await repo.chunks.list_by_document(doc.id)
    builder = TreeHierarchyBuilder()
    return builder.build_tree(
        doc_slug=doc.doc_slug,
        title=doc.title,
        chunks=chunks,
        metadata=doc.metadata,
    )


@router.get("/documents/{doc_slug}/raw", response_model=RawTextResponse)
async def get_document_raw_text(
    request: Request, doc_slug: str
) -> RawTextResponse:
    """Returns raw source text for dual-view split screen visualizer."""
    pool = _get_db_pool(request)
    if pool is None:
        raise HTTPException(status_code=503, detail="Database is not connected.")

    repo = CorpusRepository(pool)
    doc = await repo.documents.get_by_slug(doc_slug)
    if doc is None:
        raise HTTPException(
            status_code=404, detail=f"Document '{doc_slug}' not found in database."
        )

    chunks = await repo.chunks.list_by_document(doc.id)
    return RawTextResponse(
        doc_slug=doc.doc_slug,
        title=doc.title,
        raw_text=doc.raw_text or "",
        chunks_count=len(chunks),
    )


@router.get("/documents/{doc_slug}/graph", response_model=GraphVisualizerResponse)
async def get_document_graph(
    request: Request, doc_slug: str
) -> GraphVisualizerResponse:
    """Returns nodes and edges of the document knowledge graph for visualizer."""
    pool = _get_db_pool(request)
    if pool is None:
        raise HTTPException(status_code=503, detail="Database is not connected.")

    repo = CorpusRepository(pool)
    doc = await repo.documents.get_by_slug(doc_slug)
    if doc is None:
        raise HTTPException(
            status_code=404, detail=f"Document '{doc_slug}' not found in database."
        )

    chunks = await repo.chunks.list_by_document(doc.id)
    if not chunks:
        return GraphVisualizerResponse(doc_slug=doc_slug, nodes=[], edges=[])

    chunk_ids = [c.id for c in chunks]
    id_to_chunk = {c.id: c for c in chunks}
    raw_edges = await repo.graph.list_edges_for_chunks(chunk_ids)

    missing_target_ids = [
        e.target_chunk_id
        for e in raw_edges
        if e.target_chunk_id not in id_to_chunk
    ]
    target_path_map: dict[uuid.UUID, str] = {}
    if missing_target_ids:
        async with repo.chunks._connection_scope() as conn:
            rows = await conn.fetch(
                "SELECT id, path FROM chunks WHERE id = ANY($1::uuid[]);",
                missing_target_ids,
            )
            for r in rows:
                target_path_map[uuid.UUID(str(r["id"]))] = str(r["path"])

    in_degrees: dict[str, int] = {c.path: 0 for c in chunks}
    out_degrees: dict[str, int] = {c.path: 0 for c in chunks}
    graph_edges: list[GraphVisualizerEdge] = []

    for e in raw_edges:
        src_chunk = id_to_chunk.get(e.source_chunk_id)
        if not src_chunk:
            continue
        tgt_path = (
            id_to_chunk[e.target_chunk_id].path
            if e.target_chunk_id in id_to_chunk
            else target_path_map.get(e.target_chunk_id)
        )
        if not tgt_path:
            continue
        rel_enum = RelationType(e.relation_type)

        graph_edges.append(
            GraphVisualizerEdge(
                source_path=src_chunk.path,
                target_path=tgt_path,
                relation_type=rel_enum,
                rationale=e.rationale,
            )
        )
        out_degrees[src_chunk.path] = out_degrees.get(src_chunk.path, 0) + 1
        if tgt_path in in_degrees:
            in_degrees[tgt_path] += 1

    nodes = [
        GraphVisualizerNode(
            path=c.path,
            label=str(
                c.metadata.get("heading_raw")
                or c.metadata.get("title")
                or c.path
            ),
            node_type=str(
                c.metadata.get("node_type")
                or ("TABLE" if c.metadata.get("is_table") else "PARAGRAPH")
            ),
            in_degree=in_degrees.get(c.path, 0),
            out_degree=out_degrees.get(c.path, 0),
        )
        for c in chunks
    ]
    return GraphVisualizerResponse(
        doc_slug=doc_slug,
        nodes=nodes,
        edges=graph_edges,
    )


@router.post("/documents/curate", response_model=CurateEdgesResult)
async def curate_document_edges(
    request: Request, payload: CurateEdgesRequest
) -> CurateEdgesResult:
    """Atomically curates knowledge graph edges with validation and audit logging."""
    pool = _get_db_pool(request)
    if pool is None:
        raise HTTPException(status_code=503, detail="Database is not connected.")
    service = KnowledgeEnrichmentService(pool=pool)
    try:
        return await service.curate_edges(
            add_edges=payload.add_edges,
            remove_edges=payload.remove_edges,
            reason=payload.reason,
            actor="WEB_USER",
        )
    except CorpusDomainError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc


@router.post("/search", response_model=SearchResponse)
async def search_corpus(request: Request, payload: SearchRequest) -> SearchResponse:
    import time

    if _get_db_pool(request) is None:
        raise HTTPException(status_code=503, detail="Database is not connected.")

    engine = _get_retrieval_engine(request)
    started = time.perf_counter()
    want_rerank = True if payload.rerank is None else payload.rerank
    try:
        result = await engine.search_venn(
            query=payload.query,
            pattern=payload.pattern,
            limit=payload.limit,
            rerank=want_rerank,
            doc_slugs=payload.doc_slugs or None,
            path_prefix=payload.path_prefix or None,
            is_regex=payload.is_regex,
            case_sensitive=payload.case_sensitive,
            order_by_reading_order=payload.order_by_reading_order,
        )
    except CorpusDomainError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    elapsed = (time.perf_counter() - started) * 1000.0

    return SearchResponse(
        query=result.query,
        pattern=result.pattern,
        elapsed_ms=round(elapsed, 1),
        confidence=result.confidence,
        documents=result.documents,
        groups=result.groups,
        verbatim_total=result.verbatim_total,
        verbatim_truncated=result.verbatim_truncated,
    )


@router.get("/relations", response_model=list[RelationTypeCatalogResponse])
async def list_relation_types_catalog(
    request: Request,
) -> list[RelationTypeCatalogResponse]:
    """Retrieves active relation types catalog with descriptions and symmetry flags."""
    pool = _get_db_pool(request)
    if pool is None:
        raise HTTPException(status_code=503, detail="Database is not connected.")

    from rag_eval.db.repositories.graph import GraphRepository

    repo = GraphRepository(pool=pool)
    catalog = await repo.get_relation_catalog()
    return [
        RelationTypeCatalogResponse(
            code=c.code,
            description=c.description,
            is_symmetric=c.is_symmetric,
        )
        for c in catalog
    ]


@router.post(
    "/documents/{doc_slug}/graph/traverse",
    response_model=list[GraphTraversalStepResponse],
)
async def traverse_document_graph(
    request: Request, doc_slug: str, payload: GraphTraverseRequest
) -> list[GraphTraversalStepResponse]:
    """Traverses knowledge graph starting from a chunk path via PostgreSQL stored procedure."""
    pool = _get_db_pool(request)
    if pool is None:
        raise HTTPException(status_code=503, detail="Database is not connected.")

    from rag_eval.db.repositories.chunks import ChunkRepository
    from rag_eval.db.repositories.graph import GraphRepository

    chunk_repo = ChunkRepository(pool=pool)
    src_chunk = await chunk_repo.get_by_path(payload.source_path)
    if src_chunk is None:
        return []

    graph_repo = GraphRepository(pool=pool)
    steps = await graph_repo.traverse(
        source_chunk_id=src_chunk.id,
        nav_direction=payload.nav_direction,
        depth_limit=payload.depth_limit,
        filter_relations=payload.filter_relations,
        match_limit=payload.limit,
    )
    return [
        GraphTraversalStepResponse(
            edge_id=str(s.edge_id),
            source_chunk_id=str(s.source_chunk_id),
            target_chunk_id=str(s.target_chunk_id),
            relation_type=s.relation_type,
            depth=s.depth,
            source_path=s.source_path,
            target_path=s.target_path,
            target_text=s.target_text,
            target_contextualized_text=s.target_contextualized_text,
            target_doc_slug=s.target_doc_slug,
            target_start_line=s.target_start_line,
            target_end_line=s.target_end_line,
            rationale=s.rationale,
            citation_text=s.citation_text,
        )
        for s in steps
    ]



