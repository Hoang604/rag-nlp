from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import signal
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, cast

from rag_eval.db.repositories import CorpusRepository
from rag_eval.mcp.tools.answer import (
    AnswerValidator,
    CitationInput,
    DefaultPathAnswerValidator,
    GroundedCitationDTO,
    SubmitGroundedAnswerResult,
    normalize_citation_inputs,
)
from rag_eval.retrieval.engine import RetrievalEngine

Provider = Literal["agy", "claude", "codex"]
PROVIDERS: tuple[Provider, ...] = ("agy", "claude", "codex")
AGENT_PROVIDERS: tuple[Provider, ...] = ("agy", "claude")
PROVIDER_LABELS: dict[Provider, str] = {
    "agy": "Antigravity (Gemini 3.8 Flash)",
    "claude": "Claude Code",
    "codex": "Codex",
}
AGY_MODEL = "gemini-3.8-flash-high"
AGY_AGENT_NAME = "corpus-assistant"
MCP_SERVER_NAME = "docs"
MCP_ALLOWED_TOOLS = (
    f"mcp__{MCP_SERVER_NAME}__hybrid_search,"
    f"mcp__{MCP_SERVER_NAME}__hierarchical_navigate,"
    f"mcp__{MCP_SERVER_NAME}__graph_traverse,"
    f"mcp__{MCP_SERVER_NAME}__get_raw,"
    f"mcp__{MCP_SERVER_NAME}__submit_grounded_answer"
)
_REPO_ROOT = Path(__file__).resolve().parents[2]
_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


@dataclass(frozen=True)
class CitedSource:
    index: int
    path: str
    doc_slug: str
    doc_title: str
    start_line: int
    end_line: int
    verbatim_text: str
    contextualized_text: str
    citation_text: str | None = None


@dataclass(frozen=True)
class ComposedAnswer:
    question: str
    provider: Provider
    answer: str
    abstained: bool
    citations: list[CitedSource] = field(default_factory=list)
    retrieval_ms: float = 0.0
    llm_ms: float = 0.0
    total_ms: float = 0.0


def available_providers() -> list[tuple[Provider, str, bool]]:
    return [(p, PROVIDER_LABELS[p], shutil.which(p) is not None) for p in PROVIDERS]


def _resolve_executable(provider: Provider) -> str:
    exe = shutil.which(provider)
    if exe is None:
        raise RuntimeError(
            f"Không tìm thấy lệnh `{provider}` trong PATH. "
            f"Cài đặt {PROVIDER_LABELS[provider]} CLI trước khi gọi."
        )
    return exe


def _build_compose_prompt(
    question: str,
    sources: list[dict[str, object]],
) -> str:
    blocks = "\n\n".join(
        f"[{s['index']}] path={s['path']} | doc={s['doc_slug']} ({s['doc_title']}) | L{s['start_line']}-{s['end_line']}\n"
        f"{s['contextualized_text']}"
        for s in sources
    )
    return (
        "Bạn là trợ lý tra cứu kho tài liệu. Chỉ sử dụng các đoạn nguồn được đánh số dưới đây "
        "để trả lời câu hỏi bằng tiếng Việt. Không suy diễn ngoài văn bản.\n\n"
        "Quy tắc bắt buộc:\n"
        "- Mọi khẳng định phải gắn ký hiệu `[#i]` ở cuối câu (ví dụ `[#1]`, `[#2]`) tương ứng với đoạn nguồn `[i]`.\n"
        "- Trả lời duy nhất một JSON object hợp lệ (không markdown, không ```json```), theo schema:\n"
        '  {"answer": "<câu trả lời có [#i]>", "abstained": false, '
        '"citations": [{"path": "<path của đoạn nguồn đã dùng>"}]}\n'
        "- Nếu các đoạn nguồn không chứa thông tin trả lời câu hỏi, trả về:\n"
        '  {"answer": "Kho tài liệu hiện tại không có thông tin để trả lời câu hỏi này.", '
        '"abstained": true, "citations": []}\n\n'
        f"Các đoạn nguồn:\n{blocks}\n\n"
        f"Câu hỏi: {question}\n"
        "JSON:"
    )


def _build_agent_prompt(question: str, doc_slugs: list[str] | None) -> str:
    scope = (
        f"Chỉ tra cứu trong các tài liệu có doc_slug thuộc: {', '.join(doc_slugs)}.\n"
        if doc_slugs
        else ""
    )
    return (
        "Bạn là trợ lý tra cứu kho tài liệu. Hãy dùng các công cụ MCP (`hybrid_search`, "
        "`hierarchical_navigate`, `graph_traverse`, `get_raw`) để tìm căn cứ trả lời câu hỏi dưới đây, "
        "sau đó BẮT BUỘC gọi công cụ `submit_grounded_answer` ở bước cuối cùng để nộp câu trả lời.\n"
        "- Nếu kết quả công cụ dài bị hệ thống lưu ra file tạm trong `~/.gemini/antigravity-cli/`, "
        "dùng `view_file` đọc đúng đường dẫn đó; tuyệt đối không đọc bất kỳ file nào khác trong dự án.\n"
        f"{scope}"
        "- Khi gọi `submit_grounded_answer`:\n"
        "  + Truyền `answer` bằng tiếng Việt, gắn ký hiệu `[#1]`, `[#2]`, ... tương ứng với thứ tự trong `citations`.\n"
        "  + Truyền `citations` là danh sách các đường dẫn LTree `path` thực tế lấy từ kết quả công cụ (ví dụ `[{\"path\": \"...\"}]`).\n"
        "  + Nếu kho tài liệu không có thông tin trả lời, gọi `submit_grounded_answer` với `abstained=True` và `citations=[]`.\n"
        "  + Nếu `submit_grounded_answer` báo lỗi xác thực `path`, hãy kiểm tra lại `path` từ kết quả truy xuất và gọi lại `submit_grounded_answer`.\n\n"
        f"Câu hỏi: {question}"
    )


def _mcp_server_command_and_args(
    *,
    answer_output_file: Path,
    webhook_url: str | None,
    session_id: str | None,
) -> tuple[str, list[str]]:
    rag_bin = Path(sys.executable).with_name("rag-eval")
    command = str(rag_bin) if rag_bin.exists() else sys.executable
    args = (
        ["server"]
        if rag_bin.exists()
        else ["-m", "rag_eval.cli", "server"]
    )
    args.extend(
        [
            "--log-file",
            str(_REPO_ROOT / "logs" / "mcp_server.log"),
            "--enable-answer-tool",
            "--answer-output",
            str(answer_output_file),
        ]
    )
    if webhook_url:
        args.extend(["--webhook-url", webhook_url])
    if session_id:
        args.extend(["--session-id", session_id])
    return command, args


def _derive_api_base_url(webhook_url: str | None) -> str | None:
    if not webhook_url:
        return os.environ.get("RAG_API_URL")
    marker = "/api/qa/webhook"
    if marker in webhook_url:
        return webhook_url.split(marker, 1)[0]
    return os.environ.get("RAG_API_URL")


def _agent_command(
    provider: Provider,
    executable: str,
    workdir: Path,
    prompt: str,
    *,
    answer_output_file: Path,
    webhook_url: str | None = None,
    session_id: str | None = None,
) -> list[str]:
    command, args = _mcp_server_command_and_args(
        answer_output_file=answer_output_file,
        webhook_url=webhook_url,
        session_id=session_id,
    )
    api_base_url = _derive_api_base_url(webhook_url)
    stdio_server_cfg: dict[str, object] = {
        "command": command,
        "args": args,
    }
    if api_base_url:
        stdio_server_cfg["env"] = {"RAG_API_URL": api_base_url}

    mcp_payload: dict[str, object] = {
        "mcpServers": {
            MCP_SERVER_NAME: stdio_server_cfg
        }
    }
    if provider == "claude":
        mcp_config = workdir / "mcp.json"
        mcp_config.write_text(json.dumps(mcp_payload), encoding="utf-8")
        return [
            executable,
            "-p",
            "--mcp-config",
            str(mcp_config),
            "--strict-mcp-config",
            "--allowedTools",
            MCP_ALLOWED_TOOLS,
            "--tools",
            "",
            "--setting-sources",
            "user",
            "--permission-mode",
            "dontAsk",
            "--no-session-persistence",
            "--output-format",
            "stream-json",
            "--verbose",
            "--max-turns",
            "10",
            prompt,
        ]
    if provider == "agy":
        agents_dir = workdir / ".agents" / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        src_agent = _REPO_ROOT / ".agents" / "agents" / f"{AGY_AGENT_NAME}.md"
        if src_agent.exists():
            shutil.copyfile(src_agent, agents_dir / src_agent.name)
        else:
            (agents_dir / f"{AGY_AGENT_NAME}.md").write_text(
                f"---\nname: {AGY_AGENT_NAME}\ndescription: Trợ lý tra cứu kho tài liệu.\n"
                "tools:\n  - view_file\nsubagent: false\nmainAgent: true\nmodel: inherit\n---\n\n"
                "Bạn là trợ lý tra cứu kho tài liệu. Luôn gọi `submit_grounded_answer` ở bước cuối cùng.\n",
                encoding="utf-8",
            )
        if api_base_url and os.environ.get("RAG_AGY_TRANSPORT", "http").strip().lower() != "stdio":
            import urllib.parse

            query_params: dict[str, str] = {
                "enable_answer_tool": "true",
                "answer_output": str(answer_output_file),
            }
            if session_id:
                query_params["session_id"] = session_id
            mcp_http_url = f"{api_base_url.rstrip('/')}/api/mcp?{urllib.parse.urlencode(query_params)}"
            agy_mcp_payload: dict[str, object] = {
                "mcpServers": {
                    MCP_SERVER_NAME: {
                        "url": mcp_http_url,
                    }
                }
            }
        else:
            agy_mcp_payload = mcp_payload

        (workdir / ".agents" / "mcp_config.json").write_text(
            json.dumps(agy_mcp_payload),
            encoding="utf-8",
        )
        return [
            executable,
            "--agent",
            AGY_AGENT_NAME,
            "--model",
            AGY_MODEL,
            "--disable-slash-commands",
            "--output-format",
            "json",
            "--print-timeout",
            "300s",
            f"-p={prompt}",
        ]
    raise RuntimeError(f"Provider `{provider}` không hỗ trợ chế độ Agent MCP.")


async def _run_agent(
    provider: Provider,
    question: str,
    doc_slugs: list[str] | None,
    *,
    webhook_url: str | None = None,
    session_id: str | None = None,
    timeout: float = 300.0,
) -> tuple[str, SubmitGroundedAnswerResult | None]:
    executable = _resolve_executable(provider)
    prompt = _build_agent_prompt(question, doc_slugs)

    with tempfile.TemporaryDirectory(prefix="rag-agent-") as tmp:
        workdir = Path(tmp)
        stdout_file = workdir / "stdout.txt"
        stderr_file = workdir / "stderr.txt"
        answer_output_file = workdir / "submitted_answer.json"

        cmd = _agent_command(
            provider,
            executable,
            workdir,
            prompt,
            answer_output_file=answer_output_file,
            webhook_url=webhook_url,
            session_id=session_id,
        )
        env = {
            **os.environ,
            "RAG_ENABLE_ANSWER_TOOL": "1",
            "RAG_ANSWER_OUTPUT": str(answer_output_file),
        }
        api_base_url = _derive_api_base_url(webhook_url)
        if api_base_url:
            env["RAG_API_URL"] = api_base_url
        if webhook_url:
            env["RAG_WEBHOOK_URL"] = webhook_url
        if session_id:
            env["RAG_SESSION_ID"] = session_id

        with stdout_file.open("wb") as out_fh, stderr_file.open("wb") as err_fh:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=out_fh,
                stderr=err_fh,
                cwd=str(workdir),
                env=env,
                start_new_session=True,
            )
            try:
                await asyncio.wait_for(process.wait(), timeout=timeout)
            except TimeoutError as exc:
                _kill_process_group(process.pid)
                await process.wait()
                raise RuntimeError(
                    f"`{provider}` vượt quá thời gian chờ {int(timeout)}s."
                ) from exc
            finally:
                _kill_process_group(process.pid)

        out = stdout_file.read_text(encoding="utf-8", errors="replace").strip()
        err = stderr_file.read_text(encoding="utf-8", errors="replace").strip()

        submitted: SubmitGroundedAnswerResult | None = None
        if answer_output_file.exists():
            try:
                raw_submitted = json.loads(answer_output_file.read_text(encoding="utf-8"))
                submitted = SubmitGroundedAnswerResult.model_validate(raw_submitted)
            except (json.JSONDecodeError, ValueError):
                submitted = None

    if submitted is not None:
        return out, submitted

    if process.returncode != 0:
        detail = err or out or f"exit code {process.returncode}"
        raise RuntimeError(f"`{provider}` thất bại: {detail[:500]}")
    if not out:
        raise RuntimeError(f"`{provider}` trả về kết quả rỗng.")
    return out, None


async def _run_cli_compose(
    provider: Provider,
    prompt: str,
    timeout: float = 180.0,
) -> str:
    executable = _resolve_executable(provider)
    with tempfile.TemporaryDirectory(prefix="rag-llm-") as tmp:
        workdir = Path(tmp)
        stdout_file = workdir / "stdout.txt"
        stderr_file = workdir / "stderr.txt"
        if provider == "claude":
            cmd = [
                executable,
                "-p",
                "--tools",
                "",
                "--setting-sources",
                "user",
                "--no-session-persistence",
                "--output-format",
                "text",
            ]
            stdin_bytes: bytes | None = prompt.encode("utf-8")
        elif provider == "codex":
            out_path = workdir / "last.txt"
            cmd = [
                executable,
                "exec",
                "--skip-git-repo-check",
                "--sandbox",
                "read-only",
                "--ephemeral",
                "--color",
                "never",
                "-o",
                str(out_path),
                "-",
            ]
            stdin_bytes = prompt.encode("utf-8")
        elif provider == "agy":
            cmd = [
                executable,
                "--mode",
                "ask",
                "--model",
                AGY_MODEL,
                "--disable-mcps",
                "--disable-slash-commands",
                "--output-format",
                "json",
                "--print-timeout",
                f"{int(timeout)}s",
                f"-p={prompt}",
            ]
            stdin_bytes = None
        else:
            raise ValueError(f"Unsupported provider: {provider}")

        with stdout_file.open("wb") as out_fh, stderr_file.open("wb") as err_fh:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=(
                    asyncio.subprocess.DEVNULL
                    if stdin_bytes is None
                    else asyncio.subprocess.PIPE
                ),
                stdout=out_fh,
                stderr=err_fh,
                cwd=str(workdir),
                start_new_session=True,
            )
            try:
                if stdin_bytes is not None and process.stdin is not None:
                    process.stdin.write(stdin_bytes)
                    await process.stdin.drain()
                    process.stdin.close()
                await asyncio.wait_for(process.wait(), timeout=timeout)
            except TimeoutError as exc:
                _kill_process_group(process.pid)
                await process.wait()
                raise RuntimeError(
                    f"`{provider}` vượt quá thời gian chờ {int(timeout)}s."
                ) from exc
            finally:
                _kill_process_group(process.pid)

        out = stdout_file.read_text(encoding="utf-8", errors="replace").strip()
        err = stderr_file.read_text(encoding="utf-8", errors="replace").strip()
        if provider == "codex" and (workdir / "last.txt").exists():
            out = (workdir / "last.txt").read_text(encoding="utf-8", errors="replace").strip()

    if process.returncode != 0:
        detail = err or out or f"exit code {process.returncode}"
        raise RuntimeError(f"`{provider}` thất bại: {detail[:500]}")
    if provider == "agy":
        return _unwrap_agy_envelope(out)
    return out


def _kill_process_group(pid: int) -> None:
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def _unwrap_agy_envelope(raw: str) -> str:
    for line in reversed(raw.splitlines()):
        s = line.strip()
        if not (s.startswith("{") and s.endswith("}")):
            continue
        try:
            obj = json.loads(s)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        if obj.get("is_error") is True:
            raise RuntimeError(f"`agy` báo lỗi: {str(obj.get('result') or s)[:500]}")
        res = obj.get("result")
        if isinstance(res, str) and res.strip():
            return res.strip()
    return raw


def _extract_json_object(raw: str) -> dict[str, object] | None:
    text = raw.strip()
    m = _FENCE_RE.search(text)
    if m:
        text = m.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        obj = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return cast(dict[str, object], obj) if isinstance(obj, dict) else None


def _extract_agent_payload(provider: Provider, raw: str) -> dict[str, object] | None:
    if provider == "agy":
        return _extract_json_object(_unwrap_agy_envelope(raw))
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    for ln in reversed(lines):
        try:
            ev = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if not isinstance(ev, dict):
            continue
        if ev.get("type") == "result":
            result_text = str(ev.get("result") or "")
            parsed = _extract_json_object(result_text)
            if parsed is not None:
                return parsed
    return _extract_json_object(raw)


def _to_cited_sources(dtos: list[GroundedCitationDTO]) -> list[CitedSource]:
    return [
        CitedSource(
            index=d.index,
            path=d.path,
            doc_slug=d.doc_slug,
            doc_title=d.doc_title,
            start_line=d.start_line,
            end_line=d.end_line,
            verbatim_text=d.verbatim_text,
            contextualized_text=d.contextualized_text,
            citation_text=d.citation_text,
        )
        for d in dtos
    ]


async def compose(
    engine: RetrievalEngine,
    repo: CorpusRepository,
    question: str,
    provider: Provider,
    *,
    limit: int = 8,
    doc_slugs: list[str] | None = None,
    validator: AnswerValidator | None = None,
) -> ComposedAnswer:
    """Chế độ Retrieve + Compose: truy xuất top chunks trước rồi gọi CLI tổng hợp và xác thực qua AnswerValidator."""
    active_validator = validator if validator is not None else DefaultPathAnswerValidator()
    t0 = time.perf_counter()

    search_res = await engine.search_venn(
        query=question,
        pattern=question[:120],
        limit=limit,
        rerank=False,
        doc_slugs=doc_slugs or None,
    )
    retrieval_ms = (time.perf_counter() - t0) * 1000.0

    flat_paths: list[str] = []
    for grp in search_res.groups:
        for prov in grp.provisions:
            if prov.path not in flat_paths:
                flat_paths.append(prov.path)
            if len(flat_paths) >= limit:
                break
        if len(flat_paths) >= limit:
            break

    if not flat_paths:
        return ComposedAnswer(
            question=question,
            provider=provider,
            answer="Không tìm thấy đoạn tài liệu phù hợp trong kho dữ liệu.",
            abstained=True,
            citations=[],
            retrieval_ms=round(retrieval_ms, 1),
            llm_ms=0.0,
            total_ms=round(retrieval_ms, 1),
        )

    query = """
    SELECT
        c.path::text AS path,
        c.verbatim_text,
        c.contextualized_text,
        c.start_line,
        c.end_line,
        d.doc_slug,
        d.title AS doc_title
    FROM chunks c
    JOIN documents d ON d.id = c.document_id
    WHERE c.path = ANY($1::ltree[]);
    """
    async with repo.chunks._connection_scope() as conn:
        rows = await conn.fetch(query, flat_paths)
    by_path = {str(r["path"]): r for r in rows}

    source_blocks: list[dict[str, object]] = []
    for idx, p in enumerate(flat_paths, start=1):
        row = by_path.get(p)
        if row is None:
            continue
        source_blocks.append(
            {
                "index": idx,
                "path": str(row["path"]),
                "doc_slug": str(row["doc_slug"]),
                "doc_title": str(row["doc_title"]),
                "start_line": int(row["start_line"]),
                "end_line": int(row["end_line"]),
                "verbatim_text": str(row["verbatim_text"]),
                "contextualized_text": str(row["contextualized_text"]),
            }
        )

    prompt = _build_compose_prompt(question, source_blocks)
    t_llm = time.perf_counter()
    raw = await _run_cli_compose(provider, prompt)
    llm_ms = (time.perf_counter() - t_llm) * 1000.0

    parsed = _extract_json_object(raw)
    if parsed is None:
        raise RuntimeError(
            f"`{provider}` không trả về JSON hợp lệ theo schema yêu cầu: {raw[:300]}"
        )

    ans_text = str(parsed.get("answer") or "").strip()
    abstained = bool(parsed.get("abstained"))
    raw_cites = parsed.get("citations")
    cite_inputs = normalize_citation_inputs(
        cast(list[CitationInput | str | dict[str, object]], raw_cites)
        if isinstance(raw_cites, list)
        else None
    )

    validated = await active_validator.validate_and_enrich(
        repo=repo,
        answer=ans_text,
        citations=cite_inputs,
        abstained=abstained,
    )
    total_ms = (time.perf_counter() - t0) * 1000.0
    return ComposedAnswer(
        question=question,
        provider=provider,
        answer=validated.answer,
        abstained=validated.abstained,
        citations=_to_cited_sources(validated.citations),
        retrieval_ms=round(retrieval_ms, 1),
        llm_ms=round(llm_ms, 1),
        total_ms=round(total_ms, 1),
    )


async def answer_with_agent(
    repo: CorpusRepository,
    question: str,
    provider: Provider = "agy",
    *,
    doc_slugs: list[str] | None = None,
    webhook_url: str | None = None,
    session_id: str | None = None,
    validator: AnswerValidator | None = None,
) -> ComposedAnswer:
    """Chế độ Agent MCP: khởi chạy CLI agent (`agy` / `claude`) với MCP server bật `submit_grounded_answer`."""
    if provider not in AGENT_PROVIDERS:
        raise ValueError(
            f"Chế độ Agent MCP chỉ hỗ trợ {', '.join(AGENT_PROVIDERS)} (nhận `{provider}`)."
        )
    active_validator = validator if validator is not None else DefaultPathAnswerValidator()
    t0 = time.perf_counter()
    raw, submitted = await _run_agent(
        provider=provider,
        question=question,
        doc_slugs=doc_slugs,
        webhook_url=webhook_url,
        session_id=session_id,
    )
    total_ms = (time.perf_counter() - t0) * 1000.0

    if submitted is not None:
        return ComposedAnswer(
            question=question,
            provider=provider,
            answer=submitted.answer,
            abstained=submitted.abstained,
            citations=_to_cited_sources(submitted.citations),
            retrieval_ms=0.0,
            llm_ms=round(total_ms, 1),
            total_ms=round(total_ms, 1),
        )

    payload = _extract_agent_payload(provider, raw)
    if payload is not None:
        ans_text = str(payload.get("answer") or "").strip()
        abstained = bool(payload.get("abstained"))
        raw_cites = payload.get("citations")
        cite_inputs = normalize_citation_inputs(
            cast(list[CitationInput | str | dict[str, object]], raw_cites)
            if isinstance(raw_cites, list)
            else None
        )
        validated = await active_validator.validate_and_enrich(
            repo=repo,
            answer=ans_text,
            citations=cite_inputs,
            abstained=abstained,
        )
        return ComposedAnswer(
            question=question,
            provider=provider,
            answer=validated.answer,
            abstained=validated.abstained,
            citations=_to_cited_sources(validated.citations),
            retrieval_ms=0.0,
            llm_ms=round(total_ms, 1),
            total_ms=round(total_ms, 1),
        )

    raise RuntimeError(
        f"Agent `{provider}` kết thúc mà không gọi công cụ `submit_grounded_answer` "
        f"và không trả về payload hợp lệ."
    )
