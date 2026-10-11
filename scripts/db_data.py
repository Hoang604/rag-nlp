"""Database Data Export & Import Utility (Data-Only).

Supports exporting and importing live data for 'documents', 'chunks', and 'graph_edges'
without dumping database schema, tables, or extensions.

Usage:
  Export:
    uv run python scripts/db_data.py export -o data_export.sql
    uv run python scripts/db_data.py export -o data_export.sql --inserts

  Import:
    uv run python scripts/db_data.py import -i data_export.sql
    uv run python scripts/db_data.py import -i data_export.sql --clean
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

DEFAULT_DB_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:1542/rag_db"
)
TARGET_TABLES = ["documents", "chunks", "graph_edges"]


def _get_docker_container() -> str | None:
    """Checks if 'rag_postgres' docker container is active."""
    try:
        res = subprocess.run(
            ["docker", "ps", "--filter", "name=rag_postgres", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            check=False,
        )
        for line in res.stdout.splitlines():
            if line.strip() == "rag_postgres":
                return "rag_postgres"
    except (subprocess.SubprocessError, OSError):
        return None
    return None


def export_data(
    output_path: Path,
    db_url: str = DEFAULT_DB_URL,
    use_inserts: bool = False,
) -> None:
    """Exports data-only SQL snapshot for documents, chunks, and graph_edges."""
    parsed = urlparse(db_url)
    user = parsed.username or "postgres"
    db_name = parsed.path.lstrip("/") or "rag_db"
    host = parsed.hostname or "localhost"
    port = str(parsed.port or 1542)

    container = _get_docker_container()
    print(f"[*] Exporting data-only snapshot from database '{db_name}'...")
    print(f"[*] Target tables: {', '.join(TARGET_TABLES)}")

    table_args: list[str] = []
    for t in TARGET_TABLES:
        table_args.extend(["-t", t])

    cmd: list[str]
    env = os.environ.copy()
    if parsed.password:
        env["PGPASSWORD"] = parsed.password

    if container and (host in ("localhost", "127.0.0.1")):
        # Execute pg_dump directly inside the healthy postgres container
        cmd = [
            "docker",
            "exec",
            "-i",
            container,
            "pg_dump",
            "-U",
            user,
            "-d",
            db_name,
            "--data-only",
        ]
        if use_inserts:
            cmd.append("--inserts")
        cmd.extend(table_args)
    else:
        # Fallback to local pg_dump binary if available
        cmd = [
            "pg_dump",
            "-h",
            host,
            "-p",
            port,
            "-U",
            user,
            "-d",
            db_name,
            "--data-only",
        ]
        if use_inserts:
            cmd.append("--inserts")
        cmd.extend(table_args)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        proc = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, env=env, check=False)
        if proc.returncode != 0:
            err = proc.stderr.decode("utf-8", errors="replace")
            print(f"[!] Export failed: {err}", file=sys.stderr)
            sys.exit(proc.returncode)

    file_size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"[✔] Successfully exported data snapshot to: {output_path} ({file_size_mb:.2f} MB)")


def import_data(
    input_path: Path,
    db_url: str = DEFAULT_DB_URL,
    clean: bool = True,
) -> None:
    """Imports data-only SQL snapshot into PostgreSQL."""
    if not input_path.exists():
        print(f"[!] Input file does not exist: {input_path}", file=sys.stderr)
        sys.exit(1)

    parsed = urlparse(db_url)
    user = parsed.username or "postgres"
    db_name = parsed.path.lstrip("/") or "rag_db"
    host = parsed.hostname or "localhost"
    port = str(parsed.port or 1542)

    container = _get_docker_container()
    print(f"[*] Importing data snapshot from: {input_path}")
    print(f"[*] Target database: {db_name} (clean={clean})")

    env = os.environ.copy()
    if parsed.password:
        env["PGPASSWORD"] = parsed.password

    # Truncate tables first if clean=True to prevent duplicate key violations
    if clean:
        truncate_sql = "TRUNCATE TABLE graph_edges, chunks, documents CASCADE;"
        if container and (host in ("localhost", "127.0.0.1")):
            trunc_cmd = [
                "docker",
                "exec",
                "-i",
                container,
                "psql",
                "-U",
                user,
                "-d",
                db_name,
                "-c",
                truncate_sql,
            ]
        else:
            trunc_cmd = [
                "psql",
                "-h",
                host,
                "-p",
                port,
                "-U",
                user,
                "-d",
                db_name,
                "-c",
                truncate_sql,
            ]
        proc_trunc = subprocess.run(trunc_cmd, capture_output=True, env=env, check=False)
        if proc_trunc.returncode != 0:
            err = proc_trunc.stderr.decode("utf-8", errors="replace")
            print(f"[!] Truncate failed: {err}", file=sys.stderr)
            sys.exit(proc_trunc.returncode)
        print("[✔] Existing data cleanly truncated.")

    # Execute SQL restore
    if container and (host in ("localhost", "127.0.0.1")):
        psql_cmd = [
            "docker",
            "exec",
            "-i",
            container,
            "psql",
            "-U",
            user,
            "-d",
            db_name,
            "-v",
            "ON_ERROR_STOP=1",
        ]
    else:
        psql_cmd = [
            "psql",
            "-h",
            host,
            "-p",
            port,
            "-U",
            user,
            "-d",
            db_name,
            "-v",
            "ON_ERROR_STOP=1",
        ]

    with open(input_path, "rb") as f:
        proc_import = subprocess.run(psql_cmd, stdin=f, capture_output=True, env=env, check=False)
        if proc_import.returncode != 0:
            err = proc_import.stderr.decode("utf-8", errors="replace")
            print(f"[!] Import failed: {err}", file=sys.stderr)
            sys.exit(proc_import.returncode)

    print(f"[✔] Successfully imported data from: {input_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export and import data-only SQL snapshots for rag-nlp PostgreSQL database."
    )
    subparsers = parser.add_subparsers(dest="mode", required=True, help="Mode: export or import")

    # Export mode
    export_parser = subparsers.add_parser("export", help="Export data-only SQL file")
    export_parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("data_dump.sql"),
        help="Target output SQL file path (default: data_dump.sql)",
    )
    export_parser.add_argument(
        "--db-url",
        type=str,
        default=DEFAULT_DB_URL,
        help="PostgreSQL connection string",
    )
    export_parser.add_argument(
        "--inserts",
        action="store_true",
        help="Use INSERT commands instead of COPY (slower, but easier to read)",
    )

    # Import mode
    import_parser = subparsers.add_parser("import", help="Import data-only SQL file into database")
    import_parser.add_argument(
        "-i",
        "--input",
        type=Path,
        required=True,
        help="Path to SQL data file to import",
    )
    import_parser.add_argument(
        "--db-url",
        type=str,
        default=DEFAULT_DB_URL,
        help="PostgreSQL connection string",
    )
    import_parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Do not truncate existing records before importing",
    )

    args = parser.parse_args()

    if args.mode == "export":
        export_data(
            output_path=args.output,
            db_url=args.db_url,
            use_inserts=args.inserts,
        )
    elif args.mode == "import":
        import_data(
            input_path=args.input,
            db_url=args.db_url,
            clean=not args.no_clean,
        )


if __name__ == "__main__":
    main()
