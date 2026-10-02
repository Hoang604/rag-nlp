from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Final

import asyncpg
from pgvector.asyncpg import register_vector

logger = logging.getLogger(__name__)

DEFAULT_DATABASE_URL: Final[str] = (
    "postgresql://postgres:postgres@localhost:15432/rag_legal"
)

_pool: asyncpg.Pool | None = None

HNSW_EF_SEARCH: Final[int] = 200


async def init_connection_codecs(conn: asyncpg.Connection) -> None:
    """Initializes connection-level codecs for pgvector and JSONB serialization."""
    try:
        await register_vector(conn)
    except (
        asyncpg.PostgresError,
        asyncpg.InterfaceError,
        RuntimeError,
        ValueError,
    ) as exc:
        logger.debug("pgvector codec registration skipped/failed: %s", exc)

    try:
        await conn.set_type_codec(
            "jsonb",
            schema="pg_catalog",
            encoder=json.dumps,
            decoder=json.loads,
        )
    except (asyncpg.PostgresError, asyncpg.InterfaceError, RuntimeError) as exc:
        logger.debug("jsonb codec registration skipped/failed: %s", exc)


async def prepare_connection_session(conn: asyncpg.Connection) -> None:
    """Applies session settings on every acquire.

    Not in `init`: asyncpg runs RESET ALL when a connection returns to the
    pool, so anything SET there survives exactly one acquisition.
    """
    try:
        await conn.execute(f"SET hnsw.ef_search = {HNSW_EF_SEARCH}")
    except (asyncpg.PostgresError, asyncpg.InterfaceError, RuntimeError) as exc:
        logger.debug("hnsw.ef_search not set: %s", exc)


def resolve_database_url(dsn: str | None = None) -> str:
    """Resolves target database DSN from explicit argument, environment, or default fallback.

    Args:
        dsn: Optional explicit connection string.

    Returns:
        Resolved normalized PostgreSQL connection string.
    """
    if dsn is not None and dsn.strip():
        return dsn.strip()
    env_dsn = os.getenv("DATABASE_URL")
    if env_dsn is not None and env_dsn.strip():
        return env_dsn.strip()
    return DEFAULT_DATABASE_URL


async def get_db_pool(
    dsn: str | None = None,
    min_size: int = 1,
    max_size: int = 10,
    timeout: float = 30.0,
    command_timeout: float = 60.0,
    max_inactive_connection_lifetime: float = 300.0,
) -> asyncpg.Pool:
    """Returns or creates an asynchronous PostgreSQL connection pool using asyncpg.

    Args:
        dsn: Database connection URL (e.g. postgresql://user:pass@host:port/db).
        min_size: Minimum number of connections in the pool.
        max_size: Maximum number of connections in the pool.
        timeout: Timeout in seconds for establishing a connection.
        command_timeout: Default timeout in seconds for executing commands.
        max_inactive_connection_lifetime: Maximum idle time before connection is recycled (default 300s).

    Returns:
        Active asyncpg.Pool instance.

    Raises:
        RuntimeError: If connection pool creation fails.
    """
    global _pool
    current_loop = asyncio.get_running_loop()
    if _pool is not None and not _pool._closed:
        pool_loop = getattr(_pool, "_loop", None)
        if isinstance(pool_loop, asyncio.AbstractEventLoop):
            if pool_loop is current_loop and not pool_loop.is_closed():
                return _pool
        else:
            return _pool

    target_dsn = resolve_database_url(dsn)
    try:
        pool = await asyncpg.create_pool(
            dsn=target_dsn,
            min_size=min_size,
            max_size=max_size,
            timeout=timeout,
            command_timeout=command_timeout,
            max_inactive_connection_lifetime=max_inactive_connection_lifetime,
            max_queries=50000,
            statement_cache_size=1000,
            init=init_connection_codecs,
            setup=prepare_connection_session,
        )
        if pool is None:
            raise RuntimeError("asyncpg.create_pool returned None")
        _pool = pool
        logger.info(
            "Successfully initialized PostgreSQL connection pool at %s", target_dsn
        )
        return _pool
    except (
        OSError,
        TimeoutError,
        RuntimeError,
        asyncpg.PostgresError,
        asyncpg.InterfaceError,
        asyncpg.CannotConnectNowError,
    ) as exc:
        logger.error("Failed to initialize PostgreSQL pool: %s", exc)
        raise RuntimeError(
            f"Failed to connect to database at {target_dsn}: {exc}"
        ) from exc


async def close_db_pool() -> None:
    """Gracefully closes the global database connection pool and resets references."""
    global _pool
    if _pool is not None:
        try:
            pool_loop = getattr(_pool, "_loop", None)
            if isinstance(pool_loop, asyncio.AbstractEventLoop):
                if not _pool._closed and not pool_loop.is_closed():
                    await _pool.close()
            else:
                if not _pool._closed:
                    await _pool.close()
        except (RuntimeError, OSError, asyncpg.PostgresError) as exc:
            logger.debug("Error while closing pool: %s", exc)
        finally:
            _pool = None
        logger.info("Closed PostgreSQL connection pool.")


async def check_db_health(
    pool: asyncpg.Pool | None = None, dsn: str | None = None
) -> bool:
    """Probes database availability by executing a lightweight ping query.

    Args:
        pool: Optional active connection pool to probe. If None, acquires one via get_db_pool.
        dsn: Optional connection URL if pool needs to be acquired.

    Returns:
        True if database responds successfully to ping, False otherwise.
    """
    try:
        active_pool = pool if pool is not None else await get_db_pool(dsn=dsn)
        async with active_pool.acquire() as conn:
            result = await conn.fetchval("SELECT 1;")
            return result == 1
    except (
        OSError,
        TimeoutError,
        RuntimeError,
        asyncpg.PostgresError,
        asyncpg.InterfaceError,
        asyncpg.CannotConnectNowError,
    ) as exc:
        logger.debug("Database health check ping failed: %s", exc)
        return False
