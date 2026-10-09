from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from rag_eval.db.migrations import (
    LEGACY_MIGRATIONS,
    MIGRATION_ADVISORY_LOCK_ID,
    get_applied_migrations,
    get_migration_sql_files,
    init_migration_table,
    reconcile_legacy_schema,
    run_migrations,
)


def test_get_migration_sql_files_lexicographical_order(tmp_path: Path) -> None:
    """Verifies that discovery lists .sql files in deterministic alphabetical order."""
    (tmp_path / "003_chunks.sql").write_text("SELECT 3;", encoding="utf-8")
    (tmp_path / "001_extensions.sql").write_text("SELECT 1;", encoding="utf-8")
    (tmp_path / "002_documents.sql").write_text("SELECT 2;", encoding="utf-8")
    (tmp_path / "README.md").write_text("ignore me", encoding="utf-8")

    files = get_migration_sql_files(tmp_path)
    assert [f.name for f in files] == [
        "001_extensions.sql",
        "002_documents.sql",
        "003_chunks.sql",
    ]


def test_get_migration_sql_files_nonexistent_directory(tmp_path: Path) -> None:
    """Returns empty list when SQL directory does not exist."""
    missing = tmp_path / "missing_dir"
    assert get_migration_sql_files(missing) == []


@pytest.mark.asyncio
async def test_init_migration_table_executes_ddl() -> None:
    """Verifies init_migration_table creates schema_migrations table."""
    conn = AsyncMock()
    await init_migration_table(conn)
    conn.execute.assert_awaited_once()
    assert "schema_migrations" in conn.execute.call_args[0][0]


@pytest.mark.asyncio
async def test_get_applied_migrations_extracts_versions() -> None:
    """Verifies get_applied_migrations returns set of version strings."""
    conn = AsyncMock()
    conn.fetch.return_value = [
        {"version": "001_extensions.sql"},
        {"version": "002_documents.sql"},
    ]
    applied = await get_applied_migrations(conn)
    assert applied == {"001_extensions.sql", "002_documents.sql"}


@pytest.mark.asyncio
async def test_reconcile_legacy_schema_skips_when_clean() -> None:
    """Reconciliation no-ops when no legacy migrations or columns exist."""
    conn = AsyncMock()
    conn.fetchval.side_effect = [0, False]  # legacy_count=0, has_legacy_cols=False

    reconciled = await reconcile_legacy_schema(conn)
    assert reconciled is False
    assert conn.execute.await_count == 1  # only init_migration_table called


@pytest.mark.asyncio
async def test_reconcile_legacy_schema_executes_ddl_on_legacy_state() -> None:
    """Reconciliation runs DDL within transaction when legacy migrations are detected."""
    conn = AsyncMock()
    conn.fetchval.side_effect = [3, True]  # legacy_count=3, has_legacy_cols=True

    tx = MagicMock()
    tx.__aenter__ = AsyncMock(return_value=None)
    tx.__aexit__ = AsyncMock(return_value=None)
    conn.transaction = MagicMock(return_value=tx)

    reconciled = await reconcile_legacy_schema(conn)
    assert reconciled is True
    # Verify transaction entered and DDL executed with LEGACY_MIGRATIONS blacklist
    tx.__aenter__.assert_awaited_once()
    conn.execute.assert_awaited()
    # Find call where DDL is passed and call where DELETE is passed
    ddl_calls = [
        call for call in conn.execute.call_args_list if "chunk_context_refs" in call[0][0]
    ]
    assert len(ddl_calls) == 1
    delete_calls = [
        call for call in conn.execute.call_args_list if "DELETE FROM schema_migrations" in call[0][0]
    ]
    assert len(delete_calls) == 1
    assert delete_calls[0][0][1] == list(LEGACY_MIGRATIONS)


@pytest.mark.asyncio
async def test_run_migrations_advisory_lock_and_idempotency(tmp_path: Path) -> None:
    """Verifies session-level advisory lock protocol and application of unapplied scripts."""
    (tmp_path / "001_test.sql").write_text("CREATE TABLE test_tbl (id INT);", encoding="utf-8")
    (tmp_path / "002_test.sql").write_text("SELECT 1;", encoding="utf-8")

    conn = AsyncMock()
    # Simulating 001_test.sql is already applied, 002_test.sql is pending
    conn.fetch.return_value = [{"version": "001_test.sql"}]
    conn.fetchval.side_effect = [0, False]  # no legacy residue

    tx = MagicMock()
    tx.__aenter__ = AsyncMock(return_value=None)
    tx.__aexit__ = AsyncMock(return_value=None)
    conn.transaction = MagicMock(return_value=tx)

    pool = MagicMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    pool.acquire.return_value = cm

    applied = await run_migrations(pool, sql_dir=tmp_path)
    assert applied == ["002_test.sql"]

    # Verify advisory lock acquired and released
    lock_call = conn.execute.call_args_list[0]
    assert lock_call[0][0] == "SELECT pg_advisory_lock($1);"
    assert lock_call[0][1] == MIGRATION_ADVISORY_LOCK_ID

    unlock_call = conn.execute.call_args_list[-1]
    assert unlock_call[0][0] == "SELECT pg_advisory_unlock($1);"
    assert unlock_call[0][1] == MIGRATION_ADVISORY_LOCK_ID
