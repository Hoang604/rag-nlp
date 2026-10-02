from __future__ import annotations

import atexit
import datetime
import json
import logging
import os
import signal
import sys
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.shared.exceptions import MCPError
from mcp.types import CallToolResult, TextContent

from rag_eval.legal.exceptions import CorpusDomainError
from rag_eval.legal.mcp.registry import register_mcp_tools
from rag_eval.legal.mcp.tools import (
    CorpusMCPTools,
    CorpusRuntimeSensors,
    CorpusStagingTools,
    QueryEmbedder,
    SentenceTransformerQueryEmbedder,
)

logger = logging.getLogger("rag_eval.legal.mcp.server")


class FlushingFileHandler(logging.FileHandler):
    """FileHandler that automatically flushes on every emit for immediate persistence."""

    def emit(self, record: logging.LogRecord) -> None:
        super().emit(record)
        self.flush()

SERVER_NAME = "rag-corpus-mcp"
SERVER_VERSION = "3.0.0"

STATIC_SERVER_INSTRUCTIONS = """# RAG CORPUS RETRIEVAL & STAGING PRINCIPLES

## 1. DATA MODEL
- HIERARCHICAL STRUCTURE: `Document -> Segment -> Sub-segment...` represented via PostgreSQL ltree dot-separated paths.
- LEAF NODE RETRIEVAL: Database indexes and retrieves chunks at leaf level with verbatim and contextualized text.

## 2. DUAL RETRIEVAL STRATEGY
When investigating questions or documents, emit parallel retrieval calls:
- `hybrid_search`: Dense semantic vector search + Sparse BM25 keyword matching via Reciprocal Rank Fusion (RRF).
- `verbatim_grep`: Deterministic exact string and POSIX regular expression matches via PostgreSQL trigram index.

## 3. STRICT CITATION & GROUNDING
- Every conclusion must be grounded explicitly in retrieved chunks with path citations.
- Tool responses are the single authoritative source of truth. If no chunks match the query, state absence clearly."""


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
) -> CorpusMCPTools:
    """Composition root factory explicitly assembling runtime sensors and staging tools via pure DI."""
    from rag_eval.legal.ingestion.staging.manager import StagingManager

    embedder = embedding_engine or SentenceTransformerQueryEmbedder()
    staging_mgr = StagingManager()
    sensors = CorpusRuntimeSensors(embedding_engine=embedder, staging_manager=staging_mgr)
    staging = CorpusStagingTools(staging_manager=staging_mgr)
    return CorpusMCPTools(sensors=sensors, staging=staging)


def create_corpus_mcp_server(
    tools: CorpusMCPTools | None = None,
    manifest_block: str | None = None,
) -> MCPServer:
    """Builds and configures the official MCP MCPServer instance with all canonical tools."""
    tool_impl = tools if tools is not None else create_default_corpus_mcp_tools()
    instructions_text = render_server_instructions(manifest_block=manifest_block)
    server = MCPServer(
        SERVER_NAME,
        version=SERVER_VERSION,
        description="RAG Corpus Model Context Protocol Server",
        instructions=instructions_text,
    )
    register_mcp_tools(server=server, tool_impl=tool_impl)
    return server


class CorpusMCPServer:
    """Wrapper providing direct execution, JSON-RPC bridge, and SDK lifecycle management."""

    def __init__(self, tools: CorpusMCPTools | None = None) -> None:
        self.tools = tools if tools is not None else create_default_corpus_mcp_tools()
        self.mcp_server = create_corpus_mcp_server(self.tools)

    async def get_instructions(self, as_of_date: datetime.date | None = None) -> str:
        manifest = await self.tools.build_dynamic_corpus_manifest(as_of_date=as_of_date)
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
        logger.info("[TOOL] START name=%s args=%s", name, args)
        res = await self.mcp_server.call_tool(name, args)
        if isinstance(res, CallToolResult) and res.is_error:
            err_msg = "\n".join(
                c.text for c in res.content if isinstance(c, TextContent)
            )
            logger.error("[TOOL] ERROR name=%s: %s", name, err_msg)
            raise CorpusDomainError(
                error_code=-32603,
                message=err_msg or f"Error executing tool '{name}'",
            )
        if isinstance(res, CallToolResult):
            for item in res.content:
                if isinstance(item, TextContent):
                    try:
                        parsed = json.loads(item.text)
                        logger.info("[TOOL] SUCCESS name=%s", name)
                        if isinstance(parsed, dict):
                            return parsed
                        return {"result": parsed}
                    except (json.JSONDecodeError, ValueError):
                        logger.info("[TOOL] SUCCESS name=%s (raw text)", name)
                        return {"result": item.text}
        logger.info("[TOOL] SUCCESS name=%s (empty)", name)
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
            if method in all_tool_names:
                args = params if isinstance(params, dict) else {}
                out = await self.execute_tool(method, args)
                return {"jsonrpc": "2.0", "id": req_id, "result": out}

            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }

        except (CorpusDomainError, MCPError) as err:
            code = err.error_code if isinstance(err, CorpusDomainError) else err.code
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": code,
                    "message": err.message,
                    "data": err.data,
                },
            }
        except (RuntimeError, ValueError, TypeError, KeyError, OSError) as exc:
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
        logger.addHandler(handler)

    logger.info("=== MCP SERVER PROCESS LAUNCHED ===")
    logger.info("PID: %d | PPID: %d | CWD: %s", os.getpid(), os.getppid(), os.getcwd())
    logger.info("Command line: %s", sys.argv)
    logger.info("Python: %s", sys.executable)

    def _sig_handler(signum: int, frame: object) -> None:
        signame = signal.Signals(signum).name if signum in signal.Signals.__members__.values() else str(signum)
        logger.warning("[SIGNAL] Caught signal %s (%d) on pid=%d, ppid=%d. Exiting cleanly with status 0...", signame, signum, os.getpid(), os.getppid())
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
    server.run(transport="stdio")
