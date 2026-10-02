from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg

from rag_eval.db.repositories.base import BaseRepository
from rag_eval.db.repositories.chunks import ChunkRepository
from rag_eval.db.repositories.context_refs import ChunkContextRefRepository
from rag_eval.db.repositories.documents import DocumentRepository
from rag_eval.db.repositories.graph import GraphRepository

__all__ = [
    "BaseRepository",
    "ChunkContextRefRepository",
    "ChunkRepository",
    "CorpusRepository",
    "DocumentRepository",
    "GraphRepository",
]


class CorpusRepository:
    """Consolidated Data Access Membrane Layer aggregating all corpus domain repositories."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool
        self.documents = DocumentRepository(pool)
        self.chunks = ChunkRepository(pool)
        self.graph = GraphRepository(pool)
        self.context_refs = ChunkContextRefRepository(pool)

    @property
    def pool(self) -> asyncpg.Pool:
        return self._pool

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[asyncpg.Connection]:
        """Provides an atomic transaction across repositories."""
        async with self._pool.acquire() as conn, conn.transaction():
            yield conn
