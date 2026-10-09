import uuid
from unittest.mock import AsyncMock, MagicMock

import asyncpg
import pytest

from rag_eval.db.repositories.chunks import ChunkRepository


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
