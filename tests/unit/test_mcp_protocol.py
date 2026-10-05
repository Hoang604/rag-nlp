import json
import uuid
from unittest.mock import AsyncMock

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
    AgentBacklogItem,
    AgentGraphTraversalStep,
    AgentHierarchyNode,
    AgentSearchHit,
    CorpusRuntimeSensors,
    GraphTraverseResult,
)
from rag_eval.schemas import ChunkEntity, ContextType, GraphTraversalStepDTO


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
async def test_mcp_tool_definitions_and_instructions_clean_of_infrastructure_buzzwords() -> None:
    """Verifies all 19 tools and server instructions are free of database/infrastructure buzzwords."""
    server = CorpusMCPServer()
    instructions = await server.get_instructions()
    tools = await server.get_tool_definitions()

    forbidden_keywords = [
        "Trigram GIN",
        "PostgreSQL",
        ".cache/stg",
        "toán tử ltree",
        "ltree",
        "kiểm toán WAL",
        "WAL",
        "RRF",
        "cross-encoder",
    ]

    for kw in forbidden_keywords:
        assert kw not in instructions, f"Found forbidden keyword '{kw}' in server instructions"

    for tool in tools:
        t_name = str(tool["name"])
        t_desc = str(tool.get("description", ""))
        for kw in forbidden_keywords:
            assert kw not in t_desc, f"Found forbidden keyword '{kw}' in description of tool '{t_name}'"

        schema_json = json.dumps(tool.get("inputSchema", {}), ensure_ascii=False)
        for kw in forbidden_keywords:
            assert kw not in schema_json, f"Found forbidden keyword '{kw}' in inputSchema of tool '{t_name}'"


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
async def test_stg_patch_input_schema_has_no_review_or_finalization_states() -> None:
    """Verifies stg_patch input schema prohibits review_status and finalization_state backdoor."""
    server = CorpusMCPServer()
    tools = await server.get_tool_definitions()
    patch_tool = next((t for t in tools if t["name"] == "stg_patch"), None)
    assert patch_tool is not None
    schema_str = json.dumps(patch_tool["inputSchema"])
    assert "review_status" not in schema_str
    assert "finalization_state" not in schema_str


def test_sensor_dto_payload_invariants_no_internal_leakage() -> None:
    """Verifies all Agent-First DTO models strictly hide database UUIDs and raw algorithm scores."""
    # AgentSearchHit invariants
    assert "chunk_id" not in AgentSearchHit.model_fields
    assert "score" not in AgentSearchHit.model_fields
    assert "dense_similarity" not in AgentSearchHit.model_fields
    assert "rerank_score" not in AgentSearchHit.model_fields
    assert "sparse_rank" not in AgentSearchHit.model_fields

    hit = AgentSearchHit(
        doc_slug="test_doc",
        doc_title="Test Title",
        path="test_doc.sec_1",
        start_line=1,
        end_line=10,
        verbatim_text="Sample text",
        contextualized_text="Sample text contextualized",
        context_type="SELF_CONTAINED",
        is_all_refs_resolved=True,
    )
    hit_dict = hit.model_dump()
    assert "chunk_id" not in hit_dict

    # AgentHierarchyNode invariants
    assert "chunk_id" not in AgentHierarchyNode.model_fields
    assert AgentHierarchyNode.model_fields["start_line"].is_required()
    assert AgentHierarchyNode.model_fields["end_line"].is_required()

    node = AgentHierarchyNode(
        path="test_doc.sec_1",
        doc_slug="test_doc",
        start_line=1,
        end_line=10,
        verbatim_text="Node text",
        contextualized_text="Node contextualized text",
    )
    assert "chunk_id" not in node.model_dump()

    # AgentGraphTraversalStep invariants
    assert "edge_id" not in AgentGraphTraversalStep.model_fields
    assert "source_chunk_id" not in AgentGraphTraversalStep.model_fields
    assert "target_chunk_id" not in AgentGraphTraversalStep.model_fields

    step = AgentGraphTraversalStep(
        source_path="test_doc.sec_1",
        target_path="test_doc.sec_2",
        relation_type="REFERENCES",
        depth=1,
    )
    assert "edge_id" not in step.model_dump()

    # AgentBacklogItem invariants
    assert "ref_id" not in AgentBacklogItem.model_fields
    assert "edge_id" not in AgentBacklogItem.model_fields
    assert "chunk_id" not in AgentBacklogItem.model_fields
    assert "target_chunk_id" not in AgentBacklogItem.model_fields

    item = AgentBacklogItem(
        doc_slug="test_doc",
        path="test_doc.sec_1",
    )
    assert "chunk_id" not in item.model_dump()


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
        context_type=ContextType.SELF_CONTAINED,
        is_all_refs_resolved=True,
    )

    steps_dto = [
        GraphTraversalStepDTO(
            edge_id=uuid.uuid4(),
            source_chunk_id=root_id,
            target_chunk_id=child_id,
            target_path="doc.sec_2",
            relation_type="REFERENCES",
            depth=1,
            target_text="Target sec 2",
        ),
        GraphTraversalStepDTO(
            edge_id=uuid.uuid4(),
            source_chunk_id=child_id,
            target_chunk_id=uuid.uuid4(),
            target_path="doc.sec_3",
            relation_type="SUPPORTS",
            depth=2,
            target_text="Target sec 3",
        ),
    ]

    mock_repo.chunks.get_by_path = AsyncMock(return_value=mock_chunk)
    mock_repo.graph.traverse = AsyncMock(return_value=steps_dto)
    mock_repo.chunks.resolve_ids_batch = AsyncMock(return_value={child_id: "doc.sec_2"})

    res = await sensors.graph_traverse(source_path="doc.sec_1", max_depth=2)

    assert isinstance(res, GraphTraverseResult)
    assert res.source_path == "doc.sec_1"
    assert len(res.paths) == 2
    assert res.paths[0].source_path == "doc.sec_1"
    assert res.paths[0].target_path == "doc.sec_2"
    assert res.paths[1].source_path == "doc.sec_2"
    assert res.paths[1].target_path == "doc.sec_3"
    dump_str = json.dumps(res.model_dump())
    assert str(root_id) not in dump_str
    assert str(child_id) not in dump_str


@pytest.mark.asyncio
async def test_graph_traverse_multihop_unresolvable_source_id_raises_error() -> None:
    """Verifies graph_traverse strictly rejects unresolvable intermediate node IDs rather than faking fallback."""
    mock_repo = AsyncMock()
    sensors = CorpusRuntimeSensors()
    sensors._get_repo = AsyncMock(return_value=mock_repo)

    root_id = uuid.uuid4()
    orphan_id = uuid.uuid4()

    mock_chunk = ChunkEntity(
        id=root_id,
        document_id=uuid.uuid4(),
        path="doc.sec_1",
        verbatim_text="Root section",
        contextualized_text="Root section",
        start_line=1,
        end_line=5,
        context_type=ContextType.SELF_CONTAINED,
        is_all_refs_resolved=True,
    )

    steps_dto = [
        GraphTraversalStepDTO(
            edge_id=uuid.uuid4(),
            source_chunk_id=orphan_id,
            target_chunk_id=uuid.uuid4(),
            target_path="doc.sec_orphan",
            relation_type="REFERENCES",
            depth=2,
            target_text="Orphan target",
        ),
    ]

    mock_repo.chunks.get_by_path = AsyncMock(return_value=mock_chunk)
    mock_repo.graph.traverse = AsyncMock(return_value=steps_dto)
    # resolve_ids_batch does not return orphan_id (e.g. broken reference)
    mock_repo.chunks.resolve_ids_batch = AsyncMock(return_value={})

    with pytest.raises(CorpusDomainError) as exc_info:
        await sensors.graph_traverse(source_path="doc.sec_1", max_depth=2)

    assert exc_info.value.error_code == E_INVALID_DOCUMENT_HIERARCHY

