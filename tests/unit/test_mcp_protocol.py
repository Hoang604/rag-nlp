import pytest

from rag_eval.legal.exceptions import (
    E_AST_GROUNDING_VALIDATION,
    E_CORPUS_INTEGRITY_VIOLATION,
    E_INVALID_DOCUMENT_HIERARCHY,
    E_STORAGE_CONNECTION,
    CorpusDomainError,
)
from rag_eval.legal.mcp.server import (
    CorpusMCPServer,
    map_domain_error_to_jsonrpc,
    render_server_instructions,
)


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


def test_render_server_instructions_contains_principles() -> None:
    """Verifies that rendered instructions contain core principles."""
    instructions = render_server_instructions()
    assert "# RAG CORPUS RETRIEVAL & STAGING PRINCIPLES" in instructions
    assert "HIERARCHICAL STRUCTURE" in instructions


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
