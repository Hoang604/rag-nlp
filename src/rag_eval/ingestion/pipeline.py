from __future__ import annotations

import logging
import uuid
from pathlib import Path

import asyncpg

from rag_eval.db.repositories import CorpusRepository
from rag_eval.ingestion.loader import DEFAULT_EMBEDDING_MODEL, PostgresBulkLoader
from rag_eval.ingestion.parser.engine import DocumentIngestionEngine
from rag_eval.schemas import (
    ChunkEntity,
    DocumentEntity,
    GraphEdgeEntity,
    IngestionResult,
    ParsedDocumentDraft,
)

logger = logging.getLogger(__name__)


class DirectIngestionCoordinator:
    """Coordinates parsing documents into draft entities and atomically upserting to PostgreSQL with embeddings."""

    def __init__(
        self,
        pool: asyncpg.Pool,
        compute_embeddings: bool = True,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
        corpus_repo: CorpusRepository | None = None,
        loader: PostgresBulkLoader | None = None,
        engine: DocumentIngestionEngine | None = None,
    ) -> None:
        self.pool = pool
        self.compute_embeddings = compute_embeddings
        self.embedding_model = embedding_model
        self.corpus_repo = corpus_repo if corpus_repo is not None else CorpusRepository(pool)
        self.loader = loader if loader is not None else PostgresBulkLoader(
            pool=pool,
            compute_embeddings=compute_embeddings,
            embedding_model=embedding_model,
            corpus_repo=self.corpus_repo,
        )
        self.engine = engine if engine is not None else DocumentIngestionEngine()

    async def _ingest_draft(
        self,
        draft: ParsedDocumentDraft,
        overwrite: bool = True,
    ) -> IngestionResult:
        # Check existing document
        existing_doc = await self.corpus_repo.documents.get_by_slug(draft.doc_slug)
        if existing_doc is not None and not overwrite:
            existing_chunks = await self.corpus_repo.chunks.list_by_document(existing_doc.id)
            existing_edges = await self.corpus_repo.graph.list_edges_for_chunks([c.id for c in existing_chunks])
            return IngestionResult(
                document_id=existing_doc.id,
                doc_slug=draft.doc_slug,
                title=existing_doc.title,
                chunks_count=len(existing_chunks),
                edges_count=len(existing_edges),
                skipped=True,
            )

        doc_id = existing_doc.id if existing_doc is not None else uuid.uuid4()
        doc_entity = DocumentEntity(
            id=doc_id,
            doc_slug=draft.doc_slug,
            title=draft.title,
            raw_text=draft.raw_text,
            metadata=draft.metadata,
        )

        # 1. Upsert Document
        authoritative_doc_id = await self.loader.load_document(doc_entity)

        # 2. Build ChunkEntities
        chunk_entities: list[ChunkEntity] = [
            ChunkEntity(
                document_id=authoritative_doc_id,
                path=c.path,
                verbatim_text=c.verbatim_text,
                contextualized_text=c.contextualized_text,
                start_line=c.start_line,
                end_line=c.end_line,
                metadata=c.metadata,
            )
            for c in draft.chunks
        ]

        # 3. Upsert Chunks with embeddings
        path_to_id_map = await self.loader.load_chunks(chunk_entities)

        # 4. Resolve edge endpoints and upsert edges
        external_paths = [
            e.target_path
            for e in draft.edges
            if e.target_path not in path_to_id_map
        ]
        external_resolved: dict[str, uuid.UUID] = {}
        if external_paths:
            external_resolved = await self.loader.resolve_chunk_paths(external_paths)

        resolved_edges: list[GraphEdgeEntity] = []
        for e in draft.edges:
            src_id = path_to_id_map.get(e.source_path)
            tgt_id = path_to_id_map.get(e.target_path) or external_resolved.get(e.target_path)
            if src_id is not None and tgt_id is not None and src_id != tgt_id:
                rel = e.relation_type.value
                resolved_edges.append(
                    GraphEdgeEntity(
                        source_chunk_id=src_id,
                        target_chunk_id=tgt_id,
                        relation_type=rel,
                    )
                )

        edges_map = await self.loader.load_graph_edges(resolved_edges)

        return IngestionResult(
            document_id=authoritative_doc_id,
            doc_slug=draft.doc_slug,
            title=draft.title,
            chunks_count=len(chunk_entities),
            edges_count=len(edges_map),
            skipped=False,
        )

    async def ingest_file(
        self,
        file_path: Path | str,
        doc_slug: str,
        title: str,
        metadata: dict[str, object] | None = None,
        overwrite: bool = True,
    ) -> IngestionResult:
        draft = self.engine.process_file(
            doc_slug=doc_slug,
            title=title,
            file_path=file_path,
            metadata=metadata,
        )
        return await self._ingest_draft(draft, overwrite=overwrite)

    async def ingest_raw(
        self,
        raw_text: str,
        doc_slug: str,
        title: str,
        metadata: dict[str, object] | None = None,
        overwrite: bool = True,
    ) -> IngestionResult:
        draft = self.engine.process_raw(
            doc_slug=doc_slug,
            title=title,
            raw_text=raw_text,
            metadata=metadata,
        )
        return await self._ingest_draft(draft, overwrite=overwrite)

    async def ingest_bytes(
        self,
        content: bytes,
        file_name: str,
        doc_slug: str,
        title: str,
        mime_type: str | None = None,
        metadata: dict[str, object] | None = None,
        overwrite: bool = True,
    ) -> IngestionResult:
        draft = self.engine.process_bytes(
            doc_slug=doc_slug,
            title=title,
            content=content,
            file_name=file_name,
            mime_type=mime_type,
            metadata=metadata,
        )
        return await self._ingest_draft(draft, overwrite=overwrite)
