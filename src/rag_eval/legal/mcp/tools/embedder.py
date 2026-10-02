from __future__ import annotations

import asyncio
from typing import Protocol, final

from rag_eval.legal.ingestion.loader import (
    DEFAULT_EMBEDDING_MODEL,
    compute_chunk_embeddings,
)


class QueryEmbedder(Protocol):
    """Encodes a search query into a dense vector for hybrid_search."""

    async def embed_query(self, query: str) -> list[float] | None: ...


@final
class SentenceTransformerQueryEmbedder:
    """Default embedder using Qwen3-Embedding-0.6B with 512-dim MRL truncation.

    Documents and queries are embedded using Qwen/Qwen3-Embedding-0.6B with
    truncate_dim=512 and L2 normalization for cosine similarity search.
    """

    def __init__(self, model_name: str = DEFAULT_EMBEDDING_MODEL) -> None:
        self._model_name = model_name

    async def embed_query(self, query: str) -> list[float] | None:
        vectors = await asyncio.to_thread(
            compute_chunk_embeddings,
            [query],
            model_name=self._model_name,
            is_query=True,
        )
        if not vectors:
            return None
        return vectors[0]
