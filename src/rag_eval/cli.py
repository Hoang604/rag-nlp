from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, cast

import typer
from rich.console import Console

from rag_eval.console import use_utf8_stdout

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
    embed: Annotated[
        bool,
        typer.Option(
            "--embed/--no-embed",
            help="Compute dense vector embeddings upon ingestion",
        ),
    ] = True,
    overwrite: Annotated[
        bool,
        typer.Option(
            "--overwrite/--no-overwrite",
            help="Overwrite existing document if it already exists in database",
        ),
    ] = True,
) -> None:
    """Ingest a document file directly into PostgreSQL with dense vector embeddings."""
    import asyncio

    from rag_eval.db.connection import close_db_pool, get_db_pool
    from rag_eval.exceptions import CorpusDomainError
    from rag_eval.ingestion.pipeline import DirectIngestionCoordinator
    from rag_eval.schemas import sanitize_ltree_label

    doc_slug = sanitize_ltree_label(slug) if slug else sanitize_ltree_label(file_path.stem)
    doc_title = title if title else file_path.stem

    console.print(f"[cyan]Ingesting document '{file_path.name}' directly into PostgreSQL as '{doc_slug}'...[/cyan]")

    async def _run() -> None:
        pool = await get_db_pool()
        try:
            coordinator = DirectIngestionCoordinator(pool=pool, compute_embeddings=embed)
            res = await coordinator.ingest_file(
                file_path=file_path,
                doc_slug=doc_slug,
                title=doc_title,
                overwrite=overwrite,
            )
            console.print(
                f"[green]✔ Successfully ingested '{res.doc_slug}' "
                f"({res.chunks_count} chunks, {res.edges_count} edges) directly into PostgreSQL.[/green]"
            )
        except CorpusDomainError as exc:
            console.print(f"[red]Error during ingestion:[/red] {exc.message}")
            raise typer.Exit(code=1) from exc
        finally:
            await close_db_pool()

    asyncio.run(_run())


@app.command(name="ingest-all")
def ingest_all(
    dir_path: Annotated[
        Path | None,
        typer.Argument(
            help="Directory containing document files to ingest sequentially (defaults to 'data')",
        ),
    ] = None,
    dir_option: Annotated[
        Path | None,
        typer.Option(
            "--dir",
            "-d",
            help="Alternative flag to specify directory containing document files",
        ),
    ] = None,
    pattern: Annotated[
        str,
        typer.Option(
            "--pattern",
            "-p",
            help="File glob pattern to match within directory (defaults to '*')",
        ),
    ] = "*",
    skip_existing: Annotated[
        bool,
        typer.Option(
            "--skip-existing/--overwrite",
            help="Skip files that already exist in PostgreSQL",
        ),
    ] = True,
    stop_on_error: Annotated[
        bool,
        typer.Option(
            "--stop-on-error/--continue-on-error",
            help="Halt execution immediately on first ingestion failure",
        ),
    ] = False,
    embed: Annotated[
        bool,
        typer.Option(
            "--embed/--no-embed",
            help="Compute dense vector embeddings upon ingestion",
        ),
    ] = True,
) -> None:
    """Sequentially ingest all supported documents in a directory directly into PostgreSQL."""
    import asyncio

    from rag_eval.db.connection import close_db_pool, get_db_pool
    from rag_eval.db.repositories import CorpusRepository
    from rag_eval.exceptions import CorpusDomainError
    from rag_eval.ingestion.pipeline import DirectIngestionCoordinator
    from rag_eval.schemas import sanitize_ltree_label

    target_dir = dir_option or dir_path or Path("data")
    if not target_dir.exists() or not target_dir.is_dir():
        console.print(f"[red]Error:[/red] Directory '{target_dir}' does not exist or is not a directory.")
        raise typer.Exit(code=1)

    supported_extensions = {
        ".pdf",
        ".docx",
        ".md",
        ".markdown",
        ".mdown",
        ".html",
        ".htm",
        ".txt",
        ".text",
    }

    files = [
        p
        for p in sorted(target_dir.glob(pattern), key=lambda p: p.name.lower())
        if p.is_file() and not p.name.startswith(".") and p.suffix.lower() in supported_extensions
    ]

    if not files:
        console.print(
            f"[yellow]No supported document files found in '{target_dir}' with pattern '{pattern}'.[/yellow]"
        )
        return

    console.print(
        f"[cyan]Found {len(files)} document(s) in '{target_dir}' to ingest directly into PostgreSQL...[/cyan]"
    )

    async def _run() -> None:
        pool = await get_db_pool()
        try:
            corpus_repo = CorpusRepository(pool)
            coordinator = DirectIngestionCoordinator(pool=pool, compute_embeddings=embed)

            success_count = 0
            skipped_count = 0
            failed_count = 0
            total_chunks = 0
            total_edges = 0

            for idx, file_path in enumerate(files, start=1):
                doc_slug = sanitize_ltree_label(file_path.stem)
                doc_title = file_path.stem

                existing = await corpus_repo.documents.get_by_slug(doc_slug)
                if existing is not None and skip_existing:
                    console.print(
                        f"[yellow]({idx}/{len(files)}) Skipping '{file_path.name}' "
                        f"(document '{doc_slug}' already exists in database).[/yellow]"
                    )
                    skipped_count += 1
                    continue

                console.print(
                    f"[cyan]({idx}/{len(files)}) Ingesting '{file_path.name}' as '{doc_slug}'...[/cyan]"
                )
                try:
                    res = await coordinator.ingest_file(
                        file_path=file_path,
                        doc_slug=doc_slug,
                        title=doc_title,
                        overwrite=True,
                    )
                    chunks_count = res.chunks_count
                    edges_count = res.edges_count
                    total_chunks += chunks_count
                    total_edges += edges_count
                    success_count += 1
                    console.print(
                        f"[green]✔ ({idx}/{len(files)}) Successfully ingested '{res.doc_slug}' "
                        f"({chunks_count} chunks, {edges_count} edges).[/green]"
                    )
                except (CorpusDomainError, Exception) as exc:
                    failed_count += 1
                    msg = exc.message if isinstance(exc, CorpusDomainError) else str(exc)
                    console.print(f"[red]✖ ({idx}/{len(files)}) Error ingesting '{file_path.name}':[/red] {msg}")
                    if stop_on_error:
                        raise typer.Exit(code=1) from exc

            console.print(
                f"[bold green]✔ Ingest completed: {success_count} succeeded "
                f"({total_chunks} chunks, {total_edges} edges), "
                f"{skipped_count} skipped, {failed_count} failed.[/bold green]"
            )
            if failed_count > 0:
                raise typer.Exit(code=1)
        finally:
            await close_db_pool()

    asyncio.run(_run())


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
            help="Name of the MCP tool to execute (e.g. hybrid_search, hierarchical_navigate, link_chunks)"
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
    """Launch FastAPI backend server for Corpus Knowledge Observatory API."""
    import uvicorn

    src_dir = Path(__file__).resolve().parents[1]
    console.print(
        f"[bold green]Starting Corpus Knowledge Observatory API at http://{host}:{port}[/bold green]"
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
    """Launch the Corpus Knowledge Observatory Web Application."""
    import shutil
    import subprocess
    import sys
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
            is_win = sys.platform == "win32"
            subprocess.run(
                [npm, "install"],
                cwd=str(frontend_dir),
                check=True,
                shell=is_win,
            )
            subprocess.run(
                [npm, "run", "build"],
                cwd=str(frontend_dir),
                check=True,
                shell=is_win,
            )
            console.print(
                "[green]✔ Successfully built frontend SPA bundle into dist/.[/green]"
            )
        except (subprocess.CalledProcessError, FileNotFoundError) as err:
            console.print(f"[bold red]Frontend build failed:[/bold red] {err}")
            raise typer.Exit(code=1) from err

    url = f"http://{host}:{port}"
    console.print(
        f"[bold green]Starting Corpus Knowledge Observatory at {url}[/bold green]"
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
