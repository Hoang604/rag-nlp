import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rag_eval.exceptions import (
    E_AST_GROUNDING_VALIDATION,
    E_CORPUS_INTEGRITY_VIOLATION,
    E_INVALID_DOCUMENT_HIERARCHY,
    E_STORAGE_CONNECTION,
    CorpusDomainError,
)
from rag_eval.mcp.server import (
    CorpusMCPServer,
    map_domain_error_to_jsonrpc,
)
from rag_eval.mcp.tools.sensors import (
    CorpusRuntimeSensors,
)
from rag_eval.schemas import ChunkEntity, GraphTraversalStepDTO, GraphTraverseResult


def test_domain_error_to_jsonrpc_mapping() -> None:
    """Verifies that domain error codes are strictly translated to JSON-RPC 2.0 specifications."""
    # Validation / AST Grounding -> -32602 (Invalid params)
    err_val = CorpusDomainError(
        error_code=E_AST_GROUNDING_VALIDATION,
        message="Invalid syntax",
        data={"detail": "ast_error"},
    )
    code, msg, data = map_domain_error_to_jsonrpc(err_val)
    assert code == -32602
    assert "Invalid syntax" in msg
    assert data["domain_code"] == E_AST_GROUNDING_VALIDATION

    # Invalid Hierarchy -> -32602 (Invalid params)
    err_hier = CorpusDomainError(
        error_code=E_INVALID_DOCUMENT_HIERARCHY,
        message="Orphaned chunk",
    )
    code_h, _, data_h = map_domain_error_to_jsonrpc(err_hier)
    assert code_h == -32602
    assert data_h["domain_code"] == E_INVALID_DOCUMENT_HIERARCHY

    # Storage Connection -> -32603 (Internal error)
    err_store = CorpusDomainError(
        error_code=E_STORAGE_CONNECTION,
        message="Database connection lost",
    )
    code_s, _, data_s = map_domain_error_to_jsonrpc(err_store)
    assert code_s == -32603
    assert data_s["domain_code"] == E_STORAGE_CONNECTION

    # Corpus Integrity -> -32603 (Internal error)
    err_int = CorpusDomainError(
        error_code=E_CORPUS_INTEGRITY_VIOLATION,
        message="Corrupt state",
    )
    code_i, _, data_i = map_domain_error_to_jsonrpc(err_int)
    assert code_i == -32603
    assert data_i["domain_code"] == E_CORPUS_INTEGRITY_VIOLATION

    # Negative protocol codes preserved
    err_proto = CorpusDomainError(
        error_code=-32602,
        message="Protocol validation failed",
    )
    code_p, _, data_p = map_domain_error_to_jsonrpc(err_proto)
    assert code_p == -32602
    assert data_p["domain_code"] == -32602


@pytest.mark.asyncio
async def test_mcp_server_handle_unknown_method() -> None:
    """Verifies that an unknown JSON-RPC method returns code -32601."""
    server = CorpusMCPServer()
    req: dict[str, object] = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "unknown_nonexistent_method",
        "params": {},
    }
    resp = await server.handle_request_dict(req)
    assert resp is not None
    err = resp.get("error")
    assert isinstance(err, dict)
    assert err.get("code") == -32601


@pytest.mark.asyncio
async def test_hierarchical_navigate_input_schema_has_no_chunk_id() -> None:
    """Verifies hierarchical_navigate accepts strictly 'path' and no 'chunk_id' parameter."""
    server = CorpusMCPServer()
    tools = await server.get_tool_definitions()
    nav_tool = next((t for t in tools if t["name"] == "hierarchical_navigate"), None)
    assert nav_tool is not None
    schema = nav_tool["inputSchema"]
    assert isinstance(schema, dict)
    props = schema.get("properties", {})
    assert "path" in props
    assert "chunk_id" not in props


@pytest.mark.asyncio
async def test_link_and_unlink_tool_schemas() -> None:
    """Verifies link_chunks and unlink_chunks schemas adhere to pure path addressing and hide DB internals."""
    server = CorpusMCPServer()
    tools = await server.get_tool_definitions()
    link_tool = next((t for t in tools if t["name"] == "link_chunks"), None)
    unlink_tool = next((t for t in tools if t["name"] == "unlink_chunks"), None)
    assert link_tool is not None
    assert unlink_tool is not None

    link_schema = link_tool.get("inputSchema")
    assert isinstance(link_schema, dict)
    link_props = link_schema.get("properties")
    assert isinstance(link_props, dict)
    assert "source_path" in link_props
    assert "target_path" in link_props
    assert "relation_type" in link_props
    assert "citation_text" in link_props
    assert "citation_text" in link_schema.get("required", [])
    assert "rationale" in link_props
    assert "anchor_text" not in link_props
    assert "chunk_id" not in link_props

    unlink_schema = unlink_tool.get("inputSchema")
    assert isinstance(unlink_schema, dict)
    unlink_props = unlink_schema.get("properties")
    assert isinstance(unlink_props, dict)
    assert "source_path" in unlink_props
    assert "target_path" in unlink_props
    assert "relation_type" in unlink_props
    assert "chunk_id" not in unlink_props

    traverse_tool = next((t for t in tools if t["name"] == "graph_traverse"), None)
    assert traverse_tool is not None
    trav_schema = traverse_tool.get("inputSchema")
    assert isinstance(trav_schema, dict)
    trav_props = trav_schema.get("properties")
    assert isinstance(trav_props, dict)
    assert "limit" in trav_props


@pytest.mark.asyncio
async def test_graph_traverse_multihop_source_path_resolution() -> None:
    """Verifies graph_traverse resolves source_path correctly across depth > 1 without leaking UUIDs."""
    mock_repo = AsyncMock()
    sensors = CorpusRuntimeSensors()
    sensors._get_repo = AsyncMock(return_value=mock_repo)

    root_id = uuid.uuid4()
    child_id = uuid.uuid4()

    mock_chunk = ChunkEntity(
        id=root_id,
        document_id=uuid.uuid4(),
        path="doc.sec_1",
        verbatim_text="Root section",
        contextualized_text="Root section",
        start_line=1,
        end_line=5,
    )

    steps_dto = [
        GraphTraversalStepDTO(
            edge_id=uuid.uuid4(),
            source_chunk_id=root_id,
            target_chunk_id=child_id,
            relation_type="REFERENCES",
            depth=1,
            source_path="doc.sec_1",
            target_path="doc.sec_2",
            target_text="Target sec 2",
            target_contextualized_text="[Root section]\nTarget sec 2",
            target_doc_slug="doc",
            target_start_line=6,
            target_end_line=10,
            rationale="Dẫn chiếu định nghĩa cơ bản",
            citation_text="Verbatim citation for sec 2",
        ),
        GraphTraversalStepDTO(
            edge_id=uuid.uuid4(),
            source_chunk_id=child_id,
            target_chunk_id=uuid.uuid4(),
            relation_type="SUPPORTS",
            depth=2,
            source_path="doc.sec_2",
            target_path="doc.sec_3",
            target_text="Target sec 3",
            target_contextualized_text="[Target sec 2]\nTarget sec 3",
            target_doc_slug="doc",
            target_start_line=11,
            target_end_line=15,
            rationale=None,
            citation_text="Verbatim citation for sec 3",
        ),
    ]

    mock_repo.chunks.get_by_path = AsyncMock(return_value=mock_chunk)
    mock_repo.graph.traverse = AsyncMock(return_value=steps_dto)

    res = await sensors.graph_traverse(source_path="doc.sec_1", max_depth=2, limit=10)

    assert isinstance(res, GraphTraverseResult)
    assert res.source_path == "doc.sec_1"
    assert len(res.paths) == 2
    assert res.paths[0].source_path == "doc.sec_1"
    assert res.paths[0].target_path == "doc.sec_2"
    assert res.paths[0].target_context == "Root section"
    assert res.paths[0].target_text == "Target sec 2"
    assert res.paths[0].citation_text == "Verbatim citation for sec 2"
    assert not hasattr(res.paths[0], "target_contextualized_text")
    assert not hasattr(res.paths[0], "target_doc_slug")
    assert res.paths[0].target_start_line == 6
    assert res.paths[0].target_end_line == 10
    assert res.paths[0].rationale == "Dẫn chiếu định nghĩa cơ bản"
    assert res.paths[1].source_path == "doc.sec_2"
    assert res.paths[1].target_path == "doc.sec_3"
    assert res.paths[1].target_context == "Target sec 2"
    assert res.paths[1].target_text == "Target sec 3"
    assert res.paths[1].citation_text == "Verbatim citation for sec 3"
    assert res.paths[1].rationale is None
    dump_str = json.dumps(res.model_dump())
    assert str(root_id) not in dump_str
    assert str(child_id) not in dump_str
    assert "target_contextualized_text" not in dump_str
    assert "target_doc_slug" not in dump_str

    mock_repo.graph.traverse.assert_awaited_once_with(
        root_id,
        nav_direction="OUTGOING",
        depth_limit=2,
        filter_relations=None,
        match_limit=10,
    )


@pytest.mark.asyncio
async def test_graph_traverse_root_chunk_context_isolation() -> None:
    """Verifies Invariant I-03 & S-03: Root chunk with contextualized_text == verbatim_text produces target_context == ''."""
    mock_repo = AsyncMock()
    sensors = CorpusRuntimeSensors()
    sensors._get_repo = AsyncMock(return_value=mock_repo)

    root_id = uuid.uuid4()
    target_id = uuid.uuid4()
    mock_chunk = ChunkEntity(
        id=root_id,
        document_id=uuid.uuid4(),
        path="doc.root",
        verbatim_text="Verbatim text",
        contextualized_text="Verbatim text",
        start_line=1,
        end_line=5,
    )
    steps_dto = [
        GraphTraversalStepDTO(
            edge_id=uuid.uuid4(),
            source_chunk_id=root_id,
            target_chunk_id=target_id,
            relation_type="REFERENCES",
            depth=1,
            source_path="doc.root",
            target_path="doc.target",
            target_text="Target root verbatim text",
            target_contextualized_text="Target root verbatim text",
            target_doc_slug="doc",
            target_start_line=1,
            target_end_line=5,
            rationale=None,
            citation_text="Verbatim citation for root",
        )
    ]
    mock_repo.chunks.get_by_path = AsyncMock(return_value=mock_chunk)
    mock_repo.graph.traverse = AsyncMock(return_value=steps_dto)

    res = await sensors.graph_traverse(source_path="doc.root", limit=1)
    assert len(res.paths) == 1
    assert res.paths[0].target_context == ""
    assert res.paths[0].target_text == "Target root verbatim text"
    assert res.paths[0].citation_text == "Verbatim citation for root"
    dump_str = json.dumps(res.model_dump())
    assert "target_contextualized_text" not in dump_str
    assert "target_doc_slug" not in dump_str


@pytest.mark.asyncio
async def test_graph_traverse_unknown_source_path_raises_error() -> None:
    """Verifies graph_traverse strictly rejects nonexistent source chunk path (I-01)."""
    mock_repo = AsyncMock()
    sensors = CorpusRuntimeSensors()
    sensors._get_repo = AsyncMock(return_value=mock_repo)

    mock_repo.chunks.get_by_path = AsyncMock(return_value=None)

    with pytest.raises(CorpusDomainError) as exc_info:
        await sensors.graph_traverse(source_path="doc.non_existent", max_depth=2)

    assert exc_info.value.error_code == E_INVALID_DOCUMENT_HIERARCHY






@pytest.mark.asyncio
async def test_mcp_legacy_prefix_rejected() -> None:
    """Verifies that requests with legacy 'mcp_corpus_' prefix are rejected with -32601 Method not found."""
    server = CorpusMCPServer()
    req: dict[str, object] = {
        "jsonrpc": "2.0",
        "id": 43,
        "method": "mcp_corpus_hybrid_search",
        "params": {},
    }
    resp = await server.handle_request_dict(req)
    assert resp is not None
    assert "error" in resp
    err = resp["error"]
    assert isinstance(err, dict)
    assert err.get("code") == -32601


@pytest.mark.asyncio
async def test_mcp_unknown_tool_call_validation_error() -> None:
    """Verifies that unknown tool call via tools/call maps to -32602 validation error."""
    server = CorpusMCPServer()
    req: dict[str, object] = {
        "jsonrpc": "2.0",
        "id": 44,
        "method": "tools/call",
        "params": {"name": "non_existent_tool", "arguments": {}},
    }
    resp = await server.handle_request_dict(req)
    assert resp is not None
    assert "error" in resp
    err = resp["error"]
    assert isinstance(err, dict)
    assert err.get("code") == -32602


@pytest.mark.asyncio
async def test_hybrid_search_fallback_on_embedder_failure() -> None:
    """Verifies that dense query embedder failure gracefully degrades to sparse BM25 (S-05 / I-04)."""
    from rag_eval.retrieval.engine import RetrievalEngine
    from rag_eval.schemas import SearchHitDTO

    mock_pool = MagicMock()
    mock_embedder = MagicMock()
    mock_embedder.embed_query = AsyncMock(side_effect=RuntimeError("CUDA out of memory"))

    engine = RetrievalEngine(pool=mock_pool, embedder=mock_embedder)

    sample_hit = SearchHitDTO(
        chunk_id=uuid.uuid4(),
        doc_slug="doc_sec",
        doc_title="Doc Sec",
        path="doc_sec.sec_1",
        start_line=1,
        end_line=5,
        verbatim_text="Sample text",
        contextualized_text="Sample context",
        score=0.85,
        dense_similarity=0.0,
        sparse_rank=1,
        metadata={},
    )

    with patch("rag_eval.retrieval.engine.CorpusRepository") as mock_repo_cls:
        mock_repo = MagicMock()
        mock_repo.chunks.hybrid_search = AsyncMock(return_value=[sample_hit])
        mock_repo_cls.return_value = mock_repo

        result = await engine.search(query="fixture_semantic_query", limit=5)
        assert len(result.hits) == 1
        assert result.hits[0].path == "doc_sec.sec_1"
        assert result.confidence is not None


@pytest.mark.asyncio
async def test_hybrid_search_venn_partitioning() -> None:
    """Verifies that overlapping chunks appear strictly in both_hits with dual ranks,
    and non-overlapping chunks appear in their respective disjoint sets (I-01, I-02, I-05).
    """
    from rag_eval.retrieval.engine import RetrievalEngine
    from rag_eval.schemas import SearchHitDTO

    mock_pool = MagicMock()
    mock_embedder = MagicMock()
    mock_embedder.embed_query = AsyncMock(return_value=[0.1] * 512)

    engine = RetrievalEngine(pool=mock_pool, embedder=mock_embedder)

    hit_shared = SearchHitDTO(
        chunk_id=uuid.uuid4(),
        doc_slug="fixture_doc",
        doc_title="Fixture Doc",
        path="fixture_doc.sec_1",
        start_line=1,
        end_line=5,
        verbatim_text="Shared text",
        contextualized_text="Shared context",
        score=0.9,
        metadata={},
    )
    hit_sem_only = SearchHitDTO(
        chunk_id=uuid.uuid4(),
        doc_slug="fixture_doc",
        doc_title="Fixture Doc",
        path="fixture_doc.sec_2",
        start_line=6,
        end_line=10,
        verbatim_text="Semantic text",
        contextualized_text="Semantic context",
        score=0.8,
        metadata={},
    )
    hit_verb_only = SearchHitDTO(
        chunk_id=uuid.uuid4(),
        doc_slug="fixture_doc",
        doc_title="Fixture Doc",
        path="fixture_doc.sec_3",
        start_line=11,
        end_line=15,
        verbatim_text="Verbatim text",
        contextualized_text="Verbatim context",
        score=0.7,
        metadata={},
    )

    with patch("rag_eval.retrieval.engine.CorpusRepository") as mock_repo_cls:
        mock_repo = MagicMock()
        mock_repo.chunks.hybrid_search = AsyncMock(return_value=[hit_shared, hit_sem_only])
        mock_repo.chunks.verbatim_grep = AsyncMock(return_value=([hit_shared, hit_verb_only], 2))
        mock_repo_cls.return_value = mock_repo

        result = await engine.search_venn(
            query="fixture_query_token",
            pattern="fixture_anchor_token",
            limit=10,
        )

        # Disjointness (I-01)
        both_paths = {h.path for h in result.both_hits}
        sem_paths = {h.path for h in result.semantic_only_hits}
        verb_paths = {h.path for h in result.verbatim_only_hits}
        assert both_paths.isdisjoint(sem_paths)
        assert both_paths.isdisjoint(verb_paths)
        assert sem_paths.isdisjoint(verb_paths)
        assert result.total_unique_hits == 3

        # Overlap in both_hits (I-02)
        assert len(result.both_hits) == 1
        b_hit = result.both_hits[0]
        assert b_hit.path == "fixture_doc.sec_1"
        assert b_hit.context == ""  # "Shared context" has no ancestor bracket prefix
        assert b_hit.text == "Shared context"
        assert b_hit.contextualized_text == "Shared context"
        assert b_hit.semantic_rank == 1
        assert b_hit.verbatim_rank == 1
        assert b_hit.semantic_score == 0.9
        assert b_hit.verbatim_score == 0.9

        # Semantic only (I-02)
        assert len(result.semantic_only_hits) == 1
        s_hit = result.semantic_only_hits[0]
        assert s_hit.path == "fixture_doc.sec_2"
        assert s_hit.context == ""
        assert s_hit.text == "Semantic context"
        assert s_hit.contextualized_text == "Semantic context"
        assert s_hit.semantic_rank == 2
        assert s_hit.verbatim_rank is None
        assert s_hit.semantic_score == 0.8
        assert s_hit.verbatim_score is None

        # Verbatim only (I-02)
        assert len(result.verbatim_only_hits) == 1
        v_hit = result.verbatim_only_hits[0]
        assert v_hit.path == "fixture_doc.sec_3"
        assert v_hit.context == ""
        assert v_hit.text == "Verbatim context"
        assert v_hit.contextualized_text == "Verbatim context"
        assert v_hit.semantic_rank is None
        assert v_hit.verbatim_rank == 2
        assert v_hit.semantic_score is None
        assert v_hit.verbatim_score == 0.7

        # Pure Path Addressing (I-05): No database UUID in hit payload
        assert not hasattr(b_hit, "chunk_id")

        # Sparse serialization contract: unpopulated cross-channel metrics are omitted (I-03)
        assert all(v is not None for v in b_hit.model_dump().values())
        assert "contextualized_text" not in b_hit.model_dump()  # Un-serialized property (I-04)
        assert "verbatim_rank" not in s_hit.model_dump()
        assert "verbatim_score" not in s_hit.model_dump()
        assert "semantic_rank" not in v_hit.model_dump()
        assert "semantic_score" not in v_hit.model_dump()


@pytest.mark.asyncio
async def test_hybrid_search_requires_both_query_and_pattern() -> None:
    """Verifies that omitting or providing empty pattern or query triggers -32602 schema error (I-03)."""
    server = CorpusMCPServer()

    # Missing pattern
    req_missing_pattern: dict[str, object] = {
        "jsonrpc": "2.0",
        "id": 101,
        "method": "tools/call",
        "params": {
            "name": "hybrid_search",
            "arguments": {"query": "fixture_query_token"},
        },
    }
    resp = await server.handle_request_dict(req_missing_pattern)
    assert resp is not None
    assert "error" in resp
    err_missing = resp["error"]
    assert isinstance(err_missing, dict)
    assert err_missing.get("code") == -32602

    # Empty pattern (min_length=1)
    req_empty_pattern: dict[str, object] = {
        "jsonrpc": "2.0",
        "id": 102,
        "method": "tools/call",
        "params": {
            "name": "hybrid_search",
            "arguments": {"query": "fixture_query_token", "pattern": ""},
        },
    }
    resp = await server.handle_request_dict(req_empty_pattern)
    assert resp is not None
    assert "error" in resp
    err_empty = resp["error"]
    assert isinstance(err_empty, dict)
    assert err_empty.get("code") == -32602


@pytest.mark.asyncio
async def test_mcp_tool_catalog_excludes_verbatim_grep() -> None:
    """Verifies that verbatim_grep is retired from MCP tools/list and exactly 5 canonical tools exist (I-04)."""
    server = CorpusMCPServer()
    req: dict[str, object] = {
        "jsonrpc": "2.0",
        "id": 201,
        "method": "tools/list",
        "params": {},
    }
    resp = await server.handle_request_dict(req)
    assert resp is not None
    res_obj = resp.get("result")
    assert isinstance(res_obj, dict)
    tools = res_obj.get("tools")
    assert isinstance(tools, list)
    tool_names = {t["name"] for t in tools if isinstance(t, dict) and "name" in t}
    assert len(tool_names) == 6
    assert "hybrid_search" in tool_names
    assert "hierarchical_navigate" in tool_names
    assert "graph_traverse" in tool_names
    assert "link_chunks" in tool_names
    assert "unlink_chunks" in tool_names
    assert "get_raw" in tool_names
    assert "verbatim_grep" not in tool_names


@pytest.mark.asyncio
async def test_hybrid_search_venn_with_rerank() -> None:
    """Verifies single-pass reranker evaluation over semantic candidates (S-05, I-02)."""
    from rag_eval.retrieval.engine import RetrievalEngine
    from rag_eval.schemas import SearchHitDTO

    mock_pool = MagicMock()
    mock_embedder = MagicMock()
    mock_embedder.embed_query = AsyncMock(return_value=[0.1] * 512)

    mock_reranker = MagicMock()

    hit_shared = SearchHitDTO(
        chunk_id=uuid.uuid4(),
        doc_slug="fixture_doc",
        doc_title="Fixture Doc",
        path="fixture_doc.sec_1",
        start_line=1,
        end_line=5,
        verbatim_text="Shared text",
        contextualized_text="Shared context",
        score=0.9,
        metadata={},
    )
    hit_sem_only = SearchHitDTO(
        chunk_id=uuid.uuid4(),
        doc_slug="fixture_doc",
        doc_title="Fixture Doc",
        path="fixture_doc.sec_2",
        start_line=6,
        end_line=10,
        verbatim_text="Semantic text",
        contextualized_text="Semantic context",
        score=0.8,
        metadata={},
    )
    hit_reranked_shared = hit_shared.model_copy(update={"rerank_score": 0.95})
    hit_reranked_sem = hit_sem_only.model_copy(update={"rerank_score": 0.85})
    mock_reranker.rerank = AsyncMock(return_value=[hit_reranked_shared, hit_reranked_sem])

    engine = RetrievalEngine(pool=mock_pool, embedder=mock_embedder, reranker=mock_reranker)

    with patch("rag_eval.retrieval.engine.CorpusRepository") as mock_repo_cls:
        mock_repo = MagicMock()
        mock_repo.chunks.hybrid_search = AsyncMock(return_value=[hit_shared, hit_sem_only])
        mock_repo.chunks.verbatim_grep = AsyncMock(return_value=([hit_shared], 1))
        mock_repo_cls.return_value = mock_repo

        result = await engine.search_venn(
            query="fixture_semantic_query",
            pattern="fixture_anchor_token",
            rerank=True,
        )

        assert len(result.both_hits) == 1
        assert result.both_hits[0].rerank_score == 0.95
        assert len(result.semantic_only_hits) == 1
        assert result.semantic_only_hits[0].rerank_score == 0.85


@pytest.mark.asyncio
async def test_get_raw_by_doc_slug() -> None:
    """Verifies get_raw returns exact raw document slice by doc_slug with line boundaries."""
    from rag_eval.schemas import DocumentEntity

    mock_repo = AsyncMock()
    sensors = CorpusRuntimeSensors()
    sensors._get_repo = AsyncMock(return_value=mock_repo)

    raw_content = "\n".join(f"Line {i}" for i in range(1, 51))
    doc_entity = DocumentEntity(
        id=uuid.uuid4(),
        doc_slug="fixture.doc",
        title="Fixture Title",
        raw_text=raw_content,
    )
    mock_repo.documents.get_by_slug = AsyncMock(return_value=doc_entity)

    # Slice 10 to 20
    res = await sensors.get_raw(path_or_slug="fixture.doc", start_line=10, end_line=20)
    assert res.doc_slug == "fixture.doc"
    assert res.title == "Fixture Title"
    assert res.start_line == 10
    assert res.end_line == 20
    assert res.total_lines == 50
    assert res.raw_text == "\n".join(f"Line {i}" for i in range(10, 21))

    # Default end_line (up to start_line + 199 or total_lines)
    res_default = await sensors.get_raw(path_or_slug="fixture.doc", start_line=1)
    assert res_default.start_line == 1
    assert res_default.end_line == 50
    assert res_default.total_lines == 50


@pytest.mark.asyncio
async def test_get_raw_by_chunk_path() -> None:
    """Verifies get_raw resolves document from a chunk LTree path."""
    from rag_eval.schemas import DocumentEntity

    mock_repo = AsyncMock()
    sensors = CorpusRuntimeSensors()
    sensors._get_repo = AsyncMock(return_value=mock_repo)

    doc_id = uuid.uuid4()
    chunk_entity = ChunkEntity(
        id=uuid.uuid4(),
        document_id=doc_id,
        path="fixture.doc.sec_1",
        verbatim_text="Sample chunk",
        contextualized_text="Sample chunk",
        start_line=5,
        end_line=15,
    )
    doc_entity = DocumentEntity(
        id=doc_id,
        doc_slug="fixture.doc",
        title="Fixture Title",
        raw_text="Line 1\nLine 2\nLine 3\nLine 4\nLine 5",
    )

    mock_repo.documents.get_by_slug = AsyncMock(return_value=None)
    mock_repo.chunks.get_by_path = AsyncMock(return_value=chunk_entity)
    mock_repo.documents.get_by_id = AsyncMock(return_value=doc_entity)

    res = await sensors.get_raw(path_or_slug="fixture.doc.sec_1", start_line=2, end_line=4)
    assert res.doc_slug == "fixture.doc"
    assert res.start_line == 2
    assert res.end_line == 4
    assert res.raw_text == "Line 2\nLine 3\nLine 4"


@pytest.mark.asyncio
async def test_get_raw_line_range_validations() -> None:
    """Verifies get_raw rejects invalid bounds, out of range lines, and spans exceeding MAX_RAW_LINES (200)."""
    from rag_eval.schemas import DocumentEntity

    mock_repo = AsyncMock()
    sensors = CorpusRuntimeSensors()
    sensors._get_repo = AsyncMock(return_value=mock_repo)

    doc_entity = DocumentEntity(
        id=uuid.uuid4(),
        doc_slug="fixture.doc",
        title="Fixture Title",
        raw_text="\n".join(f"L{i}" for i in range(1, 301)),
    )
    mock_repo.documents.get_by_slug = AsyncMock(return_value=doc_entity)

    # 1. start_line < 1
    with pytest.raises(CorpusDomainError) as exc_info1:
        await sensors.get_raw(path_or_slug="fixture.doc", start_line=0)
    assert exc_info1.value.error_code == E_AST_GROUNDING_VALIDATION

    # 2. start_line > total_lines
    with pytest.raises(CorpusDomainError) as exc_info2:
        await sensors.get_raw(path_or_slug="fixture.doc", start_line=301)
    assert exc_info2.value.error_code == E_AST_GROUNDING_VALIDATION

    # 3. end_line < start_line
    with pytest.raises(CorpusDomainError) as exc_info3:
        await sensors.get_raw(path_or_slug="fixture.doc", start_line=10, end_line=5)
    assert exc_info3.value.error_code == E_AST_GROUNDING_VALIDATION

    # 4. span > 200 lines (e.g. 1 to 201 is 201 lines)
    with pytest.raises(CorpusDomainError) as exc_info4:
        await sensors.get_raw(path_or_slug="fixture.doc", start_line=1, end_line=201)
    assert exc_info4.value.error_code == E_AST_GROUNDING_VALIDATION

    # 5. Non-existent path or slug
    mock_repo.documents.get_by_slug = AsyncMock(return_value=None)
    mock_repo.chunks.get_by_path = AsyncMock(return_value=None)
    mock_repo.documents.list_by_prefix = AsyncMock(return_value=[])

    with pytest.raises(CorpusDomainError) as exc_info5:
        await sensors.get_raw(path_or_slug="non.existent.path")
    assert exc_info5.value.error_code == E_INVALID_DOCUMENT_HIERARCHY


