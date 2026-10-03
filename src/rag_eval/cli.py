from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, cast

import typer
from rich.console import Console

from rag_eval.console import use_utf8_stdout
from rag_eval.ingestion.staging import StagingManager

app = typer.Typer(name="rag-eval", help="Agentic RAG CLI")
console = Console()


@app.command(name="migrate")
def migrate() -> None:
    """Run PostgreSQL database DDL migrations."""
    import asyncio

    from rag_eval.db.connection import close_db_pool, get_db_pool
    from rag_eval.db.migrations import run_migrations

    async def _migrate() -> list[str]:
        try:
            pool = await get_db_pool()
            return await run_migrations(pool)
        finally:
            await close_db_pool()

    console.print("[cyan]Applying database schema migrations...[/cyan]")
    applied = asyncio.run(_migrate())
    console.print(
        f"[green]✔ Successfully applied {len(applied)} migration files.[/green]"
    )


async def _prune_stale_chunks(
    manager: StagingManager, target_slugs: list[str] | None = None
) -> int:
    """Deletes chunks of promoted documents that the current staging no longer has."""
    from rag_eval.db.connection import get_db_pool

    pool = await get_db_pool()
    from rag_eval.db.repositories import CorpusRepository

    corpus_repo = CorpusRepository(pool)
    removed = 0
    slugs_to_check = (
        target_slugs
        if target_slugs is not None
        else [s.doc_slug for s in manager.list_sessions()]
    )
    for slug in slugs_to_check:
        session = manager.load_session(slug)
        paths = [c.path for c in session.chunks]
        doc = await corpus_repo.documents.get_by_slug(session.doc_slug)
        if doc:
            all_chunks = await corpus_repo.chunks.list_by_document(doc.id)
            stale_paths = [c.path for c in all_chunks if c.path not in paths]
            if stale_paths:
                stale_ids = [c.id for c in all_chunks if c.path in stale_paths]
                await corpus_repo.graph.delete_outgoing_edges_for_chunks(stale_ids)
                count = await corpus_repo.chunks.delete_stale_by_paths(doc.id, stale_paths)
                removed += count
    return removed


async def _rebuild_indexes() -> None:
    from rag_eval.db.connection import get_db_pool
    from rag_eval.db.repositories import CorpusRepository

    pool = await get_db_pool()
    corpus_repo = CorpusRepository(pool)
    try:
        await corpus_repo.chunks.reindex_and_vacuum()
    except (OSError, RuntimeError) as exc:
        console.print(f"[yellow]  index rebuild skipped: {exc}[/yellow]")


@app.command(name="promote")
def promote(
    embed: Annotated[bool, typer.Option("--embed/--no-embed")] = True,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Automatically finalize unreviewed chunks and transition DRAFT/AMENDMENT sessions to APPROVED before promotion.",
        ),
    ] = False,
) -> None:
    """Promote every staged document into PostgreSQL, bypassing human review."""
    import asyncio

    from rag_eval.ingestion.staging import StagingManager
    from rag_eval.ingestion.staging.models import ChunkReviewStatus, StagingStatus
    from rag_eval.web.services import HumanPromotionEngine

    async def run() -> None:
        manager = StagingManager()
        engine = HumanPromotionEngine(staging_manager=manager)
        eligible_sessions = [
            s for s in manager.list_sessions()
            if s.status != StagingStatus.PROMOTED
        ]
        if not eligible_sessions:
            console.print("[yellow]No unpromoted staged documents found in .cache/stg.[/yellow]")
            return

        chunks = edges = 0
        promoted_slugs: list[str] = []
        for s_summary in eligible_sessions:
            slug = s_summary.doc_slug
            if force:
                session = manager.load_session(slug)
                unreviewed = [c.path for c in session.chunks if c.review_status != ChunkReviewStatus.REVIEWED]
                if unreviewed:
                    session, _, _ = manager.finalize_chunks(
                        doc_slug=slug,
                        paths=unreviewed,
                        actor="CLI:force_promote",
                    )
                if session.status in (StagingStatus.DRAFT, StagingStatus.AMENDMENT):
                    manager.update_session_status(
                        doc_slug=slug,
                        status=StagingStatus.APPROVED,
                        actor="CLI:force_promote",
                        description="Force transitioned to APPROVED for automated promotion.",
                    )

            result = await engine.promote_session(
                doc_slug=slug, compute_embeddings=embed
            )
            chunks += result.chunks_promoted
            edges += result.edges_promoted
            promoted_slugs.append(slug)
            console.print(
                f"  {slug}: {result.chunks_promoted} chunks, "
                f"{result.edges_promoted} edges"
            )
        pruned = await _prune_stale_chunks(manager, target_slugs=promoted_slugs)
        await _rebuild_indexes()
        console.print(
            f"[green]✔ Promoted {len(promoted_slugs)} documents: "
            f"{chunks} chunks, {edges} edges"
            + (f", pruned {pruned} stale chunks" if pruned else "")
            + ".[/green]"
        )

    asyncio.run(run())


@app.command(name="ingest")
def ingest(
    file_path: Annotated[
        Path,
        typer.Argument(
            help="Path to document file to ingest (PDF, DOCX, Markdown, HTML, TXT)",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ],
    slug: Annotated[
        str | None,
        typer.Option(
            "--slug",
            "-s",
            help="Document slug (must adhere to PostgreSQL ltree label regex). Defaults to sanitized filename stem.",
        ),
    ] = None,
    title: Annotated[
        str | None,
        typer.Option(
            "--title",
            "-t",
            help="Human-readable document title. Defaults to filename stem.",
        ),
    ] = None,
) -> None:
    """Ingest a document file (PDF, DOCX, Markdown, HTML, TXT) into a new staging session."""
    from rag_eval.exceptions import CorpusDomainError
    from rag_eval.schemas import sanitize_ltree_label

    doc_slug = sanitize_ltree_label(slug) if slug else sanitize_ltree_label(file_path.stem)
    doc_title = title if title else file_path.stem

    console.print(f"[cyan]Ingesting document '{file_path.name}' as '{doc_slug}'...[/cyan]")
    manager = StagingManager()
    try:
        session = manager.create_session_from_file(
            doc_slug=doc_slug,
            title=doc_title,
            file_path=file_path,
        )
        console.print(
            f"[green]✔ Successfully created staging session for '{session.doc_slug}' "
            f"({len(session.chunks)} chunks, {len(session.edges)} edges).[/green]"
        )
    except CorpusDomainError as exc:
        console.print(f"[red]Error during ingestion:[/red] {exc.message}")
        raise typer.Exit(code=1) from exc


@app.command(name="server")
def server(
    log_file: Annotated[
        str | None,
        typer.Option(
            "--log-file",
            help="Path to write diagnostic log file (defaults to logs/mcp_server.log)",
        ),
    ] = "logs/mcp_server.log",
) -> None:
    """Launch the MCP JSON-RPC 2.0 Server over Stdio."""
    from rag_eval.mcp.server import run_mcp_server

    run_mcp_server(log_file=log_file)


@app.command(name="tool")
def tool(
    tool_name: Annotated[
        str,
        typer.Argument(
            help="Name of the MCP tool to execute (e.g. hybrid_search, stg_preview, stg_commit)"
        ),
    ],
    args: Annotated[
        str,
        typer.Option(
            "--args",
            "-a",
            help="JSON string of arguments to pass to the tool",
        ),
    ] = "{}",
    output_file: Annotated[
        str | None,
        typer.Option(
            "--output",
            "-o",
            help="Optional path to write raw JSON result",
        ),
    ] = None,
    raw: Annotated[
        bool,
        typer.Option(
            "--raw/--no-raw",
            "-r",
            help="Output raw JSON-RPC response without extra console styling",
        ),
    ] = True,
) -> None:
    """Direct headless runner for all MCP tools."""
    import asyncio

    from rag_eval.db.connection import close_db_pool
    from rag_eval.mcp.server import CorpusMCPServer

    try:
        raw_parsed = json.loads(args.strip() if args else "{}")
        if not isinstance(raw_parsed, dict):
            console.print(
                f"[bold red]Error:[/bold red] Tool arguments must be a JSON object, got {type(raw_parsed).__name__}"
            )
            raise typer.Exit(code=1)
        parsed_args = cast(dict[str, object], raw_parsed)
    except (json.JSONDecodeError, ValueError) as err:
        console.print(f"[bold red]Error parsing JSON arguments:[/bold red] {err}")
        raise typer.Exit(code=1) from err

    async def _execute() -> dict[str, object]:
        try:
            server = CorpusMCPServer()
            res = await server.handle_request_dict(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": tool_name.strip(), "arguments": parsed_args},
                }
            )
            return res or {}
        finally:
            await close_db_pool()

    res = asyncio.run(_execute())
    formatted_json = json.dumps(res, indent=2, ensure_ascii=False)
    if output_file:
        out_p = Path(output_file)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(formatted_json, encoding="utf-8")
        if not raw:
            console.print(f"[green]✔ Tool output written to {out_p}[/green]")
    else:
        print(formatted_json)

    if "error" in res:
        raise typer.Exit(code=1)


@app.command(name="api")
def api(
    host: Annotated[
        str,
        typer.Option("--host", "-h", help="Bind host address"),
    ] = "127.0.0.1",
    port: Annotated[
        int,
        typer.Option("--port", "-p", help="Bind port number"),
    ] = 8000,
    reload: Annotated[
        bool,
        typer.Option(
            "--reload/--no-reload",
            help="Enable hot reloading on code changes in src/",
        ),
    ] = True,
) -> None:
    """Launch FastAPI backend server for staging API."""
    import uvicorn

    src_dir = Path(__file__).resolve().parents[1]
    console.print(
        f"[bold green]Starting Corpus Staging API at http://{host}:{port}[/bold green]"
    )
    if reload:
        uvicorn.run(
            "rag_eval.web.app:create_app",
            factory=True,
            host=host,
            port=port,
            reload=True,
            reload_dirs=[str(src_dir)],
            log_level="info",
        )
    else:
        from rag_eval.web.app import create_app

        uvicorn_app = create_app()
        uvicorn.run(uvicorn_app, host=host, port=port, log_level="info")


@app.command(name="ui")
def ui(
    host: Annotated[
        str,
        typer.Option("--host", "-h", help="Bind host address"),
    ] = "127.0.0.1",
    port: Annotated[
        int,
        typer.Option("--port", "-p", help="Bind port number"),
    ] = 8000,
    open_browser: Annotated[
        bool,
        typer.Option(
            "--open/--no-open",
            help="Automatically open default web browser upon startup",
        ),
    ] = True,
) -> None:
    """Launch the Human-in-the-Loop Staging Reviewer Web Application."""
    import shutil
    import subprocess
    import threading
    import time
    import webbrowser

    frontend_dir = Path("frontend")
    dist_dir = frontend_dir / "dist"

    npm = shutil.which("npm")
    if npm is None:
        console.print(
            "[bold red]Không tìm thấy `npm` trong PATH.[/bold red] "
            "Cài Node.js, hoặc chạy riêng backend:\n"
            "  uv run rag-eval api"
        )
        raise typer.Exit(code=1)

    if not (dist_dir.exists() and (dist_dir / "index.html").exists()):
        console.print(
            "[cyan]Building frontend SPA assets (dist/ missing)...[/cyan]"
        )
        try:
            subprocess.run([npm, "install"], cwd=str(frontend_dir), check=True)
            subprocess.run([npm, "run", "build"], cwd=str(frontend_dir), check=True)
            console.print(
                "[green]✔ Successfully built frontend SPA bundle into dist/.[/green]"
            )
        except (subprocess.CalledProcessError, FileNotFoundError) as err:
            console.print(f"[bold red]Frontend build failed:[/bold red] {err}")
            raise typer.Exit(code=1) from err

    url = f"http://{host}:{port}"
    console.print(
        f"[bold green]Starting Corpus Reviewer Web Application at {url}[/bold green]"
    )
    if open_browser:

        def _open() -> None:
            time.sleep(1.0)
            webbrowser.open(url)

        threading.Timer(1.0, _open).start()

    import uvicorn

    from rag_eval.web.app import create_app

    uvicorn_app = create_app(static_dir=dist_dir)
    uvicorn.run(uvicorn_app, host=host, port=port, log_level="info")


def main() -> None:
    """CLI entrypoint."""
    use_utf8_stdout()
    app()


if __name__ == "__main__":
    main()
