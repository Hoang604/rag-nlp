from __future__ import annotations

import asyncio
import datetime
import logging
import uuid
from typing import cast

import asyncpg
from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect

from rag_eval.answer import (
    PROVIDERS,
    Provider,
    answer_with_agent,
    available_providers,
    compose,
)
from rag_eval.db.connection import check_db_health
from rag_eval.db.repositories import CorpusRepository
from rag_eval.eval import (
    ExpectedTarget,
    load_cases,
    run_all,
    run_case,
    save_cases,
)
from rag_eval.exceptions import CorpusDomainError
from rag_eval.retrieval.embedder import SentenceTransformerQueryEmbedder
from rag_eval.retrieval.engine import RetrievalEngine
from rag_eval.retrieval.enrichment import KnowledgeEnrichmentService
from rag_eval.retrieval.reranker import CrossEncoderReranker
from rag_eval.schemas import CurateEdgesResult, RelationType
from rag_eval.web.schemas import (
    AnswerCitationResponse,
    AnswerRequest,
    AnswerResponse,
    CorpusDocumentResponse,
    CurateEdgesRequest,
    DocumentTreeResponse,
    EvalCaseResponse,
    EvalCaseUpdateRequest,
    GraphTraversalStepResponse,
    GraphTraverseRequest,
    GraphVisualizerEdge,
    GraphVisualizerNode,
    GraphVisualizerResponse,
    HealthResponse,
    ProviderStatusResponse,
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


class QAEventHub:
    """In-memory pub/sub hub broadcasting MCP webhook events to connected WebSocket clients."""

    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._history: list[dict[str, object]] = []
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._clients.add(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)

    async def publish(self, event: dict[str, object]) -> int:
        async with self._lock:
            self._history.append(event)
            if len(self._history) > 100:
                self._history = self._history[-100:]
            clients = list(self._clients)

        delivered = 0
        stale: list[WebSocket] = []
        for ws in clients:
            try:
                await ws.send_json(event)
                delivered += 1
            except (WebSocketDisconnect, RuntimeError, OSError):
                stale.append(ws)

        if stale:
            async with self._lock:
                for ws in stale:
                    self._clients.discard(ws)
        return delivered


qa_event_hub = QAEventHub()


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


@router.get("/answer/providers", response_model=list[ProviderStatusResponse])
async def get_answer_providers() -> list[ProviderStatusResponse]:
    """Lists CLI LLM providers and whether their executable is available in PATH."""
    return [
        ProviderStatusResponse(id=pid, label=label, available=avail)
        for pid, label, avail in available_providers()
    ]


@router.post("/qa/webhook")
async def receive_mcp_qa_webhook(request: Request) -> dict[str, object]:
    """Receives live tool-call and submit_grounded_answer events from the MCP Server and broadcasts over WebSocket."""
    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON payload: {exc}") from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Webhook body must be a JSON object.")

    event_dict = cast(dict[str, object], payload)
    if "timestamp" not in event_dict:
        event_dict["timestamp"] = datetime.datetime.now(datetime.UTC).isoformat()

    delivered = await qa_event_hub.publish(event_dict)
    return {"status": "ok", "delivered": delivered}


@router.get("/mcp")
async def mcp_streamable_http_get() -> None:
    """Stateless Streamable HTTP endpoint returns 405 on GET SSE probes per MCP 2025-03-26 spec."""
    raise HTTPException(status_code=405, detail="SSE stream not supported on stateless HTTP endpoint.")


@router.delete("/mcp")
async def mcp_streamable_http_delete() -> dict[str, str]:
    """Stateless Streamable HTTP session termination acknowledgement."""
    return {"status": "ok"}


@router.post("/mcp", response_model=None)
async def mcp_streamable_http_post(
    request: Request,
    session_id: str | None = None,
    answer_output: str | None = None,
    enable_answer_tool: bool = True,
    raw: bool = False,
) -> dict[str, object] | object:
    """Warm Streamable HTTP MCP JSON-RPC 2.0 endpoint sharing FastAPI's preloaded Qwen & CrossEncoder models."""
    from fastapi.responses import Response

    from rag_eval.mcp.server import (
        SERVER_NAME,
        SERVER_VERSION,
        CorpusMCPServer,
        create_default_corpus_mcp_tools,
        map_domain_error_to_jsonrpc,
    )

    pool = _get_db_pool(request)
    if pool is None:
        raise HTTPException(status_code=503, detail="Database is not connected.")

    try:
        req_body = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON-RPC body: {exc}") from exc

    if not isinstance(req_body, dict):
        raise HTTPException(status_code=400, detail="JSON-RPC payload must be an object.")

    # Notifications (e.g. notifications/initialized) have no 'id' and expect HTTP 202 Accepted
    if "id" not in req_body:
        return Response(status_code=202)

    engine = _get_retrieval_engine(request)

    async def _in_memory_emitter(event_type: str, data: dict[str, object]) -> None:
        event_payload: dict[str, object] = {
            "event": event_type,
            "session_id": session_id,
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
            **data,
        }
        await qa_event_hub.publish(event_payload)

    tools = create_default_corpus_mcp_tools(
        embedding_engine=engine._embedder,
        reranker=engine._reranker,
        answer_output_path=answer_output,
        pool=pool,
    )
    mcp_srv = CorpusMCPServer(
        tools=tools,
        enable_answer_tool=enable_answer_tool,
        answer_output_path=answer_output,
        session_id=session_id,
        event_emitter=_in_memory_emitter,
    )

    req_id = req_body.get("id")
    method = str(req_body.get("method") or "")
    params = req_body.get("params") or {}

    if method == "initialize":
        client_proto = (
            str(params.get("protocolVersion") or "2024-11-05")
            if isinstance(params, dict)
            else "2024-11-05"
        )
        dyn_instructions = await mcp_srv.get_instructions()
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": client_proto,
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": SERVER_NAME,
                    "version": SERVER_VERSION,
                },
                "instructions": dyn_instructions,
            },
        }

    if method == "tools/call" and not raw:
        import json

        if not isinstance(params, dict):
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32602, "message": "params must be a JSON object"},
            }
        t_name = str(params.get("name", ""))
        t_args = params.get("arguments", {})
        if not isinstance(t_args, dict):
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32602, "message": "arguments must be a JSON object"},
            }
        try:
            out = await mcp_srv.execute_tool(t_name, t_args)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(out, ensure_ascii=False),
                        }
                    ],
                    "isError": False,
                },
            }
        except CorpusDomainError as err:
            _, message, data = map_domain_error_to_jsonrpc(err)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(
                                {"error": message, "data": data},
                                ensure_ascii=False,
                            ),
                        }
                    ],
                    "isError": True,
                },
            }

    resp = await mcp_srv.handle_request_dict(cast(dict[str, object], req_body))
    if resp is None:
        return Response(status_code=202)
    return resp


@router.websocket("/qa/ws")
async def qa_websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket stream delivering live MCP tool calls and validated answers to the frontend."""
    await qa_event_hub.connect(websocket)
    try:
        await websocket.send_json(
            {
                "event": "ws_connected",
                "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
            }
        )
        while True:
            msg = await websocket.receive_text()
            if msg.strip().lower() == "ping":
                await websocket.send_json({"event": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        await qa_event_hub.disconnect(websocket)


@router.post("/answer", response_model=AnswerResponse)
async def answer_question(request: Request, payload: AnswerRequest) -> AnswerResponse:
    """Executes grounded Q&A via CLI Agent MCP (`submit_grounded_answer`) or Retrieve+Compose."""
    pool = _get_db_pool(request)
    if pool is None:
        raise HTTPException(status_code=503, detail="Database is not connected.")

    if payload.provider not in PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail=f"Provider '{payload.provider}' không hợp lệ. Chọn một trong: {', '.join(PROVIDERS)}",
        )
    provider: Provider = payload.provider
    repo = CorpusRepository(pool)
    session_id = payload.session_id or str(uuid.uuid4())

    base_url = str(request.base_url).rstrip("/")
    webhook_url = f"{base_url}/api/qa/webhook"

    await qa_event_hub.publish(
        {
            "event": "qa_started",
            "session_id": session_id,
            "question": payload.question,
            "provider": provider,
            "agent_mode": payload.agent_mode,
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
        }
    )

    try:
        if payload.agent_mode:
            composed = await answer_with_agent(
                repo=repo,
                question=payload.question,
                provider=provider,
                doc_slugs=payload.doc_slugs or None,
                webhook_url=webhook_url,
                session_id=session_id,
            )
        else:
            engine = _get_retrieval_engine(request)
            composed = await compose(
                engine=engine,
                repo=repo,
                question=payload.question,
                provider=provider,
                limit=payload.limit,
                doc_slugs=payload.doc_slugs or None,
            )
    except ( CorpusDomainError, RuntimeError, ValueError) as exc:
        err_msg = exc.message if isinstance(exc, CorpusDomainError) else str(exc)
        await qa_event_hub.publish(
            {
                "event": "qa_error",
                "session_id": session_id,
                "error": err_msg,
                "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
            }
        )
        raise HTTPException(status_code=400, detail=err_msg) from exc

    resp = AnswerResponse(
        question=composed.question,
        provider=composed.provider,
        answer=composed.answer,
        abstained=composed.abstained,
        citations=[
            AnswerCitationResponse(
                index=c.index,
                path=c.path,
                doc_slug=c.doc_slug,
                doc_title=c.doc_title,
                start_line=c.start_line,
                end_line=c.end_line,
                verbatim_text=c.verbatim_text,
                contextualized_text=c.contextualized_text,
                citation_text=c.citation_text,
            )
            for c in composed.citations
        ],
        retrieval_ms=composed.retrieval_ms,
        llm_ms=composed.llm_ms,
        total_ms=composed.total_ms,
    )

    await qa_event_hub.publish(
        {
            "event": "qa_completed",
            "session_id": session_id,
            "payload": resp.model_dump(mode="json"),
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
        }
    )
    return resp


@router.get("/eval/cases", response_model=list[EvalCaseResponse])
async def list_eval_cases() -> list[EvalCaseResponse]:
    """Returns all retrieval evaluation cases."""
    cases = await asyncio.to_thread(load_cases)
    return [EvalCaseResponse.model_validate(c.to_dict()) for c in cases]


@router.put("/eval/cases/{case_id}", response_model=EvalCaseResponse)
async def upsert_eval_case(
    case_id: str, payload: EvalCaseUpdateRequest
) -> EvalCaseResponse:
    """Updates or creates an evaluation case in data/eval/retrieval.jsonl."""
    cases = await asyncio.to_thread(load_cases)
    target = next((c for c in cases if c.id == case_id), None)
    expected_list = [
        ExpectedTarget(doc_slug=e.doc_slug, path_suffix=e.path_suffix)
        for e in payload.expected
    ]
    if target is None:
        from rag_eval.eval import EvalCase

        target = EvalCase(
            id=case_id,
            test_set=payload.test_set,
            domain=payload.domain,
            question=payload.question,
            query=payload.query,
            pattern=payload.pattern,
            expected=expected_list,
            is_regex=payload.is_regex,
            case_sensitive=payload.case_sensitive,
            doc_slugs=payload.doc_slugs,
            path_prefix=payload.path_prefix,
            note=payload.note,
        )
        cases.append(target)
    else:
        target.test_set = payload.test_set
        target.domain = payload.domain
        target.question = payload.question
        target.query = payload.query
        target.pattern = payload.pattern
        target.expected = expected_list
        target.is_regex = payload.is_regex
        target.case_sensitive = payload.case_sensitive
        target.doc_slugs = payload.doc_slugs
        target.path_prefix = payload.path_prefix
        target.note = payload.note

    await asyncio.to_thread(save_cases, cases)
    return EvalCaseResponse.model_validate(target.to_dict())


@router.delete("/eval/cases/{case_id}")
async def delete_eval_case(case_id: str) -> dict[str, str]:
    """Deletes an evaluation case by ID."""
    cases = await asyncio.to_thread(load_cases)
    filtered = [c for c in cases if c.id != case_id]
    if len(filtered) == len(cases):
        raise HTTPException(status_code=404, detail=f"Eval case '{case_id}' not found.")
    await asyncio.to_thread(save_cases, filtered)
    return {"status": "deleted", "id": case_id}


@router.post("/eval/cases/{case_id}/run", response_model=EvalCaseResponse)
async def execute_single_eval_case(
    request: Request, case_id: str
) -> EvalCaseResponse:
    """Runs a single evaluation case against RetrievalEngine and persists updated results."""
    if _get_db_pool(request) is None:
        raise HTTPException(status_code=503, detail="Database is not connected.")
    engine = _get_retrieval_engine(request)
    cases = await asyncio.to_thread(load_cases)
    target = next((c for c in cases if c.id == case_id), None)
    if target is None:
        raise HTTPException(status_code=404, detail=f"Eval case '{case_id}' not found.")
    await run_case(engine, target, limit=10, rerank=False)
    await asyncio.to_thread(save_cases, cases)
    return EvalCaseResponse.model_validate(target.to_dict())


@router.post("/eval/run", response_model=list[EvalCaseResponse])
async def execute_all_eval_cases(request: Request) -> list[EvalCaseResponse]:
    """Runs all evaluation cases and persists the updated retrieval.jsonl."""
    if _get_db_pool(request) is None:
        raise HTTPException(status_code=503, detail="Database is not connected.")
    engine = _get_retrieval_engine(request)
    cases = await run_all(engine, limit=10, rerank=False)
    return [EvalCaseResponse.model_validate(c.to_dict()) for c in cases]




