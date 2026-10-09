# RAG Evaluation and Ingestion Benchmark Suite

Structured document knowledge engineering, Write-Ahead Logging (WAL) staging buffer, hybrid search retrieval, and human-in-the-loop reviewer studio for hierarchical texts.

## Prerequisites
- Python >= 3.13.11 with [`uv`](https://docs.astral.sh/uv/) installed
- Docker & Docker Compose (or PostgreSQL 16 with `pgvector` extension)
- Node.js & npm (for UI build)

## Cross-Platform Execution (Linux & Windows)

All commands should be executed via `uv run` across platforms:

```bash
# Start PostgreSQL database with pgvector
docker compose up -d

# Run database migrations
uv run rag-eval migrate

# Run QA verification pipeline (linting and type checking)
uv run python scripts/check.py

# Launch Staging FastAPI backend
uv run rag-eval api

# Launch Reviewer Studio web application (auto-builds frontend if dist/ missing)
uv run rag-eval ui

# Launch MCP server over stdio
uv run rag-eval server
```
