import uuid
from unittest.mock import AsyncMock, MagicMock

import asyncpg
import pytest

from rag_eval.db.repositories.chunks import ChunkRepository
from rag_eval.ingestion.loader import PostgresBulkLoader


@pytest.mark.asyncio
async def test_batch_resolution() -> None:
    """Verifies that ChunkRepository.resolve_paths_batch resolves multiple paths in a single query."""
    mock_pool = MagicMock(spec=asyncpg.Pool)
    repo = ChunkRepository(mock_pool)

    mock_conn = AsyncMock(spec=asyncpg.Connection)
    p1 = "doc_sample.sec_1"
    p2 = "doc_sample.sec_2"
    u1 = uuid.uuid4()
    u2 = uuid.uuid4()

    mock_conn.fetch.return_value = [
        {"id": str(u1), "path": p1},
        {"id": str(u2), "path": p2},
    ]

    res = await repo.resolve_paths_batch([p1, p2], conn=mock_conn)
    assert res == {p1: u1, p2: u2}
    mock_conn.fetch.assert_awaited_once()
    query = str(mock_conn.fetch.await_args[0][0])
    assert "WHERE path = ANY($1::ltree[])" in query


@pytest.mark.asyncio
async def test_batch_resolution_forwards_connection() -> None:
    """Verifies that PostgresBulkLoader forwards the active connection to resolve_paths_batch to avoid connection pool deadlock."""
    mock_pool = MagicMock(spec=asyncpg.Pool)
    mock_corpus_repo = MagicMock()
    loader = PostgresBulkLoader(pool=mock_pool, corpus_repo=mock_corpus_repo)

    mock_conn = AsyncMock(spec=asyncpg.Connection)
    paths = ["doc.sec1", "doc.sec2"]
    mock_corpus_repo.chunks.resolve_paths_batch = AsyncMock(return_value={paths[0]: uuid.uuid4()})

    await loader.resolve_chunk_paths(paths, conn=mock_conn)
    mock_corpus_repo.chunks.resolve_paths_batch.assert_awaited_once_with(paths, conn=mock_conn)
