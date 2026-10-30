from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from rag_eval.db.connection import close_db_pool, get_db_pool
from rag_eval.db.repositories import CorpusRepository
from rag_eval.exceptions import CorpusDomainError
from rag_eval.mcp.server import CorpusMCPServer
from rag_eval.mcp.tools.answer import (
    CitationInput,
    CorpusAnswerTools,
    DefaultPathAnswerValidator,
    GroundedCitationDTO,
    ValidatedAnswerPayload,
)
from rag_eval.web.app import create_app


@pytest.mark.asyncio
async def test_submit_grounded_answer_disabled_by_default() -> None:
    """By default, CorpusMCPServer must only expose the 5 canonical tools."""
    try:
        server = CorpusMCPServer()
        defs = await server.get_tool_definitions()
        tool_names = [str(d["name"]) for d in defs]
        assert "submit_grounded_answer" not in tool_names
        assert len(tool_names) == 5

        instructions = await server.get_instructions()
        assert "submit_grounded_answer" not in instructions
    finally:
        await close_db_pool()


@pytest.mark.asyncio
async def test_submit_grounded_answer_enabled_and_validates_paths(tmp_path: Path) -> None:
    """When enable_answer_tool=True, submit_grounded_answer validates LTree paths against PostgreSQL."""
    output_file = tmp_path / "submitted_answer.json"
    try:
        pool = await get_db_pool()
        repo = CorpusRepository(pool)
        docs = await repo.documents.list_active()
        assert docs, "Expected active documents in PostgreSQL test corpus"
        chunks = await repo.chunks.list_by_document(docs[0].id)
        assert chunks, "Expected chunks in first document"
        valid_chunk = chunks[0]

        emitted_events: list[tuple[str, dict[str, object]]] = []

        async def _capture_event(event_type: str, data: dict[str, object]) -> None:
            emitted_events.append((event_type, data))

        server = CorpusMCPServer(
            enable_answer_tool=True,
            answer_output_path=output_file,
            event_emitter=_capture_event,
        )
        defs = await server.get_tool_definitions()
        tool_names = [str(d["name"]) for d in defs]
        assert "submit_grounded_answer" in tool_names
        assert len(tool_names) == 6

        instructions = await server.get_instructions()
        assert "submit_grounded_answer" in instructions

        # 1. Valid path submission succeeds and enriches citation from DB
        res = await server.execute_tool(
            "submit_grounded_answer",
            {
                "answer": "Nội dung trả lời được trích dẫn trực tiếp [#1].",
                "citations": [{"path": valid_chunk.path}],
                "abstained": False,
            },
        )
        assert res["accepted"] is True
        assert res["abstained"] is False
        assert "[#1]" in str(res["answer"])
        citations = res["citations"]
        assert isinstance(citations, list) and len(citations) == 1
        first_cite = citations[0]
        assert first_cite["path"] == valid_chunk.path
        assert first_cite["doc_slug"] == docs[0].doc_slug
        assert first_cite["verbatim_text"] == valid_chunk.verbatim_text

        event_names = [e[0] for e in emitted_events]
        assert "tool_start" in event_names
        assert "tool_done" in event_names
        assert "answer_submitted" in event_names

        # Verify answer_output_path was written
        assert output_file.exists()
        persisted = json.loads(output_file.read_text(encoding="utf-8"))
        assert persisted["citations"][0]["path"] == valid_chunk.path

        # 2. Non-existent path is rejected by DefaultPathAnswerValidator
        with pytest.raises(CorpusDomainError) as exc_info:
            await server.execute_tool(
                "submit_grounded_answer",
                {
                    "answer": "Câu trả lời dẫn nguồn không tồn tại.",
                    "citations": [{"path": "nonexistent_doc.fake_section.chunk_999"}],
                },
            )
        assert "PATH_NOT_FOUND" in str(exc_info.value.data)

        # 3. Missing citations when abstained=False is rejected
        with pytest.raises(CorpusDomainError) as exc_info_missing:
            await server.execute_tool(
                "submit_grounded_answer",
                {
                    "answer": "Câu trả lời không có nguồn.",
                    "citations": [],
                    "abstained": False,
                },
            )
        assert "MISSING_CITATIONS" in str(exc_info_missing.value.data)

        # 4. Dangling citation marker [#2] when only 1 citation is provided is rejected
        with pytest.raises(CorpusDomainError) as exc_info_dangling:
            await server.execute_tool(
                "submit_grounded_answer",
                {
                    "answer": "Câu trả lời trích dẫn vượt phạm vi [#1] và [#2].",
                    "citations": [{"path": valid_chunk.path}],
                    "abstained": False,
                },
            )
        assert "DANGLING_CITATION_MARKER" in str(exc_info_dangling.value.data)

        # 5. Abstained answer with empty citations succeeds
        abstained_res = await server.execute_tool(
            "submit_grounded_answer",
            {
                "answer": "Kho tài liệu không có thông tin này.",
                "citations": [],
                "abstained": True,
            },
        )
        assert abstained_res["accepted"] is True
        assert abstained_res["abstained"] is True
        assert abstained_res["citations"] == []
    finally:
        await close_db_pool()


@pytest.mark.asyncio
async def test_decoupled_custom_answer_validator() -> None:
    """Verify AnswerValidator protocol allows swapping validation logic without modifying CorpusAnswerTools."""

    class CustomPrefixValidator:
        async def validate_and_enrich(
            self,
            repo: CorpusRepository,
            answer: str,
            citations: list[CitationInput],
            abstained: bool = False,
        ) -> ValidatedAnswerPayload:
            if not answer.startswith("[VERIFIED]"):
                DefaultPathAnswerValidator._raise_violations(
                    [
                        # Custom rule enforcement
                        __import__(
                            "rag_eval.mcp.tools.answer",
                            fromlist=["AnswerValidationViolation"],
                        ).AnswerValidationViolation(
                            violation_code="CUSTOM_PREFIX_REQUIRED",
                            path=None,
                            message="Answer must start with [VERIFIED]",
                        )
                    ]
                )
            return ValidatedAnswerPayload(
                answer=answer,
                abstained=abstained,
                citations=[
                    GroundedCitationDTO(
                        index=1,
                        path=citations[0].path if citations else "custom.path",
                        doc_slug="custom",
                        doc_title="Custom Doc",
                        start_line=1,
                        end_line=2,
                        verbatim_text="verbatim",
                        contextualized_text="context",
                    )
                ],
            )

    try:
        tools = CorpusAnswerTools(validator=CustomPrefixValidator())
        with pytest.raises(CorpusDomainError) as exc_info:
            await tools.submit_grounded_answer(
                answer="Thiếu tiền tố",
                citations=["custom.path"],
            )
        assert exc_info.value.data.get("violation_code") == "CUSTOM_PREFIX_REQUIRED"

        ok = await tools.submit_grounded_answer(
            answer="[VERIFIED] Hợp lệ",
            citations=["custom.path"],
        )
        assert ok.accepted is True
        assert ok.citations[0].path == "custom.path"
    finally:
        await close_db_pool()


def test_webhook_and_websocket_broadcast() -> None:
    """Verify /api/qa/webhook broadcasts live events to /api/qa/ws clients."""
    app = create_app()
    with TestClient(app) as client, client.websocket_connect("/api/qa/ws") as ws:
        hello = ws.receive_json()
        assert hello["event"] == "ws_connected"

        resp = client.post(
            "/api/qa/webhook",
            json={
                "event": "tool_start",
                "session_id": "sess-123",
                "tool": "hybrid_search",
                "args": {"query": "test", "pattern": "test"},
            },
        )
        assert resp.status_code == 200
        assert resp.json()["delivered"] >= 1

        pushed = ws.receive_json()
        assert pushed["event"] == "tool_start"
        assert pushed["tool"] == "hybrid_search"
        assert pushed["session_id"] == "sess-123"

        providers_resp = client.get("/api/answer/providers")
        assert providers_resp.status_code == 200
        providers_list = providers_resp.json()
        assert isinstance(providers_list, list)
        assert any(p["id"] == "agy" for p in providers_list)

        eval_resp = client.get("/api/eval/cases")
        assert eval_resp.status_code == 200
        eval_cases = eval_resp.json()
        assert isinstance(eval_cases, list)
        assert len(eval_cases) == 100

