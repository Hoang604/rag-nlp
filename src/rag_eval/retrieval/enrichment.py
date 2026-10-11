from __future__ import annotations

import logging
from dataclasses import dataclass

import asyncpg

from rag_eval.db.repositories import CorpusRepository
from rag_eval.exceptions import (
    E_AST_GROUNDING_VALIDATION,
    E_INVALID_DOCUMENT_HIERARCHY,
    CorpusDomainError,
)
from rag_eval.schemas import (
    GraphEdgeEntity,
    RelationType,
    validate_ltree_path,
)
from rag_eval.text import find_normalized_span

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LinkResult:
    source_path: str
    target_path: str
    relation_type: RelationType
    citation_text: str
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
        citation_text: str,
        rationale: str | None = None,
    ) -> LinkResult:
        """Thiết lập cạnh quan hệ giữa 2 chunk dựa trên LTree path và bằng chứng trích dẫn nguyên văn."""
        norm_source = validate_ltree_path(source_path)
        norm_target = validate_ltree_path(target_path)

        if norm_source == norm_target:
            raise CorpusDomainError(
                error_code=E_INVALID_DOCUMENT_HIERARCHY,
                message=f"Self-loop relations prohibited: source '{norm_source}' equals target '{norm_target}'.",
                data={"source_path": norm_source, "target_path": norm_target},
            )

        clean_citation = citation_text.strip()
        if not clean_citation:
            raise CorpusDomainError(
                error_code=E_AST_GROUNDING_VALIDATION,
                message="Citation text cannot be empty. All knowledge graph links must be grounded in source text.",
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

        # Retrieve source chunk to verify citation grounding
        src_chunk = await self.corpus_repo.chunks.get_by_path(norm_source)
        if src_chunk is None:
            raise CorpusDomainError(
                error_code=E_INVALID_DOCUMENT_HIERARCHY,
                message=f"Source chunk not found for path: '{norm_source}'.",
                data={"source_path": norm_source},
            )

        span = find_normalized_span(src_chunk.verbatim_text, clean_citation)
        if span is None:
            raise CorpusDomainError(
                error_code=E_AST_GROUNDING_VALIDATION,
                message=f"Citation text is not grounded in source chunk '{norm_source}' verbatim text.",
                data={"source_path": norm_source, "citation_text": clean_citation},
            )

        # Resolve target chunk UUID
        path_map = await self.corpus_repo.chunks.resolve_paths_batch([norm_target])
        tgt_id = path_map.get(norm_target)
        if tgt_id is None:
            raise CorpusDomainError(
                error_code=E_INVALID_DOCUMENT_HIERARCHY,
                message=f"Target chunk not found for path: '{norm_target}'.",
                data={"target_path": norm_target},
            )

        edge = GraphEdgeEntity(
            source_chunk_id=src_chunk.id,
            target_chunk_id=tgt_id,
            relation_type=rel_enum.value,
            rationale=rationale,
            citation_text=clean_citation,
        )
        await self.corpus_repo.graph.upsert_edges([edge])

        return LinkResult(
            source_path=norm_source,
            target_path=norm_target,
            relation_type=rel_enum,
            citation_text=clean_citation,
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
