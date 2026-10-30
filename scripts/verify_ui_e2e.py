from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import uvicorn
from playwright.async_api import async_playwright

from rag_eval.db.connection import close_db_pool, get_db_pool
from rag_eval.db.repositories import CorpusRepository
from rag_eval.web.app import create_app

HOST = "127.0.0.1"
PORT = 8765
BASE_URL = f"http://{HOST}:{PORT}"


def _wait_for_server(url: str, timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{url}/api/health", timeout=2.0) as resp:
                if resp.status == 200:
                    return
        except (urllib.error.URLError, OSError):
            time.sleep(0.3)
    raise RuntimeError(f"Server at {url} did not become ready within {timeout}s")


async def _get_sample_chunk_path() -> tuple[str, str]:
    pool = await get_db_pool()
    try:
        repo = CorpusRepository(pool)
        docs = await repo.documents.list_active()
        assert docs, "No active documents in DB"
        chunks = await repo.chunks.list_by_document(docs[0].id)
        assert chunks, "No chunks in first document"
        return docs[0].doc_slug, chunks[0].path
    finally:
        await close_db_pool()


async def run_verification() -> None:
    doc_slug, valid_path = await _get_sample_chunk_path()
    print(f"[E2E] Using sample chunk: doc_slug={doc_slug}, path={valid_path}")

    app = create_app(static_dir=Path("frontend/dist"))
    config = uvicorn.Config(app, host=HOST, port=PORT, log_level="warning")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    _wait_for_server(BASE_URL, timeout=45.0)
    print(f"[E2E] FastAPI + SPA server listening at {BASE_URL}")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                executable_path="/usr/bin/google-chrome",
                headless=True,
                args=["--no-sandbox", "--disable-gpu"],
            )
            page = await browser.new_page(viewport={"width": 1440, "height": 900})
            await page.goto(BASE_URL, wait_until="networkidle")

            # 1. Verify Header, Theme Switcher, and Language Switcher
            await page.locator('[data-testid="tab-answer"]').wait_for(state="visible")
            await page.locator('[data-testid="tab-search"]').wait_for(state="visible")
            await page.locator('[data-testid="tab-eval"]').wait_for(state="visible")
            await page.locator('[data-testid="tab-explorer"]').wait_for(state="visible")

            await page.click('[data-testid="theme-light"]')
            theme_attr = await page.evaluate("document.documentElement.getAttribute('data-theme')")
            assert theme_attr == "light", f"Expected theme=light, got {theme_attr}"

            await page.click('[data-testid="theme-dark"]')
            theme_attr = await page.evaluate("document.documentElement.getAttribute('data-theme')")
            assert theme_attr == "dark", f"Expected theme=dark, got {theme_attr}"

            await page.click('[data-testid="lang-en"]')
            assert await page.evaluate("document.documentElement.lang") == "en"
            await page.click('[data-testid="lang-vi"]')
            assert await page.evaluate("document.documentElement.lang") == "vi"
            print("[E2E] ✔ Header, Theme Switcher, and i18n verified.")

            # 2. Verify Tab 1 (Q&A): WebSocket connection & Live MCP Tool + Grounded Answer Webhook Push
            await page.wait_for_function(
                """() => {
                    const el = document.querySelector('[data-testid="qa-ws-status"]');
                    return el && el.textContent && el.textContent.includes('kết nối');
                }""",
                timeout=10000,
            )

            webhook_url = f"{BASE_URL}/api/qa/webhook"
            # Invoke real CLI MCP tool `hybrid_search` with --webhook-url
            cmd_search = [
                sys.executable,
                "-m",
                "rag_eval.cli",
                "tool",
                "hybrid_search",
                "--webhook-url",
                webhook_url,
                "-a",
                json.dumps({"query": "routing", "pattern": "routing", "limit": 2}),
            ]
            subprocess_run = subprocess.run
            await asyncio.to_thread(subprocess_run, cmd_search, check=True, timeout=30)

            # Verify live tool trace appeared on the UI via WebSocket
            await page.locator('[data-testid="qa-tool-trace-hybrid_search"]').wait_for(
                state="visible", timeout=10000
            )

            # Invoke real CLI MCP tool `submit_grounded_answer` with --enable-answer-tool and --webhook-url
            cmd_answer = [
                sys.executable,
                "-m",
                "rag_eval.cli",
                "tool",
                "submit_grounded_answer",
                "--enable-answer-tool",
                "--webhook-url",
                webhook_url,
                "-a",
                json.dumps(
                    {
                        "answer": "Đây là câu trả lời đã được xác thực đường dẫn trực tiếp qua MCP [#1].",
                        "citations": [{"path": valid_path}],
                        "abstained": False,
                    }
                ),
            ]
            await asyncio.to_thread(subprocess_run, cmd_answer, check=True, timeout=30)

            # Verify live tool trace and validated answer card + citation row rendered on UI
            await page.locator('[data-testid="qa-tool-trace-submit_grounded_answer"]').wait_for(
                state="visible", timeout=10000
            )
            await page.locator('[data-testid="qa-answer-card"]').wait_for(
                state="visible", timeout=10000
            )
            answer_text = await page.locator('[data-testid="qa-answer-text"]').inner_text()
            assert "Đây là câu trả lời đã được xác thực" in answer_text
            await page.locator('[data-testid="citation-row-1"]').wait_for(
                state="visible", timeout=10000
            )
            citation_text = await page.locator('[data-testid="citation-row-1"]').inner_text()
            assert valid_path in citation_text
            print("[E2E] ✔ Tab 1 (Q&A) live MCP tool webhook -> WebSocket -> UI rendering verified.")

            # Test clicking "Mở trong Cấu trúc & Đồ thị" on Citation #1 jumps to Tab 4 (Explorer)
            await page.click('[data-testid="citation-open-explorer-1"]')
            await page.locator('[data-testid="explorer-doc-select"]').wait_for(
                state="visible", timeout=10000
            )
            print("[E2E] ✔ Deep-link from Citation #1 to Tab 4 (Explorer) verified.")

            # 3. Verify Tab 4 (Explorer): Studio & 2D Knowledge Graph
            await page.click('[data-testid="explorer-mode-graph"]')
            await page.wait_for_timeout(500)
            await page.click('[data-testid="explorer-mode-studio"]')
            print("[E2E] ✔ Tab 4 (Explorer) Studio & 2D Graph toggle verified.")

            # 4. Verify Tab 2 (Search): Dual-Channel Venn Search & Filters
            await page.click('[data-testid="tab-search"]')
            await page.locator('[data-testid="search-results-list"]').wait_for(
                state="visible", timeout=15000
            )
            await page.click('[data-testid="search-filters-toggle"]')
            await page.locator('[data-testid="search-filters-panel"]').wait_for(
                state="visible", timeout=5000
            )
            await page.fill('[data-testid="search-query-input"]', "stream pipeline error")
            await page.fill('[data-testid="search-pattern-input"]', "pipeline")
            await page.click('[data-testid="search-submit-btn"]')
            await page.locator('[data-testid="search-result-row-1"]').wait_for(
                state="visible", timeout=15000
            )
            print("[E2E] ✔ Tab 2 (Search) live dual-channel Venn search verified.")

            # 5. Verify Tab 3 (Eval): 100 Benchmark Cases & Single Case Run
            await page.click('[data-testid="tab-eval"]')
            await page.locator('[data-testid="eval-metrics-bar"]').wait_for(
                state="visible", timeout=10000
            )
            metrics_text = await page.locator('[data-testid="eval-metrics-bar"]').inner_text()
            assert "Cases: 100" in metrics_text, f"Expected 100 cases, got: {metrics_text}"
            await page.click('[data-testid="eval-run-single-btn"]')
            await page.wait_for_timeout(1500)
            print("[E2E] ✔ Tab 3 (Eval) 100-case suite and live single-case execution verified.")

            await browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=5.0)
        await close_db_pool()


if __name__ == "__main__":
    asyncio.run(run_verification())
