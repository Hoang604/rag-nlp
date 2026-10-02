from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg

from rag_eval.legal.exceptions import (
    E_STORAGE_CONNECTION,
    CorpusDomainError,
)

logger = logging.getLogger(__name__)


class BaseRepository:
    """Base repository encapsulating connection lifecycle, transactions, and error translation."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[asyncpg.Connection]:
        """Provides an atomic transaction scope on an acquired connection."""
        async with self._pool.acquire() as conn, conn.transaction():
            yield conn

    @asynccontextmanager
    async def _connection_scope(
        self, conn: asyncpg.Connection | None = None
    ) -> AsyncIterator[asyncpg.Connection]:
        """Yields the provided active connection or borrows one from the pool."""
        if conn is not None:
            yield conn
        else:
            async with self._pool.acquire() as acquired:
                yield acquired

    def _translate_error(self, operation: str, exc: Exception) -> CorpusDomainError:
        """Translates raw asyncpg/system errors into typed domain exceptions."""
        logger.error("Database operation '%s' failed: %s", operation, exc)
        return CorpusDomainError(
            error_code=E_STORAGE_CONNECTION,
            message=f"Database operation '{operation}' failed: {exc}",
            data={"operation": operation, "original_error": str(exc)},
        )

    @staticmethod
    def _parse_metadata(raw: dict[str, object] | str | None) -> dict[str, object]:
        if isinstance(raw, dict):
            return dict(raw)
        if isinstance(raw, str):
            try:
                parsed = json.loads(raw)
                return dict(parsed) if isinstance(parsed, dict) else {}
            except (json.JSONDecodeError, ValueError):
                return {}
        return {}
