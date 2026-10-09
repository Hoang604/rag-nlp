# RAG Evaluation and Ingestion Benchmark Suite

Production-grade hierarchical document knowledge engineering with AST-driven Direct Ingestion, Dense Vector + Sparse BM25 Hybrid Retrieval, Runtime Knowledge Graph Enrichment, and a Live Web Observatory Dashboard for PostgreSQL.

## Core Architecture

1. **Direct Ingestion**: Ingest PDF, DOCX, Markdown, HTML, and TXT directly into PostgreSQL production (`documents`, `chunks`, `graph_edges`) with dense vector embeddings and hierarchical LTree paths (`doc_slug.sec_1.para_2`) in a single atomic transaction. Zero staging files or review bottlenecks.
2. **Runtime Knowledge Graph Enrichment**: Retrieval agents dynamically enrich relationships discovered during query synthesis via symmetric `link_chunks` and `unlink_chunks` MCP tools using natural LTree paths (`source_path`, `target_path`, `relation_type`), keeping database internal UUIDs 100% encapsulated.
3. **Corpus & Graph Observatory Dashboard**: Real-time web visualization of document hierarchies, LTree outlines, 2D knowledge graphs, and hybrid retrieval experimentation running directly on PostgreSQL feeds.
4. **Standardized 5-Tool MCP Server**: High-performance Stdio JSON-RPC 2.0 server offering 3 sensors (`hybrid_search`, `hierarchical_navigate`, `graph_traverse`) and 2 enrichment actors (`link_chunks`, `unlink_chunks`).

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

# Run QA verification pipeline (linting and strict type checking)
uv run scripts/check.py

# Ingest documents directly into PostgreSQL
uv run rag-eval ingest path/to/document.md --slug my_doc
uv run rag-eval ingest-all data/

# Launch Corpus Knowledge Observatory API backend
uv run rag-eval api

# Launch Corpus Observatory Dashboard (auto-builds frontend if dist/ missing)
uv run rag-eval ui

# Launch MCP server over stdio
uv run rag-eval server
```

## Running Tests
```bash
uv run pytest
```
