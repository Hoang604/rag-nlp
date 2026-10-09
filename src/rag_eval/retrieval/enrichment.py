from __future__ import annotations

import logging
from dataclasses import dataclass

import asyncpg

from rag_eval.db.repositories import CorpusRepository
from rag_eval.exceptions import (
    E_INVALID_DOCUMENT_HIERARCHY,
    CorpusDomainError,
)
from rag_eval.schemas import (
    GraphEdgeEntity,
    RelationType,
    validate_ltree_path,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LinkResult:
    source_path: str
    target_path: str
    relation_type: RelationType
    created: bool
    rationale: str | None = None


@dataclass(frozen=True)
class UnlinkResult:
    source_path: str
    target_path: str
    removed_edges_count: int


class KnowledgeEnrichmentService:
    """Enriches and rectifies knowledge graph relations dynamically at retrieval runtime."""

    def __init__(
        self,
        pool: asyncpg.Pool,
        corpus_repo: CorpusRepository | None = None,
    ) -> None:
        self.pool = pool
        self.corpus_repo = corpus_repo if corpus_repo is not None else CorpusRepository(pool)

    async def link_chunks(
        self,
        source_path: str,
        target_path: str,
        relation_type: RelationType | str,
        rationale: str | None = None,
    ) -> LinkResult:
        """Thiết lập cạnh quan hệ giữa 2 chunk dựa trên LTree path."""
        norm_source = validate_ltree_path(source_path)
        norm_target = validate_ltree_path(target_path)

        if norm_source == norm_target:
            raise CorpusDomainError(
                error_code=E_INVALID_DOCUMENT_HIERARCHY,
                message=f"Self-loop relations prohibited: source '{norm_source}' equals target '{norm_target}'.",
                data={"source_path": norm_source, "target_path": norm_target},
            )

        if isinstance(relation_type, str):
            try:
                rel_enum = RelationType(relation_type)
            except ValueError as exc:
                raise CorpusDomainError(
                    error_code=E_INVALID_DOCUMENT_HIERARCHY,
                    message=f"Invalid relation_type '{relation_type}'. Must be one of valid catalog codes.",
                    data={"relation_type": relation_type},
                ) from exc
        else:
            rel_enum = relation_type

        # Resolve chunk UUIDs
        path_map = await self.corpus_repo.chunks.resolve_paths_batch([norm_source, norm_target])
        src_id = path_map.get(norm_source)
        tgt_id = path_map.get(norm_target)

        if src_id is None:
            raise CorpusDomainError(
                error_code=E_INVALID_DOCUMENT_HIERARCHY,
                message=f"Source chunk not found for path: '{norm_source}'.",
                data={"source_path": norm_source},
            )
        if tgt_id is None:
            raise CorpusDomainError(
                error_code=E_INVALID_DOCUMENT_HIERARCHY,
                message=f"Target chunk not found for path: '{norm_target}'.",
                data={"target_path": norm_target},
            )

        edge = GraphEdgeEntity(
            source_chunk_id=src_id,
            target_chunk_id=tgt_id,
            relation_type=rel_enum.value,
            rationale=rationale,
        )
        await self.corpus_repo.graph.upsert_edges([edge])

        return LinkResult(
            source_path=norm_source,
            target_path=norm_target,
            relation_type=rel_enum,
            created=True,
            rationale=rationale,
        )

    async def unlink_chunks(
        self,
        source_path: str,
        target_path: str,
        relation_type: RelationType | str | None = None,
    ) -> UnlinkResult:
        """Gỡ bỏ cạnh quan hệ giữa 2 chunk dựa trên LTree path."""
        norm_source = validate_ltree_path(source_path)
        norm_target = validate_ltree_path(target_path)

        rel_code: str | None = None
        if relation_type is not None:
            rel_code = (
                relation_type.value
                if isinstance(relation_type, RelationType)
                else str(relation_type)
            )

        path_map = await self.corpus_repo.chunks.resolve_paths_batch([norm_source, norm_target])
        src_id = path_map.get(norm_source)
        tgt_id = path_map.get(norm_target)

        if src_id is None or tgt_id is None:
            return UnlinkResult(
                source_path=norm_source,
                target_path=norm_target,
                removed_edges_count=0,
            )

        removed_count = await self.corpus_repo.graph.delete_directed_edge(
            source_chunk_id=src_id,
            target_chunk_id=tgt_id,
            relation_type=rel_code,
        )

        return UnlinkResult(
            source_path=norm_source,
            target_path=norm_target,
            removed_edges_count=removed_count,
        )
