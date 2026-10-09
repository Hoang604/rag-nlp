from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from rag_eval.web.app import create_app


@pytest.fixture
def test_app(tmp_path: Path) -> FastAPI:
    static_dir = tmp_path / "static_web"
    static_dir.mkdir(parents=True, exist_ok=True)
    (static_dir / "assets").mkdir(parents=True, exist_ok=True)
    (static_dir / "index.html").write_text("<html><body>SPA</body></html>", encoding="utf-8")

    return create_app(static_dir=static_dir)


@pytest.mark.asyncio
async def test_path_traversal_blocked(test_app: FastAPI) -> None:
    """Verifies that directory traversal attacks via static files are blocked."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=test_app),
        base_url="http://testserver",
    ) as client:
        resp = await client.get("/%2e%2e/%2e%2e/pyproject.toml")
        assert resp.status_code in (403, 404)
        assert "dependencies" not in resp.text

        resp_asset = await client.get("/pyproject.toml")
        assert resp_asset.status_code in (403, 404)
        assert "dependencies" not in resp_asset.text


@pytest.mark.asyncio
async def test_relations_fail_fast_without_pool(test_app: FastAPI) -> None:
    """Verifies that /api/relations raises 503 when db pool is not connected."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=test_app),
        base_url="http://testserver",
    ) as client:
        resp = await client.get("/api/relations")
        assert resp.status_code == 503


@pytest.mark.asyncio
async def test_traverse_fail_fast_without_pool(test_app: FastAPI) -> None:
    """Verifies that /api/documents/{doc_slug}/graph/traverse raises 503 when db pool is not connected."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=test_app),
        base_url="http://testserver",
    ) as client:
        resp = await client.post(
            "/api/documents/test_doc/graph/traverse",
            json={"source_path": "test_doc.p_1", "limit": 10},
        )
        assert resp.status_code == 503


@pytest.mark.asyncio
async def test_traverse_endpoint_validation_errors(test_app: FastAPI) -> None:
    """Verifies that invalid limit (e.g. limit > 100 or limit < 1) triggers 422 Unprocessable Entity."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=test_app),
        base_url="http://testserver",
    ) as client:
        resp_over = await client.post(
            "/api/documents/test_doc/graph/traverse",
            json={"source_path": "test_doc.p_1", "limit": 101},
        )
        assert resp_over.status_code == 422

        resp_under = await client.post(
            "/api/documents/test_doc/graph/traverse",
            json={"source_path": "test_doc.p_1", "limit": 0},
        )
        assert resp_under.status_code == 422


@pytest.mark.asyncio
async def test_link_endpoint_contract(test_app: FastAPI) -> None:
    """Verifies /api/documents/links accepts rationale in payload and fails fast with 503 when pool is None."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=test_app),
        base_url="http://testserver",
    ) as client:
        resp = await client.post(
            "/api/documents/links",
            json={
                "source_path": "test_doc.p_1",
                "target_path": "test_doc.p_2",
                "relation_type": "REFERENCES",
                "rationale": "Sample rationale for link",
            },
        )
        assert resp.status_code == 503


@pytest.mark.asyncio
async def test_api_v1_route_not_found(test_app: FastAPI) -> None:
    """Verifies that legacy /api/v1 prefix is not registered and returns 404."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=test_app),
        base_url="http://testserver",
    ) as client:
        resp = await client.get("/api/v1/relations")
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_search_endpoint_schema_contract(test_app: FastAPI) -> None:
    """Verifies that /api/search fails fast with 503 without pool and accepts clean payload."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=test_app),
        base_url="http://testserver",
    ) as client:
        resp = await client.post(
            "/api/search",
            json={"query": "test query", "limit": 5},
        )
        assert resp.status_code == 503


@pytest.mark.asyncio
async def test_corpus_grep_endpoint_contract(test_app: FastAPI) -> None:
    """Verifies that /api/corpus/grep fails fast with 503 without pool and accepts clean payload."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=test_app),
        base_url="http://testserver",
    ) as client:
        resp = await client.post(
            "/api/corpus/grep",
            json={"pattern": "quic", "limit": 10},
        )
        assert resp.status_code == 503


