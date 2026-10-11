# Coding RAG Evaluation & Ingestion Benchmark Suite

Production-grade hierarchical coding knowledge engineering with Framework-Specific AST Direct Ingestion, Dense Vector + Sparse BM25 Hybrid Retrieval, Runtime Knowledge Graph Enrichment, and a Live Web Observatory Dashboard for PostgreSQL.

## Core Architecture

1. **Coding RAG Direct Ingestion**: Ingest technical framework documentation (`.md`, `.mdx`) and source code directly into PostgreSQL production (`documents`, `chunks`, `graph_edges`) with dense vector embeddings and hierarchical LTree paths (`doc_slug.sec_1.sec_2`) in a single atomic transaction.
2. **Framework Parser Registry (`CodingParserRegistry`)**: Strict Open-Closed architecture where every software framework (starting with Next.js App Router via `NextJSMDXParser`) is handled by a dedicated parser that encapsulates its specific markdown/MDX semantics, JSX components, and code tabs. Zero generic fallbacks: unsupported frameworks fail fast with clear guidance to implement a dedicated parser.
3. **Section-Level Semantic Chunking**: Technical chunks are bound by Heading Section (H1/H2/H3) up to a 4,000-character threshold, natively preserving code snippets, explanatory preambles, and media diagrams in unified atomic chunks.
4. **Runtime Knowledge Graph Enrichment**: Retrieval agents dynamically enrich relationships discovered during query synthesis via symmetric `link_chunks` and `unlink_chunks` MCP tools using natural LTree paths (`source_path`, `target_path`, `relation_type`), keeping database internal UUIDs 100% encapsulated.
5. **Corpus & Graph Observatory Dashboard**: Real-time web visualization of document hierarchies, LTree outlines, 2D knowledge graphs, and hybrid retrieval experimentation running directly on PostgreSQL feeds.
6. **Standardized 5-Tool MCP Server**: High-performance Stdio JSON-RPC 2.0 server offering 3 sensors (`hybrid_search`, `hierarchical_navigate`, `graph_traverse`) and 2 enrichment actors (`link_chunks`, `unlink_chunks`).

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

# Ingest technical documentation directly into PostgreSQL
uv run rag-eval ingest path/to/document.mdx --slug my_doc
uv run rag-eval ingest-all data/nextjs

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
