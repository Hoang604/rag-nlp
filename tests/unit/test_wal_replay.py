from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from rag_eval.ingestion.staging.manager import StagingManager
from rag_eval.ingestion.staging.models import (
    ChunkReviewStatus,
    RelationType,
    StagingChunk,
    StagingEdge,
)
from rag_eval.ingestion.wal import GenesisSnapshot, WALSessionStore


def test_wal_concurrent_monotonic_lsn(tmp_path: Path) -> None:
    """Verifies that concurrent appends to WALSessionStore produce strictly monotonic LSNs under file locking."""
    wal_dir = tmp_path / "wal_concurrency"
    wal_dir.mkdir(parents=True, exist_ok=True)
    store = WALSessionStore(wal_dir)

    raw_text = "Section 1. Sample\nSample content."
    genesis = GenesisSnapshot.create(
        doc_slug="doc",
        title="Doc",
        raw_text=raw_text,
        initial_chunks=[
            StagingChunk(
                path="doc.sec_1",
                verbatim_text="Sample content.",
                contextualized_text="Sample content.",
                start_line=1,
                end_line=2,
            ).model_dump(mode="json")
        ],
    )
    store.init_genesis(genesis)

    num_threads = 20
    lsn_results: list[int] = []

    def append_worker(idx: int) -> int:
        rec, _ = store.append_record(
            actor=f"THREAD_{idx}",
            op_type="CHUNK_PATCHED",
            description=f"Concurrent patch {idx}",
            payload={"idx": idx},
        )
        return rec.lsn

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(append_worker, i) for i in range(num_threads)]
        for f in futures:
            lsn_results.append(f.result())

    # All LSNs must be unique, and when sorted must form a contiguous sequence 1..20
    assert len(lsn_results) == num_threads
    assert len(set(lsn_results)) == num_threads
    sorted_lsns = sorted(lsn_results)
    assert sorted_lsns == list(range(1, num_threads + 1))

    # O(1) head LSN check must match the highest LSN
    assert store.get_head_lsn() == num_threads


def test_wal_head_lsn_reverse_seek(tmp_path: Path) -> None:
    """Verifies that reverse-seek head LSN extraction works identically to sequential scans."""
    wal_dir = tmp_path / "wal_head"
    wal_dir.mkdir(parents=True, exist_ok=True)
    store = WALSessionStore(wal_dir)

    assert store.get_head_lsn() == -1

    genesis = GenesisSnapshot.create(
        doc_slug="doc_seek",
        title="Doc Seek",
        raw_text="Section 1. Content",
    )
    store.init_genesis(genesis)
    assert store.get_head_lsn() == 0

    store.append_record(
        actor="TEST",
        op_type="STATUS_CHANGED",
        description="status change",
        payload={"status": "IN_REVIEW"},
    )
    assert store.get_head_lsn() == 1


def test_deterministic_wal_replay(temp_staging_manager: StagingManager) -> None:
    """Verifies that replaying WAL from genesis snapshot yields state bitwise identical to materialized session."""
    doc_slug = "replay_doc"
    raw_text = "Section 1. Initial\nSection 2. Initial"
    temp_staging_manager.create_session_from_raw(
        doc_slug=doc_slug,
        title="Replay Doc",
        raw_text=raw_text,
    )

    chunks = [
        StagingChunk(
            path=f"{doc_slug}.sec_1",
            verbatim_text="Section 1 initial.",
            contextualized_text="Section 1 initial.",
            start_line=1,
            end_line=1,
        ),
        StagingChunk(
            path=f"{doc_slug}.sec_2",
            verbatim_text="Section 2 initial.",
            contextualized_text="Section 2 initial.",
            start_line=2,
            end_line=2,
        ),
    ]
    temp_staging_manager.patch_chunks(doc_slug=doc_slug, updated_chunks=chunks)

    # Apply chunk patch edit
    updated_chunk = StagingChunk(
        path=f"{doc_slug}.sec_1",
        verbatim_text="Section 1 modified.",
        contextualized_text="Section 1 modified.",
        start_line=1,
        end_line=1,
    )
    temp_staging_manager.patch_chunks(
        doc_slug=doc_slug,
        updated_chunks=[updated_chunk],
    )

    # Attach edge
    edge = StagingEdge(
        source_path=f"{doc_slug}.sec_1",
        target_path=f"{doc_slug}.sec_2",
        relation_type=RelationType.REFERENCES,
    )
    temp_staging_manager.add_edges(doc_slug=doc_slug, edges=[edge])

    # Finalize chunk
    temp_staging_manager.finalize_chunks(
        doc_slug=doc_slug,
        paths=[f"{doc_slug}.sec_1"],
    )

    # Active session state
    active_session = temp_staging_manager.load_session(doc_slug)

    # Replay session independently
    replayed_session, lsn_count = temp_staging_manager.replay_session(doc_slug)

    assert lsn_count == 4
    assert len(replayed_session.chunks) == len(active_session.chunks)
    assert len(replayed_session.edges) == len(active_session.edges)

    # Verify chunk properties match
    replayed_c1 = next(c for c in replayed_session.chunks if c.path == f"{doc_slug}.sec_1")
    active_c1 = next(c for c in active_session.chunks if c.path == f"{doc_slug}.sec_1")
    assert replayed_c1.verbatim_text == "Section 1 modified."
    assert replayed_c1.verbatim_text == active_c1.verbatim_text
    assert replayed_c1.review_status == ChunkReviewStatus.REVIEWED
    assert active_c1.review_status == ChunkReviewStatus.REVIEWED


def test_edge_deduplication_preserves_distinct_target_edges(
    temp_staging_manager: StagingManager,
) -> None:
    """Verifies that multiple distinct target edges from the same source are preserved without clobbering."""
    doc_slug = "cite_doc"
    raw_text = "Section 1. Content\nSection 2. Target A\nSection 3. Target B"
    temp_staging_manager.create_session_from_raw(
        doc_slug=doc_slug,
        title="Cite Doc",
        raw_text=raw_text,
    )
    chunks = [
        StagingChunk(
            path=f"{doc_slug}.sec_1",
            verbatim_text="Section 1.",
            contextualized_text="Section 1.",
            start_line=1,
            end_line=1,
        ),
        StagingChunk(
            path=f"{doc_slug}.sec_2",
            verbatim_text="Section 2.",
            contextualized_text="Section 2.",
            start_line=2,
            end_line=2,
        ),
        StagingChunk(
            path=f"{doc_slug}.sec_3",
            verbatim_text="Section 3.",
            contextualized_text="Section 3.",
            start_line=3,
            end_line=3,
        ),
    ]
    temp_staging_manager.patch_chunks(doc_slug=doc_slug, updated_chunks=chunks)

    edge_1 = StagingEdge(
        source_path=f"{doc_slug}.sec_1",
        target_path=f"{doc_slug}.sec_2",
        relation_type=RelationType.REFERENCES,
    )
    edge_2 = StagingEdge(
        source_path=f"{doc_slug}.sec_1",
        target_path=f"{doc_slug}.sec_3",
        relation_type=RelationType.REFERENCES,
    )

    temp_staging_manager.add_edges(doc_slug=doc_slug, edges=[edge_1, edge_2])

    session = temp_staging_manager.load_session(doc_slug)
    assert len(session.edges) == 2
    targets = {e.target_path for e in session.edges}
    assert f"{doc_slug}.sec_2" in targets
    assert f"{doc_slug}.sec_3" in targets
