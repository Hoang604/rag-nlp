from __future__ import annotations

import logging
from pathlib import Path
from typing import Final

import asyncpg

logger = logging.getLogger(__name__)

SQL_DIR: Final[Path] = Path(__file__).parent / "sql"
MIGRATION_ADVISORY_LOCK_ID: Final[int] = 849201

LEGACY_MIGRATIONS: Final[tuple[str, ...]] = (
    "006_chunk_context_refs.sql",
    "007_stored_procs.sql",
    "008_unresolved_external_refs.sql",
    "009_deferred_ref_integrity.sql",
    "010_drop_chunk_context_refs.sql",
)

RECONCILIATION_DDL: Final[str] = """
DROP TABLE IF EXISTS chunk_context_refs CASCADE;
ALTER TABLE chunks DROP COLUMN IF EXISTS context_type CASCADE;
ALTER TABLE chunks DROP COLUMN IF EXISTS is_all_refs_resolved CASCADE;
DROP TRIGGER IF EXISTS trg_assert_chunk_invariants ON chunks;
DROP FUNCTION IF EXISTS assert_chunk_invariants() CASCADE;
DROP FUNCTION IF EXISTS assert_chunk_context_ref_invariants() CASCADE;
DROP FUNCTION IF EXISTS assert_chunk_ref_consistency() CASCADE;
DROP FUNCTION IF EXISTS assert_chunk_ref_edge_integrity() CASCADE;
DROP INDEX IF EXISTS idx_chunks_context_type;
DROP FUNCTION IF EXISTS verbatim_grep(TEXT, TEXT[], LTREE, BOOLEAN, BOOLEAN, BOOLEAN, INT) CASCADE;
DROP FUNCTION IF EXISTS verbatim_grep_count(TEXT, TEXT[], LTREE, BOOLEAN, BOOLEAN, BOOLEAN) CASCADE;
DROP FUNCTION IF EXISTS hybrid_search(TEXT, VECTOR, INT, INT, TEXT[], LTREE, BOOLEAN, TEXT) CASCADE;
DROP FUNCTION IF EXISTS verbatim_grep(TEXT, TEXT[], LTREE, BOOLEAN, BOOLEAN, INT) CASCADE;
DROP FUNCTION IF EXISTS verbatim_grep_count(TEXT, TEXT[], LTREE, BOOLEAN, BOOLEAN) CASCADE;
DROP FUNCTION IF EXISTS hybrid_search(TEXT, VECTOR, INT, INT, TEXT[], LTREE, TEXT) CASCADE;
DROP FUNCTION IF EXISTS verbatim_grep CASCADE;
DROP FUNCTION IF EXISTS verbatim_grep_count CASCADE;
DROP FUNCTION IF EXISTS hybrid_search CASCADE;
"""


def get_migration_sql_files(sql_dir: Path | None = None) -> list[Path]:
    """Discovers all .sql migration files in the SQL directory sorted lexicographically.

    Args:
        sql_dir: Directory containing SQL migration scripts. Defaults to src/rag_eval/db/sql.

    Returns:
        List of Path objects sorted by filename.
    """
    target_dir = sql_dir if sql_dir is not None else SQL_DIR
    if not target_dir.exists() or not target_dir.is_dir():
        return []
    files = list(target_dir.glob("*.sql"))
    files.sort(key=lambda p: p.name)
    return files


async def init_migration_table(conn: asyncpg.Connection) -> None:
    """Ensures the schema_migrations tracking table exists.

    Args:
        conn: Active asyncpg connection.
    """
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version VARCHAR(255) PRIMARY KEY,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )


async def get_applied_migrations(conn: asyncpg.Connection) -> set[str]:
    """Retrieves the set of previously applied migration versions.

    Args:
        conn: Active asyncpg connection.

    Returns:
        Set of version strings recorded in schema_migrations.
    """
    await init_migration_table(conn)
    records = await conn.fetch("SELECT version FROM schema_migrations;")
    return {str(r["version"]) for r in records}


async def reconcile_legacy_schema(conn: asyncpg.Connection) -> bool:
    """Non-destructively reconciles legacy database mutations targeting clean Day-One layout.

    Args:
        conn: Active asyncpg connection.

    Returns:
        True if legacy reconciliation was executed, False if already canonical.
    """
    await init_migration_table(conn)
    legacy_count = await conn.fetchval(
        "SELECT count(*) FROM schema_migrations WHERE version = ANY($1::text[]);",
        list(LEGACY_MIGRATIONS),
    )
    has_legacy_cols = await conn.fetchval(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'chunks' AND column_name = 'context_type'
        );
        """
    )
    if not legacy_count and not has_legacy_cols:
        return False

    logger.info("Detected legacy database schema mutations; executing in-place reconciliation...")
    async with conn.transaction():
        await conn.execute(RECONCILIATION_DDL)
        await conn.execute(
            "DELETE FROM schema_migrations WHERE version = ANY($1::text[]);",
            list(LEGACY_MIGRATIONS),
        )
    logger.info("Legacy schema reconciliation successfully completed.")
    return True


async def run_migrations(
    pool: asyncpg.Pool,
    sql_dir: Path | None = None,
) -> list[str]:
    """Executes unapplied SQL migrations in deterministic alphabetical sequence after reconciliation.

    Uses PostgreSQL session-level advisory locks to prevent concurrent worker migration races.

    Args:
        pool: Active asyncpg database connection pool.
        sql_dir: Optional custom path to SQL migration directory.

    Returns:
        List of newly applied migration script filenames.

    Raises:
        RuntimeError: If a migration script fails during execution.
    """
    migration_files = get_migration_sql_files(sql_dir)
    if not migration_files:
        logger.info("No migration SQL files discovered in %s", sql_dir or SQL_DIR)
        return []

    applied_now: list[str] = []

    async with pool.acquire() as conn:
        await conn.execute("SELECT pg_advisory_lock($1);", MIGRATION_ADVISORY_LOCK_ID)
        try:
            await init_migration_table(conn)
            await reconcile_legacy_schema(conn)
            applied_set = await get_applied_migrations(conn)

            for sql_file in migration_files:
                version_name = sql_file.name
                if version_name in applied_set:
                    logger.debug(
                        "Migration %s already applied, skipping.", version_name
                    )
                    continue

                logger.info("Applying database migration: %s", version_name)
                sql_content = sql_file.read_text(encoding="utf-8")

                try:
                    async with conn.transaction():
                        await conn.execute(sql_content)
                        await conn.execute(
                            "INSERT INTO schema_migrations (version) VALUES ($1);",
                            version_name,
                        )
                    applied_now.append(version_name)
                    logger.info("Successfully applied migration: %s", version_name)
                except (
                    OSError,
                    RuntimeError,
                    asyncpg.PostgresError,
                    asyncpg.InterfaceError,
                ) as exc:
                    logger.error("Migration %s failed: %s", version_name, exc)
                    raise RuntimeError(
                        f"Migration failed at {version_name}: {exc}"
                    ) from exc
        finally:
            await conn.execute(
                "SELECT pg_advisory_unlock($1);", MIGRATION_ADVISORY_LOCK_ID
            )

    return applied_now


if __name__ == "__main__":
    import asyncio
    import sys

    from rag_eval.db.connection import get_db_pool

    async def _cli_main() -> None:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
        pool = await get_db_pool()
        try:
            applied = await run_migrations(pool)
            print(f"Applied migrations: {applied}")
        finally:
            await pool.close()

    try:
        asyncio.run(_cli_main())
    except (asyncpg.PostgresError, OSError, RuntimeError, ValueError) as exc:
        print(f"Migration error: {exc}", file=sys.stderr)
        sys.exit(1)
