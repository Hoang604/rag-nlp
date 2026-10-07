import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import asyncpg
import httpx
import pytest
from fastapi import FastAPI

from rag_eval.ingestion.staging.manager import StagingManager
from rag_eval.ingestion.staging.models import (
    ChunkReviewStatus,
    ContextType,
    RelationType,
    StagingChunk,
    StagingChunkDelta,
    StagingEdge,
)
from rag_eval.retrieval.engine import RetrievalEngine, SearchPipelineResult
from rag_eval.schemas import SearchHitDTO
from rag_eval.web.app import create_app


@pytest.fixture
def test_app_and_manager(tmp_path: Path) -> tuple[FastAPI, StagingManager]:
    staging_dir = tmp_path / "staging_web"
    staging_dir.mkdir(parents=True, exist_ok=True)
    static_dir = tmp_path / "static_web"
    static_dir.mkdir(parents=True, exist_ok=True)
    (static_dir / "assets").mkdir(parents=True, exist_ok=True)
    (static_dir / "index.html").write_text("<html><body>SPA</body></html>", encoding="utf-8")

    app = create_app(staging_dir=staging_dir, static_dir=static_dir)
    mgr = app.state.staging_manager
    return app, mgr


@pytest.mark.asyncio
async def test_sub_resource_routes_precedence_over_detail_route(
    test_app_and_manager: tuple[FastAPI, StagingManager],
) -> None:
    """Verifies that /api/staging/{doc_slug}/wal and /replay are not shadowed by /api/staging/{doc_slug}."""
    app, mgr = test_app_and_manager
    doc_slug = "route_test_doc"

    mgr.create_session_from_raw(
        doc_slug=doc_slug,
        title="Route Test Doc",
        raw_text="Section 1. Content",
    )
    chunk = StagingChunk(
        path=f"{doc_slug}.sec_1",
        verbatim_text="Content 1",
        contextualized_text="Content 1",
        start_line=1,
        end_line=1,
    )
    mgr.patch_chunks(doc_slug=doc_slug, updated_chunks=[chunk])

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        # GET /wal must hit the WAL journal endpoint and return 200, not 400
        wal_resp = await client.get(f"/api/staging/{doc_slug}/wal")
        assert wal_resp.status_code == 200
        wal_data = wal_resp.json()
        assert isinstance(wal_data, list)
        assert len(wal_data) >= 1
        assert wal_data[0]["op_type"] == "GENESIS"

        # POST /replay must hit the replay endpoint and return 200
        replay_resp = await client.post(f"/api/staging/{doc_slug}/replay")
        assert replay_resp.status_code == 200
        replay_data = replay_resp.json()
        assert replay_data["doc_slug"] == doc_slug
        assert replay_data["status"] == "SUCCESS"
        assert replay_data["is_deterministic"] is True


@pytest.mark.asyncio
async def test_path_traversal_blocked(
    test_app_and_manager: tuple[FastAPI, StagingManager],
) -> None:
    """Verifies that directory traversal attacks via /api/static are blocked."""
    app, _ = test_app_and_manager
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        # Traversal attempts and missing static assets with extensions must return 403 or 404
        resp = await client.get("/%2e%2e/%2e%2e/pyproject.toml")
        assert resp.status_code in (403, 404)
        assert "dependencies" not in resp.text

        resp_asset = await client.get("/pyproject.toml")
        assert resp_asset.status_code in (403, 404)
        assert "dependencies" not in resp_asset.text


@pytest.mark.asyncio
async def test_delete_edge_via_query_parameters(
    test_app_and_manager: tuple[FastAPI, StagingManager],
) -> None:
    """Verifies that edge deletion works via HTTP DELETE with query parameters without request body."""
    app, mgr = test_app_and_manager
    doc_slug = "edge_test_doc"

    mgr.create_session_from_raw(
        doc_slug=doc_slug,
        title="Edge Test Doc",
        raw_text="Section 1. Content\nSection 2. Content",
    )
    chunks = [
        StagingChunk(
            path=f"{doc_slug}.sec_1",
            verbatim_text="Content 1",
            contextualized_text="Content 1",
            start_line=1,
            end_line=1,
        ),
        StagingChunk(
            path=f"{doc_slug}.sec_2",
            verbatim_text="Content 2",
            contextualized_text="Content 2",
            start_line=2,
            end_line=2,
        ),
    ]
    mgr.patch_chunks(doc_slug=doc_slug, updated_chunks=chunks)
    edges = [
        StagingEdge(
            source_path=f"{doc_slug}.sec_1",
            target_path=f"{doc_slug}.sec_2",
            relation_type=RelationType.REFERENCES,
        )
    ]
    mgr.add_edges(doc_slug=doc_slug, edges=edges)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        # Issue DELETE with query parameters and NO body
        del_resp = await client.delete(
            f"/api/staging/{doc_slug}/edges",
            params={
                "source_path": f"{doc_slug}.sec_1",
                "target_path": f"{doc_slug}.sec_2",
                "relation_type": "REFERENCES",
            },
        )
        assert del_resp.status_code == 200
        del_data = del_resp.json()
        assert del_data["status"] == "SUCCESS"

    # Verify edge was removed from session
    session = mgr.load_session(doc_slug)
    assert len(session.edges) == 0


@pytest.mark.asyncio
async def test_promotion_rejects_unreviewed_session(
    test_app_and_manager: tuple[FastAPI, StagingManager],
) -> None:
    """Verifies that promote_session fails fast if chunks have not been 100% reviewed."""
    app, mgr = test_app_and_manager
    doc_slug = "unreviewed_doc"

    mgr.create_session_from_raw(
        doc_slug=doc_slug,
        title="Unreviewed Doc",
        raw_text="Section 1. Content",
    )
    chunks = [
        StagingChunk(
            path=f"{doc_slug}.sec_1",
            verbatim_text="Content",
            contextualized_text="Content",
            start_line=1,
            end_line=1,
            review_status=ChunkReviewStatus.PENDING,
        )
    ]
    mgr.patch_chunks(doc_slug=doc_slug, updated_chunks=chunks)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        resp = await client.post(
            f"/api/staging/{doc_slug}/promote",
            json={"compute_embeddings": False},
        )
        # Must be rejected with 400
        assert resp.status_code == 400


@pytest.mark.asyncio
async def test_unfinalize_chunks_endpoint_and_path_validation(
    test_app_and_manager: tuple[FastAPI, StagingManager],
) -> None:
    """Verifies that /staging/{doc_slug}/unfinalize successfully reverts reviewed chunks and rejects non-existent paths."""
    app, mgr = test_app_and_manager
    doc_slug = "unfinalize_test_doc"

    session = mgr.create_session_from_raw(
        doc_slug=doc_slug,
        title="Unfinalize Test Doc",
        raw_text="Paragraph 1\n\nParagraph 2",
    )
    assert len(session.chunks) == 2
    chunk_1 = session.chunks[0].path
    chunk_2 = session.chunks[1].path
    deltas = [
        StagingChunkDelta(path=chunk_1, context_type=ContextType.SELF_CONTAINED),
        StagingChunkDelta(path=chunk_2, context_type=ContextType.SELF_CONTAINED),
    ]
    mgr.patch_chunks(doc_slug=doc_slug, updated_chunks=deltas)
    session = mgr.load_session(doc_slug)
    session.get_chunk(chunk_1)
    session.get_chunk(chunk_2)
    mgr.save_session(session)
    mgr.finalize_chunks(doc_slug=doc_slug, paths=[chunk_1, chunk_2])

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        # 1. Unfinalize chunk 1
        resp = await client.post(
            f"/api/staging/{doc_slug}/unfinalize",
            json={"paths": [chunk_1]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "SUCCESS"
        assert data["unfinalized_count"] == 1
        assert data["pending_remaining"] == 1

        # Verify session state
        session = mgr.load_session(doc_slug)
        c1 = next(c for c in session.chunks if c.path == chunk_1)
        c2 = next(c for c in session.chunks if c.path == chunk_2)
        assert c1.review_status == ChunkReviewStatus.PENDING
        assert c2.review_status == ChunkReviewStatus.REVIEWED

        # 2. Reject non-existent path
        bad_resp = await client.post(
            f"/api/staging/{doc_slug}/unfinalize",
            json={"paths": [f"{doc_slug}.non_existent"]},
        )
        assert bad_resp.status_code == 400


@pytest.mark.asyncio
async def test_search_corpus_endpoint_returns_ranking_floats(
    test_app_and_manager: tuple[FastAPI, StagingManager],
) -> None:
    """Verifies S-07 / I-07: POST /search executes through RetrievalEngine returning ranking floats."""
    app, _ = test_app_and_manager
    mock_pool = MagicMock(spec=asyncpg.Pool)
    mock_pool._closed = False
    app.state.pool = mock_pool

    mock_hit = SearchHitDTO(
        chunk_id=uuid.uuid4(),
        doc_slug="test_doc",
        doc_title="Test Document",
        path="test_doc.sec_1",
        verbatim_text="Sample text for testing search ranking",
        contextualized_text="Sample text for testing search ranking",
        start_line=10,
        end_line=20,
        context_type="SELF_CONTAINED",
        is_all_refs_resolved=True,
        metadata={"is_table": False},
        score=0.925,
        dense_similarity=0.880,
        sparse_rank=1,
        dense_rank=1,
        rerank_score=0.950,
    )
    mock_engine = MagicMock(spec=RetrievalEngine)
    mock_engine.search = AsyncMock(
        return_value=SearchPipelineResult(
            hits=[mock_hit],
            confidence="HIGH",
            expanded_query="sample query",
        )
    )
    app.state.retrieval_engine = mock_engine

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        resp = await client.post(
            "/api/search",
            json={"query": "sample query", "limit": 5, "rerank": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "sample query"
        assert data["confidence"] == "HIGH"
        assert len(data["hits"]) == 1

        hit_resp = data["hits"][0]
        assert hit_resp["path"] == "test_doc.sec_1"
        assert hit_resp["score"] == 0.925
        assert hit_resp["dense_similarity"] == 0.880
        assert hit_resp["rerank_score"] == 0.950
        assert hit_resp["keyword_matched"] is True

        mock_engine.search.assert_awaited_once_with(
            query="sample query",
            limit=5,
            rerank=True,
            doc_slugs=None,
            path_prefix=None,
            only_resolved=False,
        )

