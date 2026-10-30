# Agent Instructions

## Project Identity & Coding RAG Scope
- **Coding RAG Suite**: This project is exclusively a **Coding RAG** system designed for technical framework documentation (`.md`, `.mdx`) and source code.
- **No PDF/DOCX Ingestion**: The system operates exclusively on technical code and documentation formats; general-purpose office formats (DOCX, PDF) are out of scope.
- **Framework Parser Registry Architecture**: Ingestion is governed strictly by `CodingParserRegistry`. Every supported framework must have a dedicated, self-contained parser (e.g., `NextJSMDXParser`) registered. The system implements **zero generic fallbacks**: unregistered documentation formats fail fast with `UnsupportedFrameworkError`.

## Package & Environment Management
- This project exclusively uses **`uv`** for Python dependency management, package execution, and environment handling.
- Always execute Python commands, tools, and scripts via `uv run` (e.g., `uv run python ...`, `uv run pytest`).
- Add project dependencies using `uv add` (and `uv add --dev` for development tooling).
- For the frontend workspace (`frontend/`), execute commands with `--prefix frontend` (e.g., `npm run build --prefix frontend`).

## Repository Validation & Migrations
- Standardized type-checking and repository validation must be executed via:
  ```bash
  uv run scripts/check.py
  ```
- Always execute this command to ensure code compliance and type safety before concluding tasks.
- Database migrations must be executed via:
  ```bash
  uv run python -m rag_eval.db.migrations
  ```
- Migrations must preserve existing promoted database records in-place without destructive data wiping.

## Testing Principles & Scope
- **Infrastructure & System Mechanics**: Unit and integration tests in `tests/` verify technical infrastructure, concurrency, architectural invariants, protocol compliance, transaction boundaries, and system mechanics.

## MCP Testing & Tool Execution
- **Always Test MCP via CLI**: When testing or verifying MCP tools during development, never attempt to interact with or restart persistent background MCP server daemons. Always test and verify tool payloads directly using the headless CLI runner:
  ```bash
  uv run rag-eval tool <tool_name> -a '<json_args>'
  ```
  Examples:
  ```bash
  uv run rag-eval tool hybrid_search -a '{"query": "routing and navigation", "pattern": "layout", "limit": 2}'
  uv run rag-eval tool hierarchical_navigate -a '{"path": "nextjs.app.building_your_application", "direction": "CHILDREN"}'
  ```
