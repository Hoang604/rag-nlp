from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from typing import TYPE_CHECKING, Final

import asyncpg

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

from rag_eval.db.repositories import CorpusRepository
from rag_eval.exceptions import (
    E_CORPUS_INTEGRITY_VIOLATION,
    CorpusDomainError,
)
from rag_eval.schemas import (
    ChunkEntity,
    DocumentEntity,
    GraphEdgeEntity,
)

logger = logging.getLogger(__name__)

_embedding_model_cache: dict[str, SentenceTransformer] = {}
_embedding_load_lock: threading.Lock = threading.Lock()

DEFAULT_EMBEDDING_MODEL: Final[str] = "Qwen/Qwen3-Embedding-0.6B"
DEFAULT_EMBEDDING_DIM: Final[int] = 512


def get_embedding_model(
    model_name: str = DEFAULT_EMBEDDING_MODEL,
    truncate_dim: int = DEFAULT_EMBEDDING_DIM,
) -> SentenceTransformer | None:
    """Loads and caches the SentenceTransformer embedding model with GPU acceleration."""
    cache_key = f"{model_name}:{truncate_dim}"
    with _embedding_load_lock:
        if cache_key in _embedding_model_cache:
            return _embedding_model_cache[cache_key]

    try:
        import torch
        from sentence_transformers import SentenceTransformer

        device_env = os.environ.get("RAG_EMBEDDING_DEVICE")
        device = (
            device_env
            if device_env
            else ("cuda" if torch.cuda.is_available() else "cpu")
        )
        model_kwargs = (
            {"torch_dtype": torch.float16}
            if device == "cuda"
            else {"torch_dtype": torch.float32}
        )
        model = SentenceTransformer(
            model_name,
            truncate_dim=truncate_dim,
            model_kwargs=model_kwargs,
            device=device,
        )
        if model.tokenizer is not None:
            model.tokenizer.padding_side = "left"
        model.eval()
        if device == "cuda":
            logger.info(
                "Loaded embedding model %s (dim=%d) on GPU (CUDA FP16).",
                model_name,
                truncate_dim,
            )
        else:
            logger.info(
                "Loaded embedding model %s (dim=%d) on CPU.",
                model_name,
                truncate_dim,
            )

        _embedding_model_cache[cache_key] = model
        return model
    except (ImportError, RuntimeError, OSError, ValueError) as exc:
        logger.debug(
            "Failed to load sentence-transformers model %s: %s", model_name, exc
        )
        return None


def compute_chunk_embeddings(
    texts: list[str],
    model_name: str = DEFAULT_EMBEDDING_MODEL,
    batch_size: int = 16,
    is_query: bool = False,
    truncate_dim: int = DEFAULT_EMBEDDING_DIM,
) -> list[list[float]]:
    """Generates dense vector embeddings using sentence-transformers with GPU FP16 and inference_mode support."""
    if not texts:
        return []

    model = get_embedding_model(model_name, truncate_dim=truncate_dim)
    if model is None:
        raise CorpusDomainError(
            error_code=E_CORPUS_INTEGRITY_VIOLATION,
            message=f"Neural embedding model '{model_name}' could not be loaded or initialized.",
            data={"model_name": model_name},
        )

    if "e5" in model_name.lower():
        prefix = "query: " if is_query else "passage: "
        formatted = [
            f"{prefix}{t}" if not t.startswith(("query: ", "passage: ")) else t
            for t in texts
        ]
    else:
        formatted = texts

    try:
        try:
            import torch

            with torch.inference_mode():
                embeddings = model.encode(
                    formatted,
                    batch_size=batch_size,
                    normalize_embeddings=True,
                    show_progress_bar=len(texts) > 100,
                    convert_to_numpy=True,
                )
        except (ImportError, AttributeError):
            embeddings = model.encode(
                formatted,
                batch_size=batch_size,
                normalize_embeddings=True,
                show_progress_bar=len(texts) > 100,
                convert_to_numpy=True,
            )
        return [emb.tolist() for emb in embeddings]
    except Exception as exc:
        logger.error("Embedding generation failed: %s", exc)
        raise CorpusDomainError(
            error_code=E_CORPUS_INTEGRITY_VIOLATION,
            message=f"Neural embedding generation failed: {exc}",
            data={"model_name": model_name, "error": str(exc)},
        ) from exc


def _clean_metadata(metadata: object) -> dict[str, object]:
    from pydantic import BaseModel

    if isinstance(metadata, BaseModel):
        return metadata.model_dump(exclude_none=True)
    if isinstance(metadata, dict):
        return dict(metadata)
    if isinstance(metadata, str):
        try:
            decoded = json.loads(metadata)
            return dict(decoded) if isinstance(decoded, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


class PostgresBulkLoader:
    """Batch loader delegating 100% of database interactions to CorpusRepository."""

    def __init__(
        self,
        pool: asyncpg.Pool,
        compute_embeddings: bool = False,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
        corpus_repo: CorpusRepository | None = None,
    ) -> None:
        self.pool = pool
        self.compute_embeddings = compute_embeddings
        self.embedding_model = embedding_model
        self.corpus_repo = corpus_repo if corpus_repo is not None else CorpusRepository(pool)

    async def load_document(
        self, doc: DocumentEntity, conn: asyncpg.Connection | None = None
    ) -> uuid.UUID:
        """Upserts a document record via DocumentRepository."""
        return await self.corpus_repo.documents.upsert(doc, conn=conn)

    async def load_chunks(
        self,
        chunks: list[ChunkEntity],
        conn: asyncpg.Connection | None = None,
    ) -> dict[str, uuid.UUID]:
        """Upserts chunks with vector embedding and differential reconciliation via repositories."""
        if not chunks:
            return {}

        doc_id = chunks[0].document_id

        # Cache existing chunk embeddings to avoid redundant recomputations
        existing_chunks = await self.corpus_repo.chunks.list_by_document(doc_id, conn=conn)
        existing_cache = {
            c.path: (c.contextualized_text, c.embedding) for c in existing_chunks
        }

        embeddings: list[list[float] | None] = [None] * len(chunks)
        texts_to_embed: list[str] = []
        embed_indices: list[int] = []

        for idx, chunk in enumerate(chunks):
            if chunk.embedding is not None:
                embeddings[idx] = chunk.embedding
            else:
                cached = existing_cache.get(chunk.path)
                if (
                    cached is not None
                    and cached[0] == chunk.contextualized_text
                    and cached[1] is not None
                ):
                    embeddings[idx] = cached[1]
                elif self.compute_embeddings:
                    texts_to_embed.append(chunk.contextualized_text)
                    embed_indices.append(idx)
                else:
                    embeddings[idx] = chunk.embedding

        if self.compute_embeddings and texts_to_embed:
            computed = compute_chunk_embeddings(
                texts_to_embed, model_name=self.embedding_model
            )
            for pos, computed_emb in enumerate(computed):
                embeddings[embed_indices[pos]] = computed_emb

        incoming_paths = {c.path for c in chunks}
        existing_paths = set(existing_cache.keys())
        stale_paths = list(existing_paths - incoming_paths)

        if stale_paths:
            # Delete stale chunks and related edges via repository
            await self.corpus_repo.chunks.delete_stale_by_paths(doc_id, stale_paths, conn=conn)

        # Prepare typed ChunkEntities
        chunk_entities: list[ChunkEntity] = []
        for idx, chunk in enumerate(chunks):
            emb = embeddings[idx]
            meta = _clean_metadata(chunk.metadata)
            chunk_entities.append(
                ChunkEntity(
                    id=chunk.id,
                    document_id=chunk.document_id,
                    path=chunk.path,
                    verbatim_text=chunk.verbatim_text,
                    contextualized_text=chunk.contextualized_text,
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                    embedding=emb,
                    metadata=meta,
                )
            )

        return await self.corpus_repo.chunks.upsert_batch(chunk_entities, conn=conn)

    async def resolve_chunk_paths(
        self, paths: list[str], conn: asyncpg.Connection | None = None
    ) -> dict[str, uuid.UUID]:
        """Resolves existing chunk UUIDs by ltree paths via ChunkRepository."""
        return await self.corpus_repo.chunks.resolve_paths_batch(paths, conn=conn)

    async def load_graph_edges(
        self, edges: list[GraphEdgeEntity], conn: asyncpg.Connection | None = None
    ) -> dict[tuple[uuid.UUID, uuid.UUID, str], uuid.UUID]:
        """Upserts graph edges via GraphRepository after validating against DB catalog."""
        if not edges:
            return {}

        valid_edges: list[GraphEdgeEntity] = []
        for e in edges:
            if e.target_chunk_id is None:
                continue
            if e.source_chunk_id == e.target_chunk_id:
                continue
            valid_edges.append(
                GraphEdgeEntity(
                    id=e.id,
                    source_chunk_id=e.source_chunk_id,
                    target_chunk_id=e.target_chunk_id,
                    relation_type=e.relation_type,
                    rationale=e.rationale,
                )
            )

        return await self.corpus_repo.graph.upsert_edges(valid_edges, conn=conn)
