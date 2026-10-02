from __future__ import annotations

import asyncio
import collections
import logging
import threading
from typing import Final, Protocol, Self

from sentence_transformers import CrossEncoder

logger = logging.getLogger(__name__)

DEFAULT_MODEL: Final = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
DEFAULT_MAX_LENGTH: Final = 256
DEFAULT_BLEND: Final = 1.0

_reranker_model_cache: dict[tuple[str, int], CrossEncoder] = {}
_model_load_lock: threading.Lock = threading.Lock()


class Reranked(Protocol):
    path: str
    contextualized_text: str
    score: float

    def model_copy(self, *, update: dict[str, object] | None = None) -> Self: ...


class CorpusReranker(Protocol):
    """Protocol for corpus provision rerankers reading candidate pairs against queries."""

    async def rerank[T: Reranked](
        self, query: str, hits: list[T], top_k: int | None = None
    ) -> list[T]: ...


class ThreadSafeScoreCache:
    """Bounded thread-safe LRU cache for cross-encoder query-passage scores."""

    def __init__(self, maxsize: int = 2048) -> None:
        self._cache: collections.OrderedDict[tuple[str, str], float] = collections.OrderedDict()
        self._maxsize: int = maxsize
        self._lock: threading.Lock = threading.Lock()

    def get(self, key: tuple[str, str]) -> float | None:
        with self._lock:
            if key not in self._cache:
                return None
            self._cache.move_to_end(key)
            return self._cache[key]

    def put(self, key: tuple[str, str], value: float) -> None:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = value
            if len(self._cache) > self._maxsize:
                self._cache.popitem(last=False)

    def __contains__(self, key: tuple[str, str]) -> bool:
        with self._lock:
            return key in self._cache

    def __len__(self) -> int:
        with self._lock:
            return len(self._cache)


class CrossEncoderReranker:
    """Reorders retrieved provisions by reading them against the question.

    The model loads lazily and once. Left to the first request it costs several
    seconds on the person waiting, so callers that care should warm it.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        max_length: int = DEFAULT_MAX_LENGTH,
        blend: float = DEFAULT_BLEND,
        model: CrossEncoder | None = None,
        max_cache_size: int = 2048,
    ) -> None:
        self._model_name = model_name
        self._max_length = max_length
        self._blend = blend
        self._model: CrossEncoder | None = model
        self._score_cache = ThreadSafeScoreCache(maxsize=max_cache_size)

    @property
    def blend(self) -> float:
        """How much of the order comes from the cross-encoder, 0..1."""
        return self._blend

    @blend.setter
    def blend(self, value: float) -> None:
        self._blend = value

    def _load(self) -> CrossEncoder:
        if self._model is not None:
            return self._model

        with _model_load_lock:
            if self._model is not None:
                return self._model

            cache_key = (self._model_name, self._max_length)
            if cache_key in _reranker_model_cache:
                self._model = _reranker_model_cache[cache_key]
                return self._model

            try:
                import torch
                from sentence_transformers import CrossEncoder

                device = "cuda" if torch.cuda.is_available() else "cpu"
                model = CrossEncoder(
                    self._model_name, max_length=self._max_length, device=device
                )
                if hasattr(model, "model") and hasattr(model.model, "eval"):
                    model.model.eval()
                if (
                    device == "cuda"
                    and hasattr(model, "model")
                    and hasattr(model.model, "half")
                ):
                    model.model.half()
                    logger.info(
                        "Loaded CrossEncoder %s on GPU (CUDA FP16).", self._model_name
                    )
                else:
                    logger.info("Loaded CrossEncoder %s on CPU.", self._model_name)

                _reranker_model_cache[cache_key] = model
                self._model = model
                return model
            except (ImportError, RuntimeError, OSError, ValueError) as exc:
                logger.debug(
                    "Failed to load CrossEncoder with acceleration %s: %s, fallback to basic load",
                    self._model_name,
                    exc,
                )
                from sentence_transformers import CrossEncoder

                model = CrossEncoder(self._model_name, max_length=self._max_length)
                _reranker_model_cache[cache_key] = model
                self._model = model
                return model

    async def warm(self) -> None:
        await asyncio.to_thread(self._load)

    def _score_sync(self, query: str, texts: list[str]) -> list[float]:
        pairs = [(query, text) for text in texts]
        results: list[float | None] = [None] * len(pairs)
        uncached_indices: list[int] = []
        uncached_pairs: list[tuple[str, str]] = []

        for idx, pair in enumerate(pairs):
            cached_val = self._score_cache.get(pair)
            if cached_val is not None:
                results[idx] = cached_val
            else:
                uncached_indices.append(idx)
                uncached_pairs.append(pair)

        if uncached_pairs:
            model = self._load()
            try:
                import torch

                with torch.inference_mode():
                    raw_scores = model.predict(
                        uncached_pairs,
                        batch_size=32,
                        show_progress_bar=False,
                        convert_to_numpy=True,
                    )
            except (ImportError, AttributeError, TypeError):
                raw_scores = model.predict(uncached_pairs)

            scores_list = [float(s) for s in raw_scores]
            for idx, score in zip(uncached_indices, scores_list, strict=False):
                results[idx] = score
                self._score_cache.put(pairs[idx], score)

        return [s if s is not None else 0.0 for s in results]

    async def score(self, query: str, texts: list[str]) -> list[float]:
        if not texts:
            return []
        return await asyncio.to_thread(self._score_sync, query, texts)

    async def rerank[T: Reranked](
        self, query: str, hits: list[T], top_k: int | None = None
    ) -> list[T]:
        """Returns hits reordered by cross-encoder relevance."""
        if not hits:
            return []

        if len(hits) == 1:
            hit = hits[0]
            text = (
                getattr(hit, "contextualized_text", "")
                or getattr(hit, "verbatim_text", "")
            )
            scores = await self.score(query, [text])
            score_val = scores[0] if scores else 0.0
            return [hit.model_copy(update={"rerank_score": score_val})]

        texts = [
            getattr(h, "contextualized_text", "") or getattr(h, "verbatim_text", "")
            for h in hits
        ]
        scores = await self.score(query, texts)

        if self._blend >= 1.0:
            order = sorted(range(len(hits)), key=lambda i: -scores[i])
        else:
            by_ce = sorted(range(len(hits)), key=lambda i: -scores[i])
            ce_rank = {index: rank for rank, index in enumerate(by_ce, start=1)}
            order = sorted(
                range(len(hits)),
                key=lambda i: (
                    -(
                        self._blend / (60 + ce_rank[i])
                        + (1.0 - self._blend) / (60 + i + 1)
                    )
                ),
            )

        reordered: list[T] = []
        for position in order:
            hit = hits[position]
            hit = hit.model_copy(update={"rerank_score": scores[position]})
            reordered.append(hit)
        return reordered[:top_k] if top_k else reordered
