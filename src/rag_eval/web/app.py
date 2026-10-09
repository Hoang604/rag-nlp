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

from rag_eval.db.connection import close_db_pool, get_db_pool
from rag_eval.exceptions import CorpusDomainError
from rag_eval.web.router import router

logger = logging.getLogger(__name__)


def create_app(
    db_pool: asyncpg.Pool | None = None,
    static_dir: Path | str | None = None,
) -> FastAPI:
    """Constructs and configures the Corpus Knowledge Observatory FastAPI application."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """Manages application startup and shutdown lifecycle (database pools, caches)."""
        logger.info("Initializing Corpus Knowledge Observatory Web Backend...")

        if db_pool is not None:
            app.state.pool = db_pool
        else:
            try:
                app.state.pool = await get_db_pool()
            except (RuntimeError, OSError, asyncpg.PostgresError) as exc:
                logger.warning("Database pool initialization deferred/offline: %s", exc)
                app.state.pool = None

        app.state.retrieval_engine = None
        if app.state.pool is not None:
            try:
                from rag_eval.retrieval.embedder import SentenceTransformerQueryEmbedder
                from rag_eval.retrieval.engine import RetrievalEngine
                from rag_eval.retrieval.reranker import CrossEncoderReranker

                embedder = SentenceTransformerQueryEmbedder()
                await embedder.embed_query("khởi động")

                reranker = CrossEncoderReranker(max_length=256)
                await reranker.warm()

                app.state.retrieval_engine = RetrievalEngine(
                    pool=app.state.pool,
                    embedder=embedder,
                    reranker=reranker,
                )
                logger.info("Retrieval engine warm.")
            except (RuntimeError, OSError, ImportError, ValueError) as exc:
                logger.warning("Retrieval warm-up skipped: %s", exc)

        yield

        logger.info("Shutting down Corpus Knowledge Observatory Web Backend...")
        if db_pool is None and app.state.pool is not None:
            await close_db_pool()

    app = FastAPI(
        title="Corpus Knowledge Observatory API",
        description="FastAPI Backend Service for Corpus Knowledge Graph and Hierarchy Observatory",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.pool = db_pool

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5173",
            "http://localhost:5173",
            "http://127.0.0.1:8000",
            "http://localhost:8000",
        ],
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

    target_static = Path(static_dir) if static_dir else Path("frontend/dist")
    if target_static.exists() and target_static.is_dir():
        logger.info("Mounting SPA static files from %s", target_static)
        assets_dir = target_static / "assets"
        if assets_dir.exists() and assets_dir.is_dir():
            app.mount(
                "/assets", StaticFiles(directory=assets_dir), name="assets"
            )

        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str) -> Response:
            if full_path == "api" or full_path.startswith("api/"):
                return JSONResponse(status_code=404, content={"detail": "Not Found"})
            resolved_static = target_static.resolve()
            file_path = (target_static / full_path).resolve()
            if not file_path.is_relative_to(resolved_static):
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Forbidden: Path traversal detected"},
                )
            if file_path.is_file():
                return FileResponse(file_path)
            if Path(full_path).suffix:
                return JSONResponse(
                    status_code=404, content={"detail": "Asset not found"}
                )
            index_path = target_static / "index.html"
            if index_path.exists():
                return FileResponse(index_path)
            return JSONResponse(
                status_code=404, content={"message": "Frontend not found"}
            )

    return app
