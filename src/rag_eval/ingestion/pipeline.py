from __future__ import annotations

import logging
import uuid
from pathlib import Path

import asyncpg

from rag_eval.db.repositories import CorpusRepository
from rag_eval.ingestion.loader import DEFAULT_EMBEDDING_MODEL, PostgresBulkLoader
from rag_eval.ingestion.parsers import NextJSMDXParser, NodeJSMarkdownParser
from rag_eval.ingestion.registry import CodingParserRegistry, UnsupportedFrameworkError
from rag_eval.schemas import (
    ChunkEntity,
    CorpusIngestionSummary,
    DocumentEntity,
    GraphEdgeEntity,
    IngestionResult,
    ParsedDocumentDraft,
)

logger = logging.getLogger(__name__)


class DirectIngestionCoordinator:
    """Coordinates parsing documents into draft entities via CodingParserRegistry and atomically upserting to PostgreSQL."""

    def __init__(
        self,
        pool: asyncpg.Pool,
        compute_embeddings: bool = True,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
        corpus_repo: CorpusRepository | None = None,
        loader: PostgresBulkLoader | None = None,
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
        # Ensure default framework parsers are registered
        CodingParserRegistry.register(NodeJSMarkdownParser())
        CodingParserRegistry.register(NextJSMDXParser())

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
                        citation_text=e.citation_text,
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
        doc_slug: str | None = None,
        title: str | None = None,
        metadata: dict[str, object] | None = None,
        overwrite: bool = True,
    ) -> IngestionResult:
        import dataclasses

        path = Path(file_path).resolve()
        parser = CodingParserRegistry.get_parser(path)
        draft = parser.parse(file_path=path, doc_slug=doc_slug)
        if title:
            draft = dataclasses.replace(draft, title=title)
        if metadata:
            merged_meta = dict(draft.metadata)
            merged_meta.update(metadata)
            draft = dataclasses.replace(draft, metadata=merged_meta)
        return await self._ingest_draft(draft, overwrite=overwrite)

    async def ingest_raw(
        self,
        raw_text: str,
        doc_slug: str,
        title: str,
        metadata: dict[str, object] | None = None,
        overwrite: bool = True,
        suffix: str = ".mdx",
    ) -> IngestionResult:
        import tempfile

        normalized_suffix = suffix if suffix.startswith(".") else f".{suffix}"
        with tempfile.NamedTemporaryFile("w", suffix=normalized_suffix, encoding="utf-8", delete=False) as f:
            f.write(raw_text)
            temp_path = Path(f.name)

        try:
            return await self.ingest_file(
                file_path=temp_path,
                doc_slug=doc_slug,
                title=title,
                metadata=metadata,
                overwrite=overwrite,
            )
        finally:
            temp_path.unlink(missing_ok=True)

    async def ingest_bytes(
        self,
        content: bytes,
        file_name: str,
        doc_slug: str,
        title: str,
        metadata: dict[str, object] | None = None,
        overwrite: bool = True,
    ) -> IngestionResult:
        import tempfile

        suffix = Path(file_name).suffix
        if not suffix:
            raise UnsupportedFrameworkError(
                f"File '{file_name}' has no extension; unable to determine framework parser."
            )
        with tempfile.NamedTemporaryFile("wb", suffix=suffix, delete=False) as f:
            f.write(content)
            temp_path = Path(f.name)

        try:
            return await self.ingest_file(
                file_path=temp_path,
                doc_slug=doc_slug,
                title=title,
                metadata=metadata,
                overwrite=overwrite,
            )
        finally:
            temp_path.unlink(missing_ok=True)

    async def ingest_corpus(
        self,
        file_paths: list[Path],
        corpus_root: Path,
        overwrite: bool = True,
    ) -> CorpusIngestionSummary:
        """Executes single-pass corpus ingestion atomically across all files via CodingParserRegistry."""
        total_chunks = 0
        total_edges = 0
        total_docs = 0
        skipped_docs = 0

        for idx, file_path in enumerate(file_paths, start=1):
            try:
                parser = CodingParserRegistry.get_parser(file_path)
                draft = parser.parse(file_path=file_path, corpus_root=corpus_root)
                res = await self._ingest_draft(draft, overwrite=overwrite)
                if res.skipped:
                    skipped_docs += 1
                    logger.info("(%d/%d) Skipped existing '%s'", idx, len(file_paths), draft.doc_slug)
                else:
                    total_docs += 1
                    total_chunks += res.chunks_count
                    total_edges += res.edges_count
                    logger.info(
                        "(%d/%d) Ingested '%s' (%d chunks)",
                        idx,
                        len(file_paths),
                        draft.doc_slug,
                        res.chunks_count,
                    )
            except Exception as exc:
                logger.error("Failed to ingest file %s: %s", file_path, exc)
                raise

        return CorpusIngestionSummary(
            total_documents=total_docs,
            total_chunks=total_chunks,
            total_edges=total_edges,
            skipped_documents=skipped_docs,
        )
