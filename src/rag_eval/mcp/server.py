from __future__ import annotations

import atexit
import json
import logging
import os
import signal
import sys
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.shared.exceptions import MCPError
from mcp.types import CallToolResult, TextContent

from rag_eval.exceptions import (
    E_AST_GROUNDING_VALIDATION,
    E_CORPUS_INTEGRITY_VIOLATION,
    E_INVALID_DOCUMENT_HIERARCHY,
    CorpusDomainError,
)
from rag_eval.mcp.registry import register_mcp_tools
from rag_eval.mcp.tools import (
    CorpusMCPTools,
    CorpusRuntimeSensors,
    CorpusStagingTools,
)
from rag_eval.retrieval.embedder import (
    QueryEmbedder,
    SentenceTransformerQueryEmbedder,
)
from rag_eval.retrieval.reranker import CorpusReranker

logger = logging.getLogger("rag_eval.mcp.server")


class FlushingFileHandler(logging.FileHandler):
    """FileHandler that automatically flushes on every emit for immediate persistence."""

    def emit(self, record: logging.LogRecord) -> None:
        super().emit(record)
        self.flush()


SERVER_NAME = "rag-corpus-mcp"
SERVER_VERSION = "3.0.0"

STATIC_SERVER_INSTRUCTIONS = """# RAG CORPUS PROTOCOL & STAGING INVARIANTS

## 1. MENTAL & TOPOLOGICAL MODEL
- HIERARCHY: Documents form a strict tree `Document -> Segment -> Sub-segment...` with dot-separated hierarchical paths (e.g. `doc_slug.sec_1.para_2`).
- KNOWLEDGE GRAPH: Directed relations interlink chunks across hierarchy boundaries to preserve cross-cutting semantic dependencies.
- LEAF INDEXING: Retrieval and curation operate on leaf chunks containing verbatim source text and contextualized ancestry text.

## 2. RETRIEVAL & CONTEXT EXPANSION PRINCIPLE
Retrieval direction is governed by token specificity and contextual completeness:
- Token Specificity: Exact alphanumeric identifiers and literal phrases demand deterministic pattern matching (`verbatim_grep`); thematic and conceptual inquiries demand hybrid semantic relevance (`hybrid_search`).
- Contextual Expansion: When a retrieved chunk possesses an unresolved referential deficit, expand locally along the hierarchical tree (`hierarchical_navigate`) or follow semantic relations through the knowledge graph (`graph_traverse`) rather than issuing ungrounded global queries.

## 3. GROUNDING & AUTHORITATIVE CITATION CONTRACT
- Every claim, inference, or synthesis must be explicitly grounded in retrieved leaf chunks and cited via exact hierarchical paths.
- Tool responses are the sole source of truth. When no retrieved chunk grounds an answer, affirm the absence of data explicitly; never extrapolate or hallucinate ungrounded facts.

## 4. STAGING CURATION & TOPOLOGICAL INVARIANTS
### Semantic Classification Principles
- The Isolation Rule: Evaluate each chunk as if the rest of the document does not exist. A chunk is `SELF_CONTAINED` if and only if it is completely self-sufficient — read entirely on its own, it conveys an unambiguous, actionable truth that does not depend on any unstated information.
- Dependency & Borrowed Meaning: A chunk is `REQUIRES_EXTERNAL_CONTEXT` whenever it relies on borrowed meaning. Read on its own, it is incomplete or risks causing incorrect actions without the context it relies upon.
- Boundary Guardrail: Arguing that "the document provides the context", "the context is clear from the document", or "the topic was already introduced" is an explicit admission that the chunk is `REQUIRES_EXTERNAL_CONTEXT`.
- Presumption of Dependency: Continuous text chunks are presumed to require context. Classifying a chunk as `SELF_CONTAINED` carries the burden of proof in `justification` to demonstrate total local autonomy.

### Topological & Finality Contracts
- Edge Topology: `SELF_CONTAINED` chunks must possess exactly zero outgoing relation edges. `REQUIRES_EXTERNAL_CONTEXT` chunks must possess at least one directed outgoing edge anchored directly to the chunk that resolves the dependency.
- Two-Tier Finality Gate:
  1. Chunk Finalization: A chunk transitions to `REVIEWED` via `stg_finalize_chunks` exclusively after explicit textual inspection (`inspected`), semantic classification, and topological edge consistency are satisfied.
  2. Session Commitment: The staging session transitions to `AGENT_COMMITTED` via `stg_commit` exclusively after pre-flight validation (`stg_validate`) confirms zero topological or integrity violations."""


def render_server_instructions(
    manifest_block: str | None = None,
) -> str:
    """Renders complete server instructions combining static protocol and dynamic manifest."""
    if not manifest_block or not manifest_block.strip():
        return STATIC_SERVER_INSTRUCTIONS.strip()
    return f"{STATIC_SERVER_INSTRUCTIONS.strip()}\n\n{manifest_block.strip()}"


CORPUS_SERVER_INSTRUCTIONS = render_server_instructions()


def create_default_corpus_mcp_tools(
    embedding_engine: QueryEmbedder | None = None,
    reranker: CorpusReranker | None = None,
) -> CorpusMCPTools:
    """Composition root factory explicitly assembling runtime sensors and staging tools via pure DI."""
    from rag_eval.ingestion.staging.manager import StagingManager
    from rag_eval.retrieval.reranker import CrossEncoderReranker

    embedder = embedding_engine or SentenceTransformerQueryEmbedder()
    re_rank = reranker or CrossEncoderReranker()
    staging_mgr = StagingManager()
    sensors = CorpusRuntimeSensors(embedding_engine=embedder, reranker=re_rank)
    staging = CorpusStagingTools(staging_manager=staging_mgr)
    return CorpusMCPTools(sensors=sensors, staging=staging)


def create_corpus_mcp_server(
    tools: CorpusMCPTools | None = None,
    manifest_block: str | None = None,
) -> MCPServer:
    """Builds and configures the official MCP MCPServer instance with all canonical tools."""
    tool_impl = tools if tools is not None else create_default_corpus_mcp_tools()

    rendered_manifest = manifest_block
    if rendered_manifest is None:
        try:
            import asyncio

            loop = asyncio.get_event_loop()
            if not loop.is_running():
                rendered_manifest = loop.run_until_complete(tool_impl.build_dynamic_corpus_manifest())
                from rag_eval.db.connection import close_db_pool
                loop.run_until_complete(close_db_pool())
                tool_impl.sensors._pool = None
        except (RuntimeError, OSError, ValueError) as exc:
            logger.debug("Could not build dynamic corpus manifest: %s", exc)

    instructions_text = render_server_instructions(manifest_block=rendered_manifest)
    server = MCPServer(
        SERVER_NAME,
        version=SERVER_VERSION,
        description="RAG Corpus Model Context Protocol Server",
        instructions=instructions_text,
    )
    register_mcp_tools(server=server, tool_impl=tool_impl)
    return server


def map_domain_error_to_jsonrpc(err: CorpusDomainError) -> tuple[int, str, dict[str, object]]:
    """Maps internal domain errors to strict JSON-RPC 2.0 error specifications."""
    if err.error_code < 0:
        code = err.error_code
    elif err.error_code in (E_AST_GROUNDING_VALIDATION, E_INVALID_DOCUMENT_HIERARCHY):
        code = -32602
    else:
        code = -32603
    data = {"domain_code": err.error_code, **err.data}
    return code, err.message, data


class CorpusMCPServer:
    """Wrapper providing direct execution, JSON-RPC bridge, and SDK lifecycle management."""

    def __init__(self, tools: CorpusMCPTools | None = None) -> None:
        self.tools = tools if tools is not None else create_default_corpus_mcp_tools()
        self.mcp_server = create_corpus_mcp_server(self.tools)

    async def get_instructions(self) -> str:
        manifest = await self.tools.build_dynamic_corpus_manifest()
        return render_server_instructions(manifest_block=manifest)

    async def get_tool_definitions(self) -> list[dict[str, object]]:
        tool_objs = await self.mcp_server.list_tools()
        return [
            {
                "name": t.name,
                "description": t.description or "",
                "inputSchema": t.input_schema,
                "parameters": t.input_schema,
            }
            for t in tool_objs
        ]

    async def execute_tool(self, name: str, args: dict[str, object]) -> dict[str, object]:
        canonical_name = name.removeprefix("mcp_corpus_")
        logger.info("[TOOL] START name=%s (canonical=%s) args=%s", name, canonical_name, args)
        try:
            res = await self.mcp_server.call_tool(canonical_name, args)
        except Exception as exc:
            cause = getattr(exc, "__cause__", None) or exc
            if isinstance(cause, CorpusDomainError):
                raise cause from exc
            logger.error("[TOOL] ERROR name=%s: %s", canonical_name, exc)
            raise CorpusDomainError(
                error_code=E_CORPUS_INTEGRITY_VIOLATION,
                message=str(cause),
                data={"tool": canonical_name, "error": str(cause)},
            ) from exc

        if isinstance(res, CallToolResult) and res.is_error:
            err_msg = "\n".join(
                c.text for c in res.content if isinstance(c, TextContent)
            )
            logger.error("[TOOL] ERROR name=%s: %s", canonical_name, err_msg)

            err_code = E_AST_GROUNDING_VALIDATION
            err_data: dict[str, object] | None = None
            try:
                parsed = json.loads(err_msg)
                if isinstance(parsed, dict):
                    raw_code = parsed.get("error_code") or parsed.get("code")
                    if isinstance(raw_code, int):
                        err_code = raw_code
                    if isinstance(parsed.get("data"), dict):
                        err_data = parsed["data"]
                    if "message" in parsed and isinstance(parsed["message"], str):
                        err_msg = parsed["message"]
            except (json.JSONDecodeError, ValueError):
                pass

            raise CorpusDomainError(
                error_code=err_code,
                message=err_msg or f"Error executing tool '{canonical_name}'",
                data=err_data or {"tool": canonical_name},
            )
        if isinstance(res, CallToolResult):
            for item in res.content:
                if isinstance(item, TextContent):
                    try:
                        parsed = json.loads(item.text)
                        logger.info("[TOOL] SUCCESS name=%s", canonical_name)
                        if isinstance(parsed, dict):
                            return parsed
                        return {"result": parsed}
                    except (json.JSONDecodeError, ValueError):
                        logger.info("[TOOL] SUCCESS name=%s (raw text)", canonical_name)
                        return {"result": item.text}
        logger.info("[TOOL] SUCCESS name=%s (empty)", canonical_name)
        return {}

    async def handle_request_dict(self, req: dict[str, object]) -> dict[str, object] | None:
        if not isinstance(req, dict) or req.get("jsonrpc") != "2.0":
            return {
                "jsonrpc": "2.0",
                "id": req.get("id") if isinstance(req, dict) else None,
                "error": {"code": -32600, "message": "Invalid JSON-RPC 2.0 request"},
            }

        req_id = req.get("id")
        method = str(req.get("method") or "")
        params = req.get("params") or {}
        logger.info("[JSON-RPC] >>> method=%s id=%s", method, req_id)

        try:
            if method == "initialize":
                dyn_instructions = await self.get_instructions()
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {
                            "name": SERVER_NAME,
                            "version": SERVER_VERSION,
                        },
                        "instructions": dyn_instructions,
                    },
                }
            if method == "notifications/initialized":
                return None
            if method == "ping":
                return {"jsonrpc": "2.0", "id": req_id, "result": {}}
            if method == "tools/list":
                defs = await self.get_tool_definitions()
                return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": defs}}
            if method == "tools/call":
                if not isinstance(params, dict):
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {
                            "code": -32602,
                            "message": "params must be a JSON object",
                        },
                    }
                t_name = str(params.get("name", ""))
                t_args = params.get("arguments", {})
                if not isinstance(t_args, dict):
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {
                            "code": -32602,
                            "message": "arguments must be a JSON object",
                        },
                    }
                out = await self.execute_tool(t_name, t_args)
                return {"jsonrpc": "2.0", "id": req_id, "result": out}

            all_tool_names = {t.name for t in await self.mcp_server.list_tools()}
            clean_method = method.removeprefix("mcp_corpus_")
            if clean_method in all_tool_names:
                args = params if isinstance(params, dict) else {}
                out = await self.execute_tool(clean_method, args)
                return {"jsonrpc": "2.0", "id": req_id, "result": out}

            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }

        except CorpusDomainError as err:
            code, message, data = map_domain_error_to_jsonrpc(err)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": code,
                    "message": message,
                    "data": data,
                },
            }
        except MCPError as err:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": err.code,
                    "message": err.message,
                    "data": err.data,
                },
            }
        except Exception as exc:
            logger.exception("Error handling request")
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32603, "message": str(exc)},
            }

    def run(self, transport: str = "stdio") -> None:
        logger.info("[RUN] Starting MCPServer transport='%s' (pid=%d, ppid=%d)...", transport, os.getpid(), os.getppid())
        try:
            self.mcp_server.run(transport=transport)  # type: ignore
            logger.info("[RUN] MCPServer transport='%s' finished cleanly.", transport)
        except Exception:
            logger.exception("[RUN] MCPServer transport='%s' exited with exception", transport)
            raise


def run_mcp_server(log_file: str | None = None) -> None:
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handler = FlushingFileHandler(str(log_path), encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] (pid=%(process)d) %(name)s: %(message)s"))
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        root_logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    logger.info("=== MCP SERVER PROCESS LAUNCHED ===")
    logger.info("PID: %d | PPID: %d | CWD: %s", os.getpid(), os.getppid(), os.getcwd())
    logger.info("Command line: %s", sys.argv)
    logger.info("Python: %s", sys.executable)

    def _sig_handler(signum: int, frame: object) -> None:
        signame = signal.Signals(signum).name if signum in signal.Signals.__members__.values() else str(signum)
        logger.warning("[SIGNAL] Caught signal %s (%d) on pid=%d, ppid=%d. Unwinding cleanly...", signame, signum, os.getpid(), os.getppid())
        for h in list(logger.handlers) + list(logging.getLogger().handlers):
            h.flush()
        sys.exit(0)

    try:
        signal.signal(signal.SIGTERM, _sig_handler)
        signal.signal(signal.SIGINT, _sig_handler)
        if hasattr(signal, "SIGHUP"):
            signal.signal(signal.SIGHUP, _sig_handler)
        logger.info("[SIGNALS] Registered SIGTERM, SIGINT, SIGHUP handlers.")
    except (ValueError, OSError) as exc:
        logger.warning("[SIGNALS] Could not register signal handlers: %s", exc)

    def _on_exit() -> None:
        logger.info("[EXIT] atexit hook triggered for pid=%d.", os.getpid())
        for h in list(logger.handlers) + list(logging.getLogger().handlers):
            h.flush()

    atexit.register(_on_exit)

    server = CorpusMCPServer()
    try:
        server.run(transport="stdio")
    except (KeyboardInterrupt, SystemExit):
        logger.info("[SHUTDOWN] MCPServer exited via signal or exit request.")
    finally:
        try:
            import asyncio

            from rag_eval.db.connection import close_db_pool

            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(close_db_pool())
                else:
                    loop.run_until_complete(close_db_pool())
            except (RuntimeError, OSError) as exc:
                logger.debug("Event loop not available for pool close: %s, running asyncio.run", exc)
                asyncio.run(close_db_pool())
        except (RuntimeError, OSError, ValueError) as exc:
            logger.debug("Failed closing db pool on shutdown: %s", exc)
        for h in list(logger.handlers) + list(logging.getLogger().handlers):
            h.flush()
