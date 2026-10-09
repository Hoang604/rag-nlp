from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from rag_eval.exceptions import (
    E_AST_GROUNDING_VALIDATION,
    E_INVALID_DOCUMENT_HIERARCHY,
    CorpusDomainError,
)
from rag_eval.ingestion.staging.manager import StagingManager
from rag_eval.ingestion.staging.models import (
    ChunkReviewStatus,
    ContextType,
    FinalizationState,
    RelationType,
    StagingChunkDelta,
    StagingEdge,
    StagingEdgeFilter,
    StagingStatus,
    StagingViolationCode,
)
from rag_eval.mcp.tools.staging import CorpusStagingTools
from rag_eval.web.services.validation import PreFlightValidator


def _setup_test_session(
    tmp_path: Path, doc_slug: str = "doc_test", raw_text: str = "# Header\n\nParagraph text."
) -> tuple[StagingManager, CorpusStagingTools]:
    mgr = StagingManager(staging_dir=tmp_path)
    mgr.create_session_from_raw(
        doc_slug=doc_slug,
        title="Test Document",
        raw_text=raw_text,
    )
    tools = CorpusStagingTools(staging_manager=mgr)
    return mgr, tools


@pytest.mark.asyncio
async def test_bounded_poll_pending_clamps_to_max_limit(tmp_path: Path) -> None:
    """Verifies that stg_poll_pending_chunks strictly clamps requested limit to [1, 15] with default 10."""
    mgr, tools = _setup_test_session(
        tmp_path, "doc_poll", raw_text="\n\n".join(f"# S{i}\n\nP{i}" for i in range(1, 25))
    )

    # Request limit=50 when ceiling is 15
    res = await tools.stg_poll_pending_chunks(doc_slug="doc_poll", limit=50)
    assert res.limit == 15
    assert res.returned_chunks == 15

    # Request limit=0 (or below min 1)
    res_min = await tools.stg_poll_pending_chunks(doc_slug="doc_poll", limit=0)
    assert res_min.limit == 1
    assert res_min.returned_chunks == 1

    # Request default limit
    res_def = await tools.stg_poll_pending_chunks(doc_slug="doc_poll")
    assert res_def.limit == 10
    assert res_def.returned_chunks == 10

    # Verify that queue polling never mutates inspected_paths
    session = mgr.load_session("doc_poll")
    assert len(session.inspected_paths) == 0


@pytest.mark.asyncio
async def test_poll_pending_grouped_hierarchy(tmp_path: Path) -> None:
    """Verifies that pending leaf chunks are grouped under their immediate parent with non-mutating ancestor lookup."""
    mgr, tools = _setup_test_session(
        tmp_path, "doc_group", raw_text="# Section 1\n\nParagraph 1.\n\nParagraph 2."
    )
    res = await tools.stg_poll_pending_chunks(doc_slug="doc_group", limit=10)
    assert res.returned_chunks >= 2
    assert len(res.groups) >= 1
    for grp in res.groups:
        assert grp.parent_path is not None
        assert grp.parent_context is not None
        for chunk in grp.chunks:
            assert chunk.path.startswith(grp.parent_path) or grp.parent_path == "doc_group"

    session = mgr.load_session("doc_group")
    assert len(session.inspected_paths) == 0


@pytest.mark.asyncio
async def test_stg_grep_returns_compact_snippets(tmp_path: Path) -> None:
    """Verifies that stg_grep returns compact GrepHit snippets with bold markdown highlights."""
    _, tools = _setup_test_session(
        tmp_path, "doc_grep", raw_text="# Điều 1\n\nQuy định về quản lý an toàn thông tin."
    )
    res = await tools.stg_grep(pattern="quản lý", doc_slug="doc_grep", limit=5)
    assert res.total_matches >= 1
    assert len(res.hits) >= 1
    hit = res.hits[0]
    assert hit.doc_slug == "doc_grep"
    assert "**quản lý**" in hit.snippet
    assert hit.start_line >= 1
    assert hit.end_line >= 1
    assert not hasattr(hit, "verbatim_text")


@pytest.mark.asyncio
async def test_finalize_uninspected_chunk_raises_violation(tmp_path: Path) -> None:
    """Verifies that attempting to finalize an uninspected chunk triggers UNINSPECTED_CHUNK domain error."""
    mgr, tools = _setup_test_session(tmp_path, "doc_uninspected")
    session = mgr.load_session("doc_uninspected")
    target_path = session.chunks[0].path

    with pytest.raises(CorpusDomainError) as exc_info:
        await tools.stg_finalize_chunks(doc_slug="doc_uninspected", paths=[target_path])

    assert exc_info.value.error_code == E_AST_GROUNDING_VALIDATION
    assert exc_info.value.data is not None
    assert exc_info.value.data.get("violation_code") == StagingViolationCode.UNINSPECTED_CHUNK.value
    assert exc_info.value.data.get("path") == target_path
    hint = exc_info.value.data.get("remediation_hint")
    assert isinstance(hint, str) and len(hint.strip()) > 0
    assert "context_type=" not in hint


@pytest.mark.asyncio
async def test_finalize_unclassified_chunk_raises_violation(tmp_path: Path) -> None:
    """Verifies that finalizing an inspected chunk without explicit context_type raises UNCLASSIFIED_CHUNK."""
    mgr, tools = _setup_test_session(tmp_path, "doc_unclass")
    session = mgr.load_session("doc_unclass")
    target_path = session.chunks[0].path

    # Mark inspected via get_chunk
    await tools.stg_get_chunk(doc_slug="doc_unclass", path=target_path)

    with pytest.raises(CorpusDomainError) as exc_info:
        await tools.stg_finalize_chunks(doc_slug="doc_unclass", paths=[target_path])

    assert exc_info.value.error_code == E_AST_GROUNDING_VALIDATION
    assert exc_info.value.data is not None
    assert exc_info.value.data.get("violation_code") == StagingViolationCode.UNCLASSIFIED_CHUNK.value
    hint = exc_info.value.data.get("remediation_hint")
    assert isinstance(hint, str) and len(hint.strip()) > 0
    assert "context_type=" not in hint


@pytest.mark.asyncio
async def test_finalize_missing_edge_for_external_context_raises_violation(tmp_path: Path) -> None:
    """Verifies that REQUIRES_EXTERNAL_CONTEXT chunk without graph edges raises MISSING_RELATION_EDGE."""
    mgr, tools = _setup_test_session(tmp_path, "doc_missing_edge")
    session = mgr.load_session("doc_missing_edge")
    target_path = session.chunks[0].path

    # 1. Inspect chunk
    await tools.stg_get_chunk(doc_slug="doc_missing_edge", path=target_path)

    # 2. Patch as REQUIRES_EXTERNAL_CONTEXT without edges
    await tools.stg_patch(
        doc_slug="doc_missing_edge",
        updated_chunks=[
            StagingChunkDelta(
                path=target_path,
                context_type=ContextType.REQUIRES_EXTERNAL_CONTEXT,
                justification="Needs reference link",
            )
        ],
    )

    with pytest.raises(CorpusDomainError) as exc_info:
        await tools.stg_finalize_chunks(doc_slug="doc_missing_edge", paths=[target_path])

    assert exc_info.value.error_code == E_AST_GROUNDING_VALIDATION
    assert exc_info.value.data is not None
    assert exc_info.value.data.get("violation_code") == StagingViolationCode.MISSING_RELATION_EDGE.value
    hint = exc_info.value.data.get("remediation_hint")
    assert isinstance(hint, str) and len(hint.strip()) > 0
    assert "context_type=" not in hint
    assert "(1)" in hint and "(2)" in hint


@pytest.mark.asyncio
async def test_finalize_self_contained_with_edges_raises_violation(tmp_path: Path) -> None:
    """Verifies that SELF_CONTAINED chunk having an outgoing edge raises INVALID_RELATION_ON_SELF_CONTAINED."""
    mgr, tools = _setup_test_session(tmp_path, "doc_invalid_rel")
    session = mgr.load_session("doc_invalid_rel")
    src_path = session.chunks[0].path
    tgt_path = session.chunks[1].path

    # Add edge
    mgr.add_edges(
        "doc_invalid_rel",
        edges=[
            StagingEdge(
                source_path=src_path,
                target_path=tgt_path,
                relation_type=RelationType.REFERENCES,
            )
        ],
    )

    # Inspect and patch as SELF_CONTAINED
    await tools.stg_get_chunk(doc_slug="doc_invalid_rel", path=src_path)
    await tools.stg_patch(
        doc_slug="doc_invalid_rel",
        updated_chunks=[
            StagingChunkDelta(
                path=src_path,
                context_type=ContextType.SELF_CONTAINED,
                justification="Standalone text",
            )
        ],
    )

    with pytest.raises(CorpusDomainError) as exc_info:
        await tools.stg_finalize_chunks(doc_slug="doc_invalid_rel", paths=[src_path])

    assert exc_info.value.error_code == E_AST_GROUNDING_VALIDATION
    assert exc_info.value.data is not None
    assert exc_info.value.data.get("violation_code") == StagingViolationCode.INVALID_RELATION_ON_SELF_CONTAINED.value
    hint = exc_info.value.data.get("remediation_hint")
    assert isinstance(hint, str) and len(hint.strip()) > 0
    assert "context_type=" not in hint
    assert "(1)" in hint and "(2)" in hint


@pytest.mark.asyncio
async def test_finalize_valid_self_contained_and_linked_chunks(tmp_path: Path) -> None:
    """Verifies successful finalization for both SELF_CONTAINED and REQUIRES_EXTERNAL_CONTEXT chunks."""
    mgr, tools = _setup_test_session(tmp_path, "doc_valid")
    session = mgr.load_session("doc_valid")
    chunk0_path = session.chunks[0].path
    chunk1_path = session.chunks[1].path

    # 1. Inspect both chunks
    await tools.stg_get_chunk(doc_slug="doc_valid", path=chunk0_path)
    await tools.stg_get_chunk(doc_slug="doc_valid", path=chunk1_path)

    # 2. Add edge from chunk1 to chunk0
    mgr.add_edges(
        "doc_valid",
        edges=[
            StagingEdge(
                source_path=chunk1_path,
                target_path=chunk0_path,
                relation_type=RelationType.REFERENCES,
            )
        ],
    )

    # 3. Patch chunk0 as SELF_CONTAINED, chunk1 as REQUIRES_EXTERNAL_CONTEXT
    await tools.stg_patch(
        doc_slug="doc_valid",
        updated_chunks=[
            StagingChunkDelta(
                path=chunk0_path,
                context_type=ContextType.SELF_CONTAINED,
                justification="Header chunk",
            ),
            StagingChunkDelta(
                path=chunk1_path,
                context_type=ContextType.REQUIRES_EXTERNAL_CONTEXT,
                justification="References chunk 0",
            ),
        ],
    )

    # 4. Finalize both
    res = await tools.stg_finalize_chunks(
        doc_slug="doc_valid",
        paths=[chunk0_path, chunk1_path],
    )
    assert res.finalized_count == 2

    reloaded = mgr.load_session("doc_valid")
    c0 = reloaded.get_chunk(chunk0_path)
    c1 = reloaded.get_chunk(chunk1_path)
    assert c0 is not None and c1 is not None
    assert c0.review_status == ChunkReviewStatus.REVIEWED
    assert c0.finalization_state == FinalizationState.FINALIZED_SELF_CONTAINED
    assert c1.review_status == ChunkReviewStatus.REVIEWED
    assert c1.finalization_state == FinalizationState.FINALIZED_FULLY_LINKED

    # 5. PreFlightValidator Rule 8 verifies cleanly
    validator = PreFlightValidator()
    report = validator.validate(reloaded)
    rule8_summary = report.summary.get("chunk_review_completion")
    assert isinstance(rule8_summary, dict)
    assert rule8_summary["passed"] is True
    assert report.passed is True


@pytest.mark.asyncio
async def test_stg_commit_transitions_session_to_agent_committed(tmp_path: Path) -> None:
    """Verifies that stg_commit locks session to AGENT_COMMITTED status."""
    mgr, tools = _setup_test_session(tmp_path, "doc_commit")
    session = mgr.load_session("doc_commit")
    for c in session.chunks:
        await tools.stg_get_chunk(doc_slug="doc_commit", path=c.path)
        await tools.stg_patch(
            doc_slug="doc_commit",
            updated_chunks=[
                StagingChunkDelta(
                    path=c.path,
                    context_type=ContextType.SELF_CONTAINED,
                    justification="Autonomous section",
                )
            ],
        )
    await tools.stg_finalize_chunks(
        doc_slug="doc_commit",
        paths=[c.path for c in session.chunks],
    )

    commit_res = await tools.stg_commit("doc_commit")
    assert commit_res.status == StagingStatus.AGENT_COMMITTED.value
    committed_session = mgr.load_session("doc_commit")
    assert committed_session.status == StagingStatus.AGENT_COMMITTED


@pytest.mark.asyncio
async def test_stg_unfinalize_chunks_reverts_state_and_evicts_inspection(tmp_path: Path) -> None:
    """Verifies that stg_unfinalize_chunks reverts REVIEWED chunk to PENDING, resets finalization_state, and evicts inspected_paths."""
    mgr, tools = _setup_test_session(tmp_path, "doc_unfinalize")
    session = mgr.load_session("doc_unfinalize")
    target_path = session.chunks[0].path

    # First inspect, patch context_type, and finalize
    await tools.stg_get_chunk(doc_slug="doc_unfinalize", path=target_path)
    await tools.stg_patch(
        doc_slug="doc_unfinalize",
        updated_chunks=[
            StagingChunkDelta(
                path=target_path,
                context_type=ContextType.SELF_CONTAINED,
                justification="Self contained section",
            )
        ],
    )
    fin_res = await tools.stg_finalize_chunks(doc_slug="doc_unfinalize", paths=[target_path])
    assert fin_res.finalized_count == 1

    # Verify finalized in session
    session = mgr.load_session("doc_unfinalize")
    assert session.chunks[0].review_status == ChunkReviewStatus.REVIEWED
    assert target_path in session.inspected_paths

    # Now unfinalize
    unfin_res = await tools.stg_unfinalize_chunks(doc_slug="doc_unfinalize", paths=[target_path])
    assert unfin_res.status == "SUCCESS"
    assert unfin_res.unfinalized_count == 1

    session = mgr.load_session("doc_unfinalize")
    assert session.chunks[0].review_status == ChunkReviewStatus.PENDING
    assert session.chunks[0].finalization_state == FinalizationState.UNFINALIZED
    assert target_path not in session.inspected_paths

    # Attempting to unfinalize non-existent path raises E_INVALID_DOCUMENT_HIERARCHY
    with pytest.raises(CorpusDomainError) as exc_info:
        await tools.stg_unfinalize_chunks(doc_slug="doc_unfinalize", paths=["nonexistent.chunk"])
    assert exc_info.value.error_code == E_INVALID_DOCUMENT_HIERARCHY


@pytest.mark.asyncio
async def test_stg_grep_global_sessions(tmp_path: Path) -> None:
    """Verifies that passing doc_slug=None searches across all discovered active sessions (S-03)."""
    mgr = StagingManager(staging_dir=tmp_path)
    mgr.create_session_from_raw(
        doc_slug="doc_alpha",
        title="Document Alpha",
        raw_text="# Section 1\n\nCommon term identifier alpha.",
    )
    mgr.create_session_from_raw(
        doc_slug="doc_beta",
        title="Document Beta",
        raw_text="# Section 2\n\nCommon term identifier beta.",
    )
    tools = CorpusStagingTools(staging_manager=mgr)

    res = await tools.stg_grep(pattern="Common term", doc_slug=None, limit=10)
    assert res.doc_slug is None
    assert res.total_matches >= 2
    slugs = {h.doc_slug for h in res.hits}
    assert "doc_alpha" in slugs
    assert "doc_beta" in slugs


@pytest.mark.asyncio
async def test_stg_remove_edges_typed_filter(tmp_path: Path) -> None:
    """Verifies that stg_remove_edges removes specified edges via typed list[StagingEdgeFilter] (S-04 / I-03)."""
    mgr, tools = _setup_test_session(tmp_path, "doc_edge_rem", raw_text="# S1\n\nP1\n\n# S2\n\nP2")
    session = mgr.load_session("doc_edge_rem")
    p1 = session.chunks[0].path
    p2 = session.chunks[1].path

    mgr.add_edges(
        "doc_edge_rem",
        edges=[
            StagingEdge(source_path=p1, target_path=p2, relation_type=RelationType.REFERENCES)
        ],
    )
    reloaded = mgr.load_session("doc_edge_rem")
    assert len(reloaded.edges) == 1

    flt = StagingEdgeFilter(source_path=p1, target_path=p2)
    res = await tools.stg_remove_edges(doc_slug="doc_edge_rem", edges=[flt])
    assert res.status == "SUCCESS"
    assert res.removed_count == 1
    assert res.total_edges == 0

    # Ensure StagingEdgeFilter forbids extra fields
    with pytest.raises(ValidationError):
        StagingEdgeFilter.model_validate({"source_path": p1, "extra_field": "bad"})


def test_staging_chunk_delta_forbids_extra_and_status() -> None:
    """Verifies that StagingChunkDelta rejects undeclared extra keys and status alterations (S-08 / I-05)."""
    with pytest.raises(ValidationError):
        StagingChunkDelta.model_validate({"path": "doc.sec_1", "review_status": "REVIEWED"})

    with pytest.raises(ValidationError):
        StagingChunkDelta.model_validate({"path": "doc.sec_1", "invalid_extra_key": "exploit"})

