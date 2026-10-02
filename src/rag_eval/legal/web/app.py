from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import asyncpg
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from rag_eval.legal.db.connection import close_db_pool, get_db_pool
from rag_eval.legal.exceptions import CorpusDomainError
from rag_eval.legal.ingestion.staging import DEFAULT_STAGING_DIR, StagingManager
from rag_eval.legal.web.router import router

logger = logging.getLogger(__name__)


def create_app(
    staging_dir: Path | str = DEFAULT_STAGING_DIR,
    db_pool: asyncpg.Pool | None = None,
    static_dir: Path | str | None = None,
) -> FastAPI:
    """Constructs and configures the RAG Corpus Staging Reviewer FastAPI application."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """Manages application startup and shutdown lifecycle (database pools, caches)."""
        logger.info("Initializing RAG Corpus Staging Reviewer Web Backend...")
        app.state.staging_manager = StagingManager(staging_dir=staging_dir)

        if db_pool is not None:
            app.state.pool = db_pool
        else:
            try:
                app.state.pool = await get_db_pool()
            except (RuntimeError, OSError, asyncpg.PostgresError) as exc:
                logger.warning("Database pool initialization deferred/offline: %s", exc)
                app.state.pool = None

        app.state.search_tools = None
        if app.state.pool is not None:
            try:
                from rag_eval.legal.mcp.tools import (
                    CorpusMCPTools,
                    SentenceTransformerQueryEmbedder,
                )

                embedder = SentenceTransformerQueryEmbedder()
                await embedder.embed_query("khởi động")

                from rag_eval.legal.retrieval.reranker import CrossEncoderReranker

                reranker = CrossEncoderReranker(max_length=256)
                await reranker.warm()

                app.state.search_tools = CorpusMCPTools.build(
                    pool=app.state.pool,
                    embedding_engine=embedder,
                    reranker=reranker,
                    rerank_by_default=True,
                )
                logger.info("Retrieval engine warm.")
            except (RuntimeError, OSError, ImportError, ValueError) as exc:
                logger.warning("Retrieval warm-up skipped: %s", exc)

        yield

        logger.info("Shutting down RAG Corpus Staging Reviewer Web Backend...")
        if db_pool is None and app.state.pool is not None:
            await close_db_pool()

    app = FastAPI(
        title="RAG Corpus Staging Reviewer API",
        description="FastAPI Backend Service for Human-in-the-Loop Corpus Staging and Promotion",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.staging_manager = StagingManager(staging_dir=staging_dir)
    app.state.pool = db_pool

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(CorpusDomainError)
    async def corpus_domain_error_handler(
        request: Request, exc: CorpusDomainError
    ) -> JSONResponse:
        logger.warning(
            "CorpusDomainError handled: %s (code: %d)", exc.message, exc.error_code
        )
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": exc.error_code,
                    "message": exc.message,
                    "data": exc.data,
                }
            },
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"error": {"code": -32602, "message": str(exc)}},
        )

    app.include_router(router, prefix="/api")
    app.include_router(router, prefix="/api/v1")

    target_static = Path(static_dir) if static_dir else Path("frontend/dist")
    if target_static.exists() and target_static.is_dir():
        logger.info("Mounting SPA static files from %s", target_static)
        app.mount(
            "/assets", StaticFiles(directory=target_static / "assets"), name="assets"
        )

        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str) -> Response:
            if full_path == "api" or full_path.startswith("api/"):
                return JSONResponse(status_code=404, content={"detail": "Not Found"})
            file_path = target_static / full_path
            if file_path.is_file():
                return FileResponse(file_path)
            index_path = target_static / "index.html"
            if index_path.exists():
                return FileResponse(index_path)
            return JSONResponse(
                status_code=404, content={"message": "Frontend not found"}
            )

    return app
