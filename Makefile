.PHONY: check lint typecheck api ui server migrate help

help:
	@echo "Available commands:"
	@echo "  make check      - Run QA verification pipeline (ruff, ty)"
	@echo "  make lint       - Run ruff check with auto-fix"
	@echo "  make typecheck  - Run ty type checker"
	@echo "  make api        - Launch Staging FastAPI backend"
	@echo "  make ui         - Launch Reviewer Studio web application"
	@echo "  make server     - Launch MCP server over stdio"
	@echo "  make migrate    - Run PostgreSQL database migrations"

check:
	uv run python scripts/check.py

lint:
	uv run ruff check --fix

typecheck:
	uv run ty check

api:
	uv run rag-eval api

ui:
	uv run rag-eval ui

server:
	uv run rag-eval server

migrate:
	uv run rag-eval migrate
