from __future__ import annotations

from pathlib import Path

import pytest

from rag_eval.exceptions import (
    E_AST_GROUNDING_VALIDATION,
    E_CORPUS_INTEGRITY_VIOLATION,
    CorpusDomainError,
)
from rag_eval.ingestion.staging.manager import StagingManager
from rag_eval.ingestion.staging.models import (
    ChunkReviewStatus,
    ContextType,
    StagingChunk,
    StagingChunkDelta,
    StagingStatus,
)


def _setup_staged_session(
    tmp_path: Path, doc_slug: str = "doc_test"
) -> tuple[StagingManager, list[StagingChunk]]:
    mgr = StagingManager(staging_dir=tmp_path)
    session = mgr.create_session_from_raw(
        doc_slug=doc_slug,
        title="Test Document",
        raw_text="# Section 1\n\nParagraph text.",
    )
    deltas = [
        StagingChunkDelta(
            path=c.path,
            context_type=ContextType.SELF_CONTAINED,
            justification="Self contained section",
        )
        for c in session.chunks
    ]
    mgr.patch_chunks(doc_slug=doc_slug, updated_chunks=deltas)
    session = mgr.load_session(doc_slug)
    for c in session.chunks:
        session.get_chunk(c.path)
    mgr.save_session(session)
    mgr.finalize_chunks(doc_slug=doc_slug, paths=[c.path for c in session.chunks])
    return mgr, session.chunks


def test_uncommit_agent_committed_to_draft(tmp_path: Path) -> None:
    """Verifies S-01, I-01, I-02, I-05: AGENT_COMMITTED session reverts to DRAFT, cleanses committed_at, and preserves chunks/edges."""
    mgr, chunks = _setup_staged_session(tmp_path, "doc_draft_uncommit")
    doc_slug = "doc_draft_uncommit"

    # Commit session via domain commit_session
    committed_session = mgr.commit_session(doc_slug=doc_slug, actor="AGENT")
    assert committed_session.status == StagingStatus.AGENT_COMMITTED
    assert committed_session.committed_at is not None

    # Now uncommit
    uncommitted = mgr.uncommit_session(
        doc_slug=doc_slug, actor="AGENT", reason="Need to attach cross-ref edge"
    )
    assert uncommitted.status == StagingStatus.DRAFT
    assert uncommitted.committed_at is None
    assert len(uncommitted.chunks) == len(chunks)
    assert all(c.review_status == ChunkReviewStatus.REVIEWED for c in uncommitted.chunks)

    # In-memory materialized reload matches
    reloaded = mgr.load_session(doc_slug)
    assert reloaded.status == StagingStatus.DRAFT
    assert reloaded.committed_at is None


def test_uncommit_agent_committed_origin_aware_amendment(tmp_path: Path) -> None:
    """Verifies S-02, I-01, I-02: Session with amendment_baseline_snapshot reverts to AMENDMENT upon uncommit."""
    mgr, _ = _setup_staged_session(tmp_path, "doc_amend_uncommit")
    doc_slug = "doc_amend_uncommit"

    # Simulate PROMOTED -> reopen_session_for_amendment -> commit -> uncommit
    mgr.update_session_status(
        doc_slug=doc_slug, status=StagingStatus.PROMOTED, actor="SYSTEM", description="Promoted"
    )
    amended = mgr.reopen_session_for_amendment(doc_slug=doc_slug, actor="AGENT", reason="Add errata")
    assert amended.status == StagingStatus.AMENDMENT
    assert "amendment_baseline_snapshot" in amended.metadata

    # Commit the amended session
    committed_amend = mgr.commit_session(doc_slug=doc_slug, actor="AGENT")
    assert committed_amend.status == StagingStatus.AGENT_COMMITTED
    assert committed_amend.committed_at is not None

    # Uncommit must return to AMENDMENT (Origin-Aware)
    uncommitted = mgr.uncommit_session(doc_slug=doc_slug, actor="AGENT", reason="Need further edits")
    assert uncommitted.status == StagingStatus.AMENDMENT
    assert uncommitted.committed_at is None
    assert "amendment_baseline_snapshot" in uncommitted.metadata


def test_uncommit_idempotent_when_already_unlocked(tmp_path: Path) -> None:
    """Verifies S-03, I-01: uncommit is idempotent when session is already DRAFT or AMENDMENT."""
    mgr, _ = _setup_staged_session(tmp_path, "doc_idempotent")
    doc_slug = "doc_idempotent"

    # Already in DRAFT
    session_draft = mgr.load_session(doc_slug)
    assert session_draft.status == StagingStatus.DRAFT

    res = mgr.uncommit_session(doc_slug=doc_slug, actor="AGENT", reason="Idempotent check")
    assert res.status == StagingStatus.DRAFT


def test_uncommit_rejects_promoted_or_approved(tmp_path: Path) -> None:
    """Verifies S-04, I-01: uncommit strictly rejects sessions in PROMOTED or APPROVED status."""
    mgr, _ = _setup_staged_session(tmp_path, "doc_reject")
    doc_slug = "doc_reject"

    mgr.update_session_status(
        doc_slug=doc_slug, status=StagingStatus.APPROVED, actor="HUMAN:reviewer", description="Approved"
    )
    with pytest.raises(CorpusDomainError) as exc_info:
        mgr.uncommit_session(doc_slug=doc_slug, actor="AGENT")
    assert exc_info.value.error_code == E_CORPUS_INTEGRITY_VIOLATION
    assert "AGENT_COMMITTED" in exc_info.value.message

    # Transition to PROMOTED
    mgr.update_session_status(
        doc_slug=doc_slug, status=StagingStatus.PROMOTED, actor="SYSTEM", description="Promoted"
    )
    with pytest.raises(CorpusDomainError) as exc_info_promoted:
        mgr.uncommit_session(doc_slug=doc_slug, actor="AGENT")
    assert exc_info_promoted.value.error_code == E_CORPUS_INTEGRITY_VIOLATION


def test_uncommit_non_existent_session(tmp_path: Path) -> None:
    """Verifies S-05: uncommit raises E_CORPUS_INTEGRITY_VIOLATION for non-existent session."""
    mgr = StagingManager(staging_dir=tmp_path)
    with pytest.raises(CorpusDomainError) as exc_info:
        mgr.uncommit_session("non_existent_doc", actor="AGENT")
    assert exc_info.value.error_code == E_CORPUS_INTEGRITY_VIOLATION


def test_uncommit_wal_replay_determinism(tmp_path: Path) -> None:
    """Verifies S-06, I-03: WAL replay deterministically produces uncommitted DRAFT state with committed_at=None."""
    mgr, _ = _setup_staged_session(tmp_path, "doc_wal_replay")
    doc_slug = "doc_wal_replay"

    mgr.commit_session(doc_slug=doc_slug, actor="AGENT")
    mgr.uncommit_session(doc_slug=doc_slug, actor="AGENT", reason="Reverting for test")

    active_session = mgr.load_session(doc_slug)
    replayed_session, _lsn_count = mgr.replay_session(doc_slug)

    assert replayed_session.status == StagingStatus.DRAFT
    assert replayed_session.committed_at is None
    assert replayed_session.status == active_session.status
    assert replayed_session.committed_at == active_session.committed_at
    assert len(replayed_session.chunks) == len(active_session.chunks)


def test_update_session_status_prohibits_illegal_unlocked_transitions(tmp_path: Path) -> None:
    """Verifies S-08, I-01: update_session_status rejects arbitrary transitions to DRAFT or AMENDMENT on PROMOTED/APPROVED."""
    mgr, _ = _setup_staged_session(tmp_path, "doc_backdoor")
    doc_slug = "doc_backdoor"

    mgr.update_session_status(
        doc_slug=doc_slug, status=StagingStatus.APPROVED, actor="HUMAN:reviewer", description="Approved"
    )

    with pytest.raises(CorpusDomainError) as exc_info:
        mgr.update_session_status(
            doc_slug=doc_slug, status=StagingStatus.DRAFT, actor="ATTACKER", description="Bypass attempt"
        )
    assert exc_info.value.error_code == E_CORPUS_INTEGRITY_VIOLATION


def test_commit_session_domain_validation(tmp_path: Path) -> None:
    """Verifies I-05: commit_session validates 100% chunks reviewed and edge integrity at the domain level."""
    mgr = StagingManager(staging_dir=tmp_path)
    mgr.create_session_from_raw(
        doc_slug="doc_commit_val",
        title="Unreviewed Commit Doc",
        raw_text="Paragraph 1\n\nParagraph 2",
    )
    # Both chunks are PENDING
    with pytest.raises(CorpusDomainError) as exc_info:
        mgr.commit_session("doc_commit_val")
    assert exc_info.value.error_code == E_AST_GROUNDING_VALIDATION
    assert "PENDING" in exc_info.value.message
