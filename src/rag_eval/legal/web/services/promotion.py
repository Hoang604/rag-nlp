from __future__ import annotations

import datetime
import logging
import uuid

import asyncpg

from rag_eval.legal.db.connection import get_db_pool
from rag_eval.legal.exceptions import (
    E_AST_GROUNDING_VALIDATION,
    E_CORPUS_INTEGRITY_VIOLATION,
    CorpusDomainError,
)
from rag_eval.legal.ingestion.loader import (
    PostgresBulkLoader,
    compute_chunk_embeddings,
)
from rag_eval.legal.ingestion.staging.manager import StagingManager
from rag_eval.legal.ingestion.staging.models import ChunkReviewStatus, StagingStatus
from rag_eval.legal.schemas import (
    ChunkContextRefEntity,
    ChunkEntity,
    DocumentEntity,
    FinalizationState,
    GraphEdgeEntity,
)
from rag_eval.legal.web.schemas import PromotionResultResponse
from rag_eval.legal.web.services.validation import PreFlightValidator

logger = logging.getLogger(__name__)


class HumanPromotionEngine:
    """Executes atomic promotion of approved staging sessions into PostgreSQL production tables."""

    def __init__(
        self,
        staging_manager: StagingManager | None = None,
        validator: PreFlightValidator | None = None,
    ) -> None:
        self.staging_manager = staging_manager or StagingManager()
        self.validator = validator or PreFlightValidator()

    async def promote_session(
        self,
        doc_slug: str,
        reviewer_notes: str | None = None,
        compute_embeddings: bool = True,
        pool: asyncpg.Pool | None = None,
    ) -> PromotionResultResponse:
        """Validates and atomically promotes a staging session into PostgreSQL."""
        session, _ = self.staging_manager.replay_session(doc_slug)

        # 100% review gate & status preconditions
        if session.status not in (StagingStatus.AGENT_COMMITTED, StagingStatus.APPROVED):
            raise CorpusDomainError(
                error_code=E_AST_GROUNDING_VALIDATION,
                message=f"Session status '{session.status.value}' is not eligible for promotion. Must be AGENT_COMMITTED or APPROVED.",
                data={"status": session.status.value},
            )

        unreviewed = [c.path for c in session.chunks if c.review_status != ChunkReviewStatus.REVIEWED]
        if unreviewed:
            raise CorpusDomainError(
                error_code=E_AST_GROUNDING_VALIDATION,
                message=f"Cannot promote session with {len(unreviewed)} unreviewed chunk(s). All chunks must be in REVIEWED status.",
                data={"unreviewed_count": len(unreviewed), "sample_paths": unreviewed[:10]},
            )

        validation = self.validator.validate(session)
        if not validation.passed:
            violation_msgs = [f"[{i.rule}] {i.message}" for i in validation.issues if i.blocking]
            error_details = "; ".join(violation_msgs)
            raise CorpusDomainError(
                error_code=E_CORPUS_INTEGRITY_VIOLATION,
                message=f"Pre-flight validation failed with {len(violation_msgs)} blocking issue(s): {error_details}",
                data={"issues": [i.model_dump() for i in validation.issues]},
            )

        # Compute neural embeddings OUTSIDE database transaction to eliminate transaction bloat
        computed_embeddings: list[list[float]] = []
        if compute_embeddings and session.chunks:
            texts_to_embed = [c.contextualized_text for c in session.chunks]
            computed_embeddings = compute_chunk_embeddings(texts_to_embed)

        target_pool = pool if pool is not None else await get_db_pool()
        loader = PostgresBulkLoader(pool=target_pool, compute_embeddings=False)

        doc_entity = DocumentEntity(
            doc_slug=session.doc_slug,
            title=session.title,
            valid_from=session.valid_from,
            valid_to=session.valid_to,
            metadata=session.metadata,
            raw_text=session.raw_text,
        )

        async with target_pool.acquire() as conn, conn.transaction():
            doc_id = await loader.load_document(doc_entity, conn=conn)

            chunk_edges_count: dict[str, int] = {}
            for edge in session.edges:
                chunk_edges_count[edge.source_path] = chunk_edges_count.get(edge.source_path, 0) + 1

            canonical_chunks = [
                ChunkEntity(
                    document_id=doc_id,
                    path=c.path,
                    verbatim_text=c.verbatim_text,
                    contextualized_text=c.contextualized_text,
                    start_line=c.start_line,
                    end_line=c.end_line,
                    context_type=(
                        "SELF_CONTAINED"
                        if (
                            c.finalization_state == FinalizationState.FINALIZED_SELF_CONTAINED
                            and chunk_edges_count.get(c.path, 0) == 0
                        )
                        else "REQUIRES_EXTERNAL_CONTEXT"
                    ),
                    is_all_refs_resolved=(
                        c.finalization_state == FinalizationState.FINALIZED_SELF_CONTAINED
                        and chunk_edges_count.get(c.path, 0) == 0
                    ),
                    embedding=computed_embeddings[idx] if computed_embeddings else None,
                    metadata=c.metadata,
                )
                for idx, c in enumerate(session.chunks)
            ]
            path_to_uuid = await loader.load_chunks(canonical_chunks, conn=conn)

            # Prune stale edges and context refs for existing document chunks to prevent duplicate & FK errors
            doc_chunk_ids = list(path_to_uuid.values())
            if doc_chunk_ids:
                await conn.execute(
                    "DELETE FROM chunk_context_refs WHERE chunk_id = ANY($1::uuid[]);",
                    doc_chunk_ids,
                )
                await loader.corpus_repo.graph.delete_edges_for_chunks(doc_chunk_ids, conn=conn)

            unresolved_target_paths: list[str] = [
                e.target_path
                for e in session.edges
                if e.target_path and e.target_path not in path_to_uuid
            ]

            external_path_to_uuid: dict[str, uuid.UUID] = {}
            if unresolved_target_paths:
                external_path_to_uuid = await loader.resolve_chunk_paths(
                    unresolved_target_paths, conn=conn
                )

            graph_edge_entities: list[GraphEdgeEntity] = []
            for edge in session.edges:
                src_uuid = path_to_uuid.get(edge.source_path)
                if src_uuid is None:
                    raise CorpusDomainError(
                        error_code=E_CORPUS_INTEGRITY_VIOLATION,
                        message=f"Source chunk '{edge.source_path}' was not assigned a valid UUID during promotion.",
                        data={"source_path": edge.source_path},
                    )

                tgt_uuid = None
                if edge.target_path:
                    if edge.target_path in path_to_uuid:
                        tgt_uuid = path_to_uuid[edge.target_path]
                    elif edge.target_path in external_path_to_uuid:
                        tgt_uuid = external_path_to_uuid[edge.target_path]

                if tgt_uuid is not None:
                    rel_val = edge.relation_type.value
                    graph_edge_entities.append(
                        GraphEdgeEntity(
                            id=uuid.uuid4(),
                            source_chunk_id=src_uuid,
                            target_chunk_id=tgt_uuid,
                            relation_type=rel_val,
                        )
                    )

            edge_map: dict[tuple[uuid.UUID, uuid.UUID, str], uuid.UUID] = {}
            if graph_edge_entities:
                edge_map = await loader.load_graph_edges(graph_edge_entities, conn=conn)

            # Build chunk_context_refs with authoritative edge IDs from edge_map
            chunk_context_refs: list[ChunkContextRefEntity] = []
            for edge in session.edges:
                src_uuid = path_to_uuid.get(edge.source_path)
                if src_uuid is None:
                    continue

                tgt_uuid = None
                if edge.target_path:
                    if edge.target_path in path_to_uuid:
                        tgt_uuid = path_to_uuid[edge.target_path]
                    elif edge.target_path in external_path_to_uuid:
                        tgt_uuid = external_path_to_uuid[edge.target_path]

                if tgt_uuid is not None:
                    rel_val = edge.relation_type.value if hasattr(edge.relation_type, "value") else str(edge.relation_type)
                    persisted_edge_id = edge_map.get((src_uuid, tgt_uuid, rel_val))
                    if persisted_edge_id is not None:
                        chunk_context_refs.append(
                            ChunkContextRefEntity(
                                id=uuid.uuid4(),
                                chunk_id=src_uuid,
                                target_chunk_id=tgt_uuid,
                                edge_id=persisted_edge_id,
                            )
                        )

            if chunk_context_refs:
                await loader.corpus_repo.context_refs.batch_create_refs(chunk_context_refs, conn=conn)

            fully_linked_uuids = [
                path_to_uuid[c.path]
                for c in session.chunks
                if c.finalization_state == FinalizationState.FINALIZED_FULLY_LINKED
                and c.path in path_to_uuid
            ]
            if fully_linked_uuids:
                await conn.execute(
                    "UPDATE chunks SET is_all_refs_resolved = TRUE WHERE id = ANY($1::uuid[])",
                    fully_linked_uuids,
                )

        now = datetime.datetime.now(datetime.UTC)
        self.staging_manager.update_session_status(
            doc_slug=session.doc_slug,
            status=StagingStatus.PROMOTED,
            actor="HUMAN:reviewer",
            description=f"Promoted to production PostgreSQL (doc_id: {doc_id}). Notes: {reviewer_notes or 'None'}",
        )

        return PromotionResultResponse(
            status="SUCCESS",
            doc_slug=session.doc_slug,
            document_id=str(doc_id),
            chunks_promoted=len(canonical_chunks),
            edges_promoted=len(edge_map),
            promoted_at=now.isoformat(),
            message=(
                f"Document '{session.doc_slug}' has been approved and committed to PostgreSQL "
                f"({len(canonical_chunks)} chunks, {len(edge_map)} graph edges)."
            ),
        )
