from __future__ import annotations

import asyncio
import atexit
import datetime
import json
import logging
import os
import signal
import sys
import urllib.error
import urllib.request
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.shared.exceptions import MCPError
from mcp.types import CallToolResult, TextContent

from rag_eval.exceptions import (
    E_AST_GROUNDING_VALIDATION,
    E_CORPUS_INTEGRITY_VIOLATION,
    E_INVALID_DOCUMENT_HIERARCHY,
    CorpusDomainError,
)
from rag_eval.mcp.registry import WebhookEmitter, register_mcp_tools
from rag_eval.mcp.tools import (
    AnswerValidator,
    CorpusAnswerTools,
    CorpusMCPTools,
    CorpusRuntimeSensors,
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

STATIC_SERVER_INSTRUCTIONS = """# RAG CORPUS PROTOCOL & AGENT OPERATIONAL PLAYBOOK

## 1. MENTAL & TOPOLOGICAL MODEL
- HIERARCHY: Documents form a strict tree `Document -> Segment -> Sub-segment...` with dot-separated hierarchical paths (e.g. `doc_slug.sec_1.para_2`).
- KNOWLEDGE GRAPH: Directed relations interlink chunks across hierarchy boundaries to preserve cross-cutting semantic dependencies.
- LEAF INDEXING: Retrieval and curation operate on leaf chunks containing verbatim source text and contextualized ancestry text.

## 2. OPERATIONAL PLAYBOOK: WHEN TO USE WHICH TOOL
- Discovery & Search: Reach for `hybrid_search` when starting an investigation, seeking relevant topics, or locating anchor terms.
- Local Referential Deficit: Reach for `hierarchical_navigate` when an identified chunk requires surrounding context, ancestor headers, sibling flow, or descendant subtrees.
- Cross-Cutting Relationships: Reach for `graph_traverse` when following citation links across documents or exploring multi-hop architectural dependencies.
- Ground-Truth Verification: Reach for `get_raw` when inspecting raw unparsed documentation or source code lines without AST chunk boundaries.
- Knowledge Curation: Reach for `graph_curate_edges` when atomically adding grounded semantic links or removing superseded graph connections.

## 3. GROUNDING & AUTHORITATIVE CITATION CONTRACT
- Every claim, inference, or synthesis must be explicitly grounded in retrieved leaf chunks and cited via exact hierarchical paths.
- Tool responses are the sole source of truth. When no retrieved chunk grounds an answer, affirm the absence of data explicitly; never extrapolate or hallucinate ungrounded facts.
- Pure Path Addressing: All operations identify nodes and edges exclusively by hierarchical LTree dot-paths. Database internal UUIDs are completely abstracted."""

ANSWER_TOOL_INSTRUCTIONS = """## 4. GROUNDED ANSWER SUBMISSION (`submit_grounded_answer`)
- When answering a user question, you MUST call `submit_grounded_answer` as your final step so the server can validate every cited LTree `path` against PostgreSQL before delivering the response.
- Pass `answer` with inline markers `[#1]`, `[#2]`, ... and `citations` listing the corresponding retrieved LTree `path`s (or `abstained=True` if the corpus does not contain the answer).
- If `submit_grounded_answer` returns a validation error, correct the invalid `path` using retrieved tool results and invoke `submit_grounded_answer` again."""


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def render_server_instructions(
    manifest_block: str | None = None,
    *,
    enable_answer_tool: bool = False,
) -> str:
    """Renders complete server instructions combining static protocol and dynamic manifest."""
    base = STATIC_SERVER_INSTRUCTIONS.strip()
    if enable_answer_tool:
        base = f"{base}\n\n{ANSWER_TOOL_INSTRUCTIONS.strip()}"
    if not manifest_block or not manifest_block.strip():
        return base
    return f"{base}\n\n{manifest_block.strip()}"


def create_default_corpus_mcp_tools(
    embedding_engine: QueryEmbedder | None = None,
    reranker: CorpusReranker | None = None,
    answer_validator: AnswerValidator | None = None,
    answer_output_path: str | Path | None = None,
    pool: object | None = None,
) -> CorpusMCPTools:
    """Composition root factory explicitly assembling runtime sensors, enrichment, and answer tools via pure DI."""
    from typing import cast

    import asyncpg

    from rag_eval.mcp.tools.enrichment import CorpusEnrichmentTools
    from rag_eval.retrieval.reranker import CrossEncoderReranker

    typed_pool = cast(asyncpg.Pool | None, pool)
    embedder = embedding_engine or SentenceTransformerQueryEmbedder()
    re_rank = reranker or CrossEncoderReranker()
    sensors = CorpusRuntimeSensors(
        pool=typed_pool,
        embedding_engine=embedder,
        reranker=re_rank,
    )
    enrichment = CorpusEnrichmentTools(pool=typed_pool)
    resolved_output = answer_output_path or os.environ.get("RAG_ANSWER_OUTPUT")
    answer_tools = CorpusAnswerTools(
        validator=answer_validator,
        pool=typed_pool,
        answer_output_path=resolved_output,
    )
    return CorpusMCPTools(sensors=sensors, enrichment=enrichment, answer_tools=answer_tools)


def create_corpus_mcp_server(
    tools: CorpusMCPTools | None = None,
    manifest_block: str | None = None,
    *,
    enable_answer_tool: bool | None = None,
    answer_output_path: str | Path | None = None,
    event_emitter: WebhookEmitter | None = None,
) -> MCPServer:
    """Builds and configures the official MCP MCPServer instance with all canonical tools."""
    resolved_enable = (
        enable_answer_tool
        if enable_answer_tool is not None
        else _env_flag("RAG_ENABLE_ANSWER_TOOL", default=False)
    )
    tool_impl = (
        tools
        if tools is not None
        else create_default_corpus_mcp_tools(answer_output_path=answer_output_path)
    )
    if answer_output_path is not None:
        tool_impl.answer_tools.answer_output_path = Path(answer_output_path)

    rendered_manifest = manifest_block
    if rendered_manifest is None:
        try:
            loop = asyncio.get_event_loop()
            if not loop.is_running():
                rendered_manifest = loop.run_until_complete(tool_impl.build_dynamic_corpus_manifest())
                from rag_eval.db.connection import close_db_pool
                loop.run_until_complete(close_db_pool())
                tool_impl.sensors._pool = None
        except (RuntimeError, OSError, ValueError) as exc:
            logger.debug("Could not build dynamic corpus manifest: %s", exc)

    instructions_text = render_server_instructions(
        manifest_block=rendered_manifest,
        enable_answer_tool=resolved_enable,
    )
    server = MCPServer(
        SERVER_NAME,
        version=SERVER_VERSION,
        description="RAG Corpus Model Context Protocol Server",
        instructions=instructions_text,
    )
    register_mcp_tools(
        server=server,
        tool_impl=tool_impl,
        enable_answer_tool=resolved_enable,
        event_emitter=event_emitter,
    )
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


def _json_default(obj: object) -> object:
    from pydantic import BaseModel

    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    return str(obj)


def _post_webhook_sync(url: str, payload: dict[str, object]) -> None:
    try:
        body = json.dumps(payload, ensure_ascii=False, default=_json_default).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            resp.read()
    except (urllib.error.URLError, OSError, ValueError) as exc:
        logger.debug("Webhook POST to %s failed (ignored): %s", url, exc)


class CorpusMCPServer:
    """Wrapper providing direct execution, JSON-RPC bridge, webhook emission, and SDK lifecycle management."""

    def __init__(
        self,
        tools: CorpusMCPTools | None = None,
        *,
        enable_answer_tool: bool | None = None,
        webhook_url: str | None = None,
        answer_output_path: str | Path | None = None,
        session_id: str | None = None,
        event_emitter: WebhookEmitter | None = None,
    ) -> None:
        self.enable_answer_tool = (
            enable_answer_tool
            if enable_answer_tool is not None
            else _env_flag("RAG_ENABLE_ANSWER_TOOL", default=False)
        )
        self.webhook_url = (webhook_url or os.environ.get("RAG_WEBHOOK_URL") or "").strip() or None
        self.answer_output_path = (
            str(answer_output_path)
            if answer_output_path is not None
            else (os.environ.get("RAG_ANSWER_OUTPUT") or "").strip() or None
        )
        self.session_id = (session_id or os.environ.get("RAG_SESSION_ID") or "").strip() or None
        self.tools = (
            tools
            if tools is not None
            else create_default_corpus_mcp_tools(answer_output_path=self.answer_output_path)
        )
        if self.answer_output_path is not None:
            self.tools.answer_tools.answer_output_path = Path(self.answer_output_path)
        self.mcp_server = create_corpus_mcp_server(
            self.tools,
            enable_answer_tool=self.enable_answer_tool,
            answer_output_path=self.answer_output_path,
            event_emitter=event_emitter or self._emit_webhook,
        )

    async def _emit_webhook(self, event_type: str, data: dict[str, object]) -> None:
        if not self.webhook_url:
            return
        payload: dict[str, object] = {
            "event": event_type,
            "session_id": self.session_id,
            "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
            **data,
        }
        await asyncio.to_thread(_post_webhook_sync, self.webhook_url, payload)

    async def get_instructions(self) -> str:
        manifest = await self.tools.build_dynamic_corpus_manifest()
        return render_server_instructions(
            manifest_block=manifest,
            enable_answer_tool=self.enable_answer_tool,
        )

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
        try:
            res = await self.mcp_server.call_tool(name, args)
        except ToolError as exc:
            cause = getattr(exc, "__cause__", None) or exc
            if isinstance(cause, CorpusDomainError):
                raise cause from exc
            raise CorpusDomainError(
                error_code=E_AST_GROUNDING_VALIDATION,
                message=str(exc),
                data={"tool": name, "error": str(exc)},
            ) from exc
        except Exception as exc:
            cause = getattr(exc, "__cause__", None) or exc
            if isinstance(cause, CorpusDomainError):
                raise cause from exc
            if isinstance(cause, ToolError):
                raise CorpusDomainError(
                    error_code=E_AST_GROUNDING_VALIDATION,
                    message=str(cause),
                    data={"tool": name, "error": str(cause)},
                ) from exc
            logger.error("[TOOL] ERROR name=%s: %s", name, exc)
            from pydantic import ValidationError

            err_code = (
                E_AST_GROUNDING_VALIDATION
                if isinstance(cause, (ValidationError, ValueError, TypeError, ToolError))
                or "validation error" in str(cause).lower()
                else E_CORPUS_INTEGRITY_VIOLATION
            )
            raise CorpusDomainError(
                error_code=err_code,
                message=str(cause),
                data={"tool": name, "error": str(cause)},
            ) from exc

        if isinstance(res, CallToolResult) and res.is_error:
            err_msg = "\n".join(
                c.text for c in res.content if isinstance(c, TextContent)
            )
            logger.error("[TOOL] ERROR name=%s: %s", name, err_msg)

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
                message=err_msg or f"Error executing tool '{name}'",
                data=err_data or {"tool": name},
            )
        if isinstance(res, CallToolResult):
            for item in res.content:
                if isinstance(item, TextContent):
                    try:
                        parsed = json.loads(item.text)
                        return parsed if isinstance(parsed, dict) else {"result": parsed}
                    except (json.JSONDecodeError, ValueError):
                        return {"result": item.text}
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


def run_mcp_server(
    log_file: str | None = None,
    *,
    enable_answer_tool: bool | None = None,
    webhook_url: str | None = None,
    answer_output_path: str | None = None,
    session_id: str | None = None,
) -> None:
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

    server = CorpusMCPServer(
        enable_answer_tool=enable_answer_tool,
        webhook_url=webhook_url,
        answer_output_path=answer_output_path,
        session_id=session_id,
    )
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
