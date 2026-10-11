from __future__ import annotations

import datetime
import logging
import uuid

import asyncpg

from rag_eval.db.repositories import CorpusRepository
from rag_eval.exceptions import (
    E_AST_GROUNDING_VALIDATION,
    E_INVALID_DOCUMENT_HIERARCHY,
    CorpusDomainError,
)
from rag_eval.schemas import (
    CurateEdgesResult,
    EdgeKey,
    EdgeLogEntity,
    EdgeProposal,
    GraphEdgeEntity,
    RelationType,
    validate_ltree_path,
)
from rag_eval.text import find_normalized_span

logger = logging.getLogger(__name__)


class KnowledgeEnrichmentService:
    """Enriches and rectifies knowledge graph relations dynamically at retrieval runtime."""

    def __init__(
        self,
        pool: asyncpg.Pool,
        corpus_repo: CorpusRepository | None = None,
    ) -> None:
        self.pool = pool
        self.corpus_repo = corpus_repo if corpus_repo is not None else CorpusRepository(pool)

    async def curate_edges(
        self,
        add_edges: list[EdgeProposal] | None = None,
        remove_edges: list[EdgeKey] | None = None,
        reason: str = "",
        actor: str = "AGENT",
    ) -> CurateEdgesResult:
        """Executes atomic batch edge addition and removal within a single PostgreSQL transaction.
        Pre-flight verifies citation span grounding, expands container paths symmetrically,
        rejects self-loops, and appends audit events to graph_edge_log.
        """
        clean_reason = reason.strip()
        if not clean_reason:
            raise CorpusDomainError(
                error_code=E_AST_GROUNDING_VALIDATION,
                message="reason là bắt buộc: ghi rõ mục đích hoặc ngữ cảnh nhiệm vụ phục vụ kiểm toán.",
                data={"violation_code": "MISSING_REASON"},
            )

        proposals = [
            EdgeProposal(
                source_path=validate_ltree_path(e.source_path),
                target_path=validate_ltree_path(e.target_path),
                relation_type=e.relation_type,
                citation_text=e.citation_text.strip(),
                rationale=e.rationale,
            )
            for e in (add_edges or [])
        ]

        for proposal in proposals:
            try:
                RelationType(proposal.relation_type)
            except ValueError as exc:
                raise CorpusDomainError(
                    error_code=E_INVALID_DOCUMENT_HIERARCHY,
                    message=f"Mã quan hệ '{proposal.relation_type}' không hợp lệ trong danh mục hệ thống.",
                    data={"relation_type": proposal.relation_type, "violation_code": "INVALID_RELATION_TYPE"},
                ) from exc
            if proposal.source_path == proposal.target_path:
                raise CorpusDomainError(
                    error_code=E_INVALID_DOCUMENT_HIERARCHY,
                    message=f"Không thể tạo liên kết tự thân (self-loop) trên chunk '{proposal.source_path}'.",
                    data={"source_path": proposal.source_path, "target_path": proposal.target_path, "violation_code": "SELF_REFERENCING_EDGE"},
                )

        remove_keys = [
            EdgeKey(
                source_path=validate_ltree_path(e.source_path),
                target_path=validate_ltree_path(e.target_path),
                relation_type=e.relation_type,
            )
            for e in (remove_edges or [])
        ]

        # Symmetrically collect paths to expand/resolve
        all_sources = list({e.source_path for e in proposals} | {e.source_path for e in remove_keys})
        all_targets = list({e.target_path for e in proposals} | {e.target_path for e in remove_keys})

        async with self.pool.acquire() as conn, conn.transaction():
            sources = await self.corpus_repo.chunks.get_verbatim_by_paths(all_sources, conn=conn)
            targets = await self.corpus_repo.chunks.expand_to_leaf_paths(all_targets, conn=conn)
            now = datetime.datetime.now(datetime.UTC)

            violations: list[dict[str, object]] = []
            planned_additions: dict[tuple[uuid.UUID, uuid.UUID, str], tuple[EdgeKey, GraphEdgeEntity]] = {}

            for proposal in proposals:
                source = sources.get(proposal.source_path)
                leaves = targets.get(proposal.target_path, [])
                if source is None:
                    violations.append({
                        "violation_code": "SOURCE_NOT_FOUND",
                        "source_path": proposal.source_path,
                        "target_path": proposal.target_path,
                        "message": f"Source chunk '{proposal.source_path}' does not exist in database.",
                    })
                    continue
                if not leaves:
                    violations.append({
                        "violation_code": "TARGET_NOT_FOUND",
                        "source_path": proposal.source_path,
                        "target_path": proposal.target_path,
                        "message": f"Target path '{proposal.target_path}' does not match any chunk at or under it.",
                    })
                    continue

                source_id, source_text = source
                if not proposal.citation_text:
                    violations.append({
                        "violation_code": "EMPTY_CITATION_TEXT",
                        "source_path": proposal.source_path,
                        "target_path": proposal.target_path,
                        "message": "Citation text cannot be empty.",
                    })
                    continue

                if find_normalized_span(source_text, proposal.citation_text) is None:
                    violations.append({
                        "violation_code": "UNGROUNDED_CITATION_TEXT",
                        "source_path": proposal.source_path,
                        "target_path": proposal.target_path,
                        "message": f"Citation text is not grounded in source chunk '{proposal.source_path}' verbatim text.",
                    })
                    continue

                other_leaves = [(path, cid) for path, cid in leaves if cid != source_id]
                if not other_leaves:
                    violations.append({
                        "violation_code": "SELF_REFERENCING_EDGE",
                        "source_path": proposal.source_path,
                        "target_path": proposal.target_path,
                        "message": "Target consists exclusively of the source chunk itself (self-loops prohibited).",
                    })
                    continue

                for leaf_path, leaf_id in other_leaves:
                    key_tuple = (source_id, leaf_id, proposal.relation_type)
                    if key_tuple not in planned_additions:
                        planned_additions[key_tuple] = (
                            EdgeKey(
                                source_path=proposal.source_path,
                                target_path=leaf_path,
                                relation_type=proposal.relation_type,
                            ),
                            GraphEdgeEntity(
                                id=uuid.uuid4(),
                                source_chunk_id=source_id,
                                target_chunk_id=leaf_id,
                                relation_type=proposal.relation_type,
                                rationale=proposal.rationale,
                                citation_text=proposal.citation_text,
                                created_at=now,
                            ),
                        )

            if violations:
                raise CorpusDomainError(
                    error_code=E_AST_GROUNDING_VALIDATION,
                    message=f"{len(violations)} edge proposals are invalid; zero edges written.",
                    data={"violation_code": violations[0]["violation_code"], "violations": violations},
                )

            # Insert added edges
            new_entities = [entity for _, entity in planned_additions.values()]
            inserted = await self.corpus_repo.graph.insert_edges_atomic(new_entities, conn=conn)
            inserted_ids = {e.id for e in inserted}

            added_keys = [key for key, entity in planned_additions.values() if entity.id in inserted_ids]
            existing_keys = [key for key, entity in planned_additions.values() if entity.id not in inserted_ids]

            # Log ADDED events
            add_events = [
                EdgeLogEntity(
                    id=uuid.uuid4(),
                    action="ADDED",
                    actor=actor,
                    source_path=key.source_path,
                    target_path=key.target_path,
                    relation_type=key.relation_type,
                    citation_text=entity.citation_text,
                    reason=clean_reason,
                    created_at=now,
                )
                for key, entity in planned_additions.values()
                if entity.id in inserted_ids
            ]
            await self.corpus_repo.graph.log_edge_events(add_events, conn=conn)

            # Process Removals: expand container paths symmetrically
            expanded_remove_triples: list[tuple[str, str, str]] = []
            for rk in remove_keys:
                leaves = targets.get(rk.target_path, [])
                if leaves:
                    for leaf_path, _ in leaves:
                        expanded_remove_triples.append((rk.source_path, leaf_path, rk.relation_type))
                else:
                    expanded_remove_triples.append((rk.source_path, rk.target_path, rk.relation_type))

            found_edges = await self.corpus_repo.graph.find_edges(expanded_remove_triples, conn=conn)
            for edge_id, _, _, _, _ in found_edges:
                await self.corpus_repo.graph.delete_edge(edge_id, conn=conn)

            removed_keys = [
                EdgeKey(source_path=s, target_path=t, relation_type=r)
                for _, s, t, r, _ in found_edges
            ]
            # Log REMOVED events
            remove_events = [
                EdgeLogEntity(
                    id=uuid.uuid4(),
                    action="REMOVED",
                    actor=actor,
                    source_path=s,
                    target_path=t,
                    relation_type=r,
                    citation_text=cit,
                    reason=clean_reason,
                    created_at=now,
                )
                for _, s, t, r, cit in found_edges
            ]
            await self.corpus_repo.graph.log_edge_events(remove_events, conn=conn)

            found_triple_set = {(s, t, r) for _, s, t, r, _ in found_edges}
            not_found_keys = [
                rk for rk in remove_keys
                if not any((rk.source_path, leaf_path, rk.relation_type) in found_triple_set
                           for leaf_path, _ in targets.get(rk.target_path, [(rk.target_path, None)]))
            ]

        return CurateEdgesResult(
            added=added_keys,
            existing=existing_keys,
            removed=removed_keys,
            not_found=not_found_keys,
            message=f"Added {len(added_keys)} edges ({len(existing_keys)} existing); removed {len(removed_keys)} edges ({len(not_found_keys)} not found).",
        )
