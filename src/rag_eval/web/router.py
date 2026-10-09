from __future__ import annotations

import datetime
import logging
import re
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
from rag_eval.schemas import (
    RelationType,
    SearchHitDTO,
    VerbatimGrepQuery,
)
from rag_eval.web.schemas import (
    CorpusDocumentResponse,
    DocumentTreeResponse,
    GraphTraversalStepResponse,
    GraphTraverseRequest,
    GraphVisualizerEdge,
    GraphVisualizerNode,
    GraphVisualizerResponse,
    HealthResponse,
    LinkChunksInput,
    LinkChunksResponse,
    RawTextResponse,
    RelationTypeCatalogResponse,
    SearchHitResponse,
    SearchRequest,
    SearchResponse,
    UnlinkChunksInput,
    UnlinkChunksResponse,
    VerbatimGrepHitResponse,
    VerbatimGrepRequest,
    VerbatimGrepResponse,
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


def _format_verbatim_grep_hits(
    raw_hits: list[SearchHitDTO],
    pattern: str,
    is_regex: bool,
    case_sensitive: bool,
) -> list[VerbatimGrepHitResponse]:
    """Helper trích xuất vị trí ký tự và định dạng snippet cho Web UI."""
    hits: list[VerbatimGrepHitResponse] = []
    for m in raw_hits:
        offset = 0
        match_len = len(pattern)
        if is_regex:
            flags = 0 if case_sensitive else re.IGNORECASE
            try:
                match_obj = re.search(pattern, m.verbatim_text, flags)
                if match_obj:
                    offset = match_obj.start()
                    match_len = max(1, match_obj.end() - match_obj.start())
            except re.error:
                offset = 0
        else:
            if case_sensitive:
                idx = m.verbatim_text.find(pattern)
            else:
                idx = m.verbatim_text.lower().find(pattern.lower())
            offset = max(0, idx)

        snippet_start = max(0, offset - 20)
        snippet_end = min(len(m.verbatim_text), offset + match_len + 100)
        snippet = m.verbatim_text[snippet_start:snippet_end]
        hits.append(
            VerbatimGrepHitResponse(
                chunk_id=str(m.chunk_id),
                doc_slug=m.doc_slug,
                path=m.path,
                start_line=m.start_line,
                end_line=m.end_line,
                char_offset=offset,
                match_snippet=snippet,
                verbatim_text=m.verbatim_text,
                metadata=m.metadata,
            )
        )
    return hits


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


@router.post("/documents/links", response_model=LinkChunksResponse)
async def link_document_chunks(
    request: Request, payload: LinkChunksInput
) -> LinkChunksResponse:
    """Creates or updates a semantic relationship edge between two chunks."""
    pool = _get_db_pool(request)
    if pool is None:
        raise HTTPException(status_code=503, detail="Database is not connected.")
    service = KnowledgeEnrichmentService(pool=pool)
    try:
        res = await service.link_chunks(
            source_path=payload.source_path,
            target_path=payload.target_path,
            relation_type=payload.relation_type,
            rationale=payload.rationale,
        )
        return LinkChunksResponse(
            status="SUCCESS",
            source_path=res.source_path,
            target_path=res.target_path,
            relation_type=res.relation_type,
            created=res.created,
            rationale=res.rationale,
        )
    except CorpusDomainError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc


@router.post("/documents/unlinks", response_model=UnlinkChunksResponse)
async def unlink_document_chunks(
    request: Request, payload: UnlinkChunksInput
) -> UnlinkChunksResponse:
    """Removes targeted relationship edge(s) between two chunks."""
    pool = _get_db_pool(request)
    if pool is None:
        raise HTTPException(status_code=503, detail="Database is not connected.")
    service = KnowledgeEnrichmentService(pool=pool)
    try:
        res = await service.unlink_chunks(
            source_path=payload.source_path,
            target_path=payload.target_path,
            relation_type=payload.relation_type,
        )
        return UnlinkChunksResponse(
            status="SUCCESS",
            source_path=res.source_path,
            target_path=res.target_path,
            removed_edges_count=res.removed_edges_count,
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
        result = await engine.search(
            query=payload.query,
            limit=payload.limit,
            rerank=want_rerank,
            doc_slugs=payload.doc_slugs or None,
            path_prefix=payload.path_prefix or None,
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
        )
        for s in steps
    ]


@router.post("/corpus/grep", response_model=VerbatimGrepResponse)
async def grep_corpus_verbatim(
    request: Request, payload: VerbatimGrepRequest
) -> VerbatimGrepResponse:
    """Exact or regex grep across PostgreSQL corpus chunks via verbatim_grep repository call."""
    pool = _get_db_pool(request)
    if pool is None:
        raise HTTPException(status_code=503, detail="Database is not connected.")

    repo = CorpusRepository(pool)
    query_dto = VerbatimGrepQuery(
        query_pattern=payload.pattern,
        target_documents=None,
        path_prefix=None,
        is_regex=payload.is_regex,
        case_sensitive=payload.case_sensitive,
        match_limit=payload.limit,
    )
    raw_hits, total_matches = await repo.chunks.verbatim_grep(query_dto)
    hits = _format_verbatim_grep_hits(
        raw_hits, payload.pattern, payload.is_regex, payload.case_sensitive
    )
    return VerbatimGrepResponse(
        pattern=payload.pattern,
        is_regex=payload.is_regex,
        total_matches=total_matches,
        returned=len(hits),
        truncated=(total_matches > len(hits)),
        matches=hits,
    )
