from __future__ import annotations

import datetime
import json
import uuid
from unittest.mock import AsyncMock, MagicMock

import asyncpg
import pytest

from rag_eval.db.repositories.chunks import ChunkRepository
from rag_eval.schemas import ChunkEntity, HybridSearchQuery, VerbatimGrepQuery


def test_chunk_repository_row_to_entity() -> None:
    """Verifies _row_to_entity maps records without context_type or is_all_refs_resolved."""
    repo = ChunkRepository(pool=MagicMock())
    c_id = uuid.uuid4()
    d_id = uuid.uuid4()
    now = datetime.datetime.now(datetime.UTC)

    record = {
        "id": c_id,
        "document_id": d_id,
        "path": "rfc9000.sec_1",
        "verbatim_text": "QUIC protocol specifications.",
        "contextualized_text": "[rfc9000] QUIC protocol specifications.",
        "start_line": 1,
        "end_line": 10,
        "embedding": [0.1] * 512,
        "metadata": json.dumps({"source": "rfc"}),
        "created_at": now,
        "updated_at": now,
    }

    mock_record = MagicMock(spec=asyncpg.Record)
    mock_record.__getitem__.side_effect = record.__getitem__

    entity = repo._row_to_entity(mock_record)
    assert entity.id == c_id
    assert entity.document_id == d_id
    assert entity.path == "rfc9000.sec_1"
    assert entity.start_line == 1
    assert entity.end_line == 10
    assert entity.metadata == {"source": "rfc"}
    assert not hasattr(entity, "context_type")
    assert not hasattr(entity, "is_all_refs_resolved")


@pytest.mark.asyncio
async def test_chunk_repository_upsert_batch_9_tuple_packing() -> None:
    """Verifies upsert_batch packs strictly 9-element tuples matching $1-$9 placeholders."""
    conn = AsyncMock()
    conn.fetch.return_value = [{"id": str(uuid.uuid4()), "path": "test.sec_1"}]
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)

    pool = MagicMock()
    pool.acquire.return_value = cm
    repo = ChunkRepository(pool=pool)

    entity = ChunkEntity(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        path="test.sec_1",
        verbatim_text="Text content",
        contextualized_text="Context text",
        start_line=1,
        end_line=2,
        embedding=None,
        metadata={"key": "val"},
    )

    await repo.upsert_batch([entity])

    conn.executemany.assert_awaited_once()
    sql, records = conn.executemany.call_args[0]
    assert "$9" in sql
    assert "$10" not in sql
    assert len(records) == 1
    assert len(records[0]) == 9
    assert records[0][0] == entity.id
    assert records[0][1] == entity.document_id
    assert records[0][2] == entity.path
    assert records[0][7] is None  # embedding
    assert json.loads(records[0][8]) == {"key": "val"}  # metadata


@pytest.mark.asyncio
async def test_chunk_repository_stored_proc_parameter_counts() -> None:
    """Verifies hybrid_search binds 7 arguments, verbatim_grep binds 6, and count binds 5."""
    conn = AsyncMock()
    conn.fetch.return_value = []
    conn.fetchval.return_value = 0
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)

    pool = MagicMock()
    pool.acquire.return_value = cm
    repo = ChunkRepository(pool=pool)

    # 1. hybrid_search (7 arguments)
    h_query = HybridSearchQuery(query_text="search text")
    await repo.hybrid_search(h_query)
    h_sql, *h_args = conn.fetch.call_args[0]
    assert "$7::text" in h_sql
    assert "$8" not in h_sql
    assert len(h_args) == 7

    # 2. verbatim_grep (6 arguments)
    g_query = VerbatimGrepQuery(query_pattern="pattern")
    await repo.verbatim_grep(g_query)
    g_sql, *g_args = conn.fetch.call_args[0]
    assert "$6::int" in g_sql
    assert "$7" not in g_sql
    assert len(g_args) == 6

    # 3. verbatim_grep_count (5 arguments)
    await repo.verbatim_grep_count(g_query)
    c_sql, *c_args = conn.fetchval.call_args[0]
    assert "$5::boolean" in c_sql
    assert "$6" not in c_sql
    assert len(c_args) == 5
