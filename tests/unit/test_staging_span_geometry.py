from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from rag_eval.exceptions import (
    E_AST_GROUNDING_VALIDATION,
    CorpusDomainError,
)
from rag_eval.ingestion.staging.manager import StagingManager
from rag_eval.ingestion.staging.models import (
    ChunkReviewStatus,
    ContextType,
    RelationType,
    StagingChunkDelta,
    StagingEdge,
    StagingEdgeInput,
    StagingStatus,
)
from rag_eval.web.services.promotion import HumanPromotionEngine


def test_staging_edge_span_geometry_invariants() -> None:
    """Verifies that StagingEdge rejects inverted, negative, or asymmetric coordinates while admitting valid intervals and dual-None."""
    # Dual-None is permitted (document-level / whole-chunk citation)
    edge_dual_none = StagingEdge(
        source_path="doc.sec1",
        target_path="doc.sec2",
        relation_type=RelationType.REFERENCES,
        char_start=None,
        char_end=None,
    )
    assert edge_dual_none.char_start is None
    assert edge_dual_none.char_end is None

    # Valid span interval
    edge_valid = StagingEdge(
        source_path="doc.sec1",
        target_path="doc.sec2",
        relation_type=RelationType.REFERENCES,
        char_start=10,
        char_end=25,
    )
    assert edge_valid.char_start == 10
    assert edge_valid.char_end == 25

    # Inverted interval (start > end)
    with pytest.raises(ValidationError):
        StagingEdge(
            source_path="doc.sec1",
            target_path="doc.sec2",
            relation_type=RelationType.REFERENCES,
            char_start=25,
            char_end=10,
        )

    # Degenerate interval (start == end)
    with pytest.raises(ValidationError):
        StagingEdge(
            source_path="doc.sec1",
            target_path="doc.sec2",
            relation_type=RelationType.REFERENCES,
            char_start=10,
            char_end=10,
        )

    # Negative coordinates
    with pytest.raises(ValidationError):
        StagingEdge(
            source_path="doc.sec1",
            target_path="doc.sec2",
            relation_type=RelationType.REFERENCES,
            char_start=-1,
            char_end=10,
        )

    with pytest.raises(ValidationError):
        StagingEdge(
            source_path="doc.sec1",
            target_path="doc.sec2",
            relation_type=RelationType.REFERENCES,
            char_start=0,
            char_end=-5,
        )

    # Asymmetric coordinate (start without end)
    with pytest.raises(ValidationError):
        StagingEdge(
            source_path="doc.sec1",
            target_path="doc.sec2",
            relation_type=RelationType.REFERENCES,
            char_start=10,
            char_end=None,
        )

    # Asymmetric coordinate (end without start)
    with pytest.raises(ValidationError):
        StagingEdge(
            source_path="doc.sec1",
            target_path="doc.sec2",
            relation_type=RelationType.REFERENCES,
            char_start=None,
            char_end=10,
        )


def test_attach_edges_resolves_anchor_text_to_coordinates(tmp_path: Path) -> None:
    """Verifies that validate_and_attach_edges_to_session resolves anchor_text substring to exact char_start and char_end offsets."""
    mgr = StagingManager(staging_dir=tmp_path)
    raw_content = "# Section 1\n\nPrefix token TARGET_SNIPPET Suffix token.\n\n# Section 2\n\nTarget content."
    mgr.create_session_from_raw(
        doc_slug="test_anchor_doc",
        title="Test Document",
        raw_text=raw_content,
    )

    session = mgr.load_session("test_anchor_doc")
    target_quote = "TARGET_SNIPPET"
    src_chunk = next(c for c in session.chunks if target_quote in c.verbatim_text)
    tgt_chunk = next(c for c in session.chunks if c.path != src_chunk.path)

    expected_start = src_chunk.verbatim_text.find(target_quote)
    expected_end = expected_start + len(target_quote)

    res = mgr.add_edges(
        doc_slug="test_anchor_doc",
        edges=[
            StagingEdgeInput(
                source_path=src_chunk.path,
                target_path=tgt_chunk.path,
                relation_type=RelationType.REFERENCES,
                anchor_text=target_quote,
            )
        ],
    )

    assert len(res.edges) == 1
    session_after = mgr.load_session("test_anchor_doc")
    assert len(session_after.edges) == 1
    attached_edge = session_after.edges[0]

    assert attached_edge.source_path == src_chunk.path
    assert attached_edge.target_path == tgt_chunk.path
    assert attached_edge.anchor_text == target_quote
    assert attached_edge.char_start == expected_start
    assert attached_edge.char_end == expected_end
    assert (
        src_chunk.verbatim_text[attached_edge.char_start : attached_edge.char_end]
        == target_quote
    )


def test_attach_edges_rejects_hallucinated_anchor_text(tmp_path: Path) -> None:
    """Verifies that validate_and_attach_edges_to_session raises E_AST_GROUNDING_VALIDATION when anchor_text is absent."""
    mgr = StagingManager(staging_dir=tmp_path)
    mgr.create_session_from_raw(
        doc_slug="test_hallucination_doc",
        title="Test Document",
        raw_text="# Section 1\n\nPure verbatim content.\n\n# Section 2\n\nTarget content.",
    )

    session = mgr.load_session("test_hallucination_doc")
    src_path = session.chunks[0].path
    tgt_path = session.chunks[1].path

    with pytest.raises(CorpusDomainError) as exc_info:
        mgr.add_edges(
            doc_slug="test_hallucination_doc",
            edges=[
                StagingEdgeInput(
                    source_path=src_path,
                    target_path=tgt_path,
                    relation_type=RelationType.REFERENCES,
                    anchor_text="NONEXISTENT_HALLUCINATED_QUOTE",
                )
            ],
        )

    assert exc_info.value.error_code == E_AST_GROUNDING_VALIDATION


def test_add_edges_with_direct_coordinates_and_bounds_validation(tmp_path: Path) -> None:
    """Verifies S-03: validating direct coordinates against chunk text bounds and anchor text integrity."""
    mgr = StagingManager(staging_dir=tmp_path)
    mgr.create_session_from_raw(
        doc_slug="test_bounds_doc",
        title="Test Document",
        raw_text="# Section 1\n\nShort text.\n\n# Section 2\n\nTarget content.",
    )

    session = mgr.load_session("test_bounds_doc")
    src_chunk = next(c for c in session.chunks if "Short text." in c.verbatim_text)
    tgt_chunk = next(c for c in session.chunks if "Target content." in c.verbatim_text)
    src_len = len(src_chunk.verbatim_text)

    # Out of bounds coordinates: char_end > src_len
    oob_edge = StagingEdge(
        source_path=src_chunk.path,
        target_path=tgt_chunk.path,
        relation_type=RelationType.REFERENCES,
        char_start=0,
        char_end=src_len + 10,
    )
    with pytest.raises(CorpusDomainError) as exc_info:
        mgr.add_edges(doc_slug="test_bounds_doc", edges=[oob_edge])
    assert exc_info.value.error_code == E_AST_GROUNDING_VALIDATION

    # Mismatched span vs anchor_text: coordinates slice does not match declared anchor_text
    mismatch_edge = StagingEdge(
        source_path=src_chunk.path,
        target_path=tgt_chunk.path,
        relation_type=RelationType.REFERENCES,
        char_start=0,
        char_end=5,
        anchor_text="MISMATCH_STRING",
    )
    with pytest.raises(CorpusDomainError) as exc_mismatch:
        mgr.add_edges(doc_slug="test_bounds_doc", edges=[mismatch_edge])
    assert exc_mismatch.value.error_code == E_AST_GROUNDING_VALIDATION


def test_attach_multiple_span_edges_between_same_chunk_pair_retained_across_reparent(
    tmp_path: Path,
) -> None:
    """Verifies S-04: multiple distinct span edges between the same chunk pair are retained and survive subtree reparenting."""
    mgr = StagingManager(staging_dir=tmp_path)
    mgr.create_session_from_raw(
        doc_slug="test_multi_span_doc",
        title="Test Document",
        raw_text="# Section 1\n\nToken TARGET_ONE middle tokens and TARGET_TWO.\n\n# Section 2\n\nReferred content.",
    )

    session = mgr.load_session("test_multi_span_doc")
    src_chunk = next(c for c in session.chunks if "TARGET_ONE" in c.verbatim_text)
    tgt_chunk = next(c for c in session.chunks if "Referred content" in c.verbatim_text)

    # Attach two distinct citation edges between the same chunk pair
    mgr.add_edges(
        doc_slug="test_multi_span_doc",
        edges=[
            StagingEdgeInput(
                source_path=src_chunk.path,
                target_path=tgt_chunk.path,
                relation_type=RelationType.REFERENCES,
                anchor_text="TARGET_ONE",
            ),
            StagingEdgeInput(
                source_path=src_chunk.path,
                target_path=tgt_chunk.path,
                relation_type=RelationType.REFERENCES,
                anchor_text="TARGET_TWO",
            ),
        ],
    )

    session_attached = mgr.load_session("test_multi_span_doc")
    assert len(session_attached.edges) == 2
    spans = {(e.char_start, e.char_end) for e in session_attached.edges}
    assert len(spans) == 2

    # Reparent subtree to verify 5-tuple deduplication retains both spans
    mgr.reparent_node(
        doc_slug="test_multi_span_doc",
        old_path_prefix="test_multi_span_doc.section_1",
        new_path_prefix="test_multi_span_doc.new_section_1",
    )

    session_reparented = mgr.load_session("test_multi_span_doc")
    assert len(session_reparented.edges) == 2
    reparented_spans = {(e.char_start, e.char_end) for e in session_reparented.edges}
    assert reparented_spans == spans
    for e in session_reparented.edges:
        assert e.source_path.startswith("test_multi_span_doc.new_section_1")


@pytest.mark.asyncio
async def test_promotion_propagates_resolved_spans(tmp_path: Path) -> None:
    """Verifies that HumanPromotionEngine maps resolved edge span coordinates to ChunkContextRefEntity."""
    mgr = StagingManager(staging_dir=tmp_path)
    raw_content = "# Section 1\n\nToken TARGET_PROMO_SNIPPET content.\n\n# Section 2\n\nTarget content."
    mgr.create_session_from_raw(
        doc_slug="doc_promo_test",
        title="Test Document",
        raw_text=raw_content,
    )

    session = mgr.load_session("doc_promo_test")
    quote = "TARGET_PROMO_SNIPPET"
    src_chunk = next(c for c in session.chunks if quote in c.verbatim_text)
    tgt_chunk = next(c for c in session.chunks if "Target content." in c.verbatim_text)

    # 1. Attach edge while chunks are in initial DRAFT
    mgr.add_edges(
        doc_slug="doc_promo_test",
        edges=[
            StagingEdgeInput(
                source_path=src_chunk.path,
                target_path=tgt_chunk.path,
                relation_type=RelationType.REFERENCES,
                anchor_text=quote,
            )
        ],
    )

    # 2. Update chunk context types and mark REVIEWED (source chunk has references, so REQUIRES_EXTERNAL_CONTEXT)
    mgr.patch_chunks(
        doc_slug="doc_promo_test",
        updated_chunks=[
            StagingChunkDelta(
                path=src_chunk.path,
                review_status=ChunkReviewStatus.REVIEWED,
                context_type=ContextType.REQUIRES_EXTERNAL_CONTEXT,
            ),
            StagingChunkDelta(
                path=tgt_chunk.path,
                review_status=ChunkReviewStatus.REVIEWED,
                context_type=ContextType.SELF_CONTAINED,
            ),
            *[
                StagingChunkDelta(
                    path=c.path,
                    review_status=ChunkReviewStatus.REVIEWED,
                    context_type=ContextType.SELF_CONTAINED,
                )
                for c in session.chunks
                if c.path not in (src_chunk.path, tgt_chunk.path)
            ],
        ],
    )

    # 3. Transition session to APPROVED
    mgr.update_session_status(
        doc_slug="doc_promo_test",
        status=StagingStatus.APPROVED,
        actor="HUMAN:reviewer",
        description="Approved for promotion",
    )

    # 4. Mock DB pool & bulk loader to capture ChunkContextRefEntity creation
    mock_pool = MagicMock()
    mock_conn = MagicMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
    mock_conn.transaction.return_value.__aenter__.return_value = mock_conn
    mock_conn.fetch = AsyncMock(return_value=[])
    mock_conn.execute = AsyncMock()

    with patch("rag_eval.web.services.promotion.PostgresBulkLoader") as mock_loader_cls:
        mock_loader = mock_loader_cls.return_value
        doc_uuid = uuid.uuid4()
        src_uuid = uuid.uuid4()
        tgt_uuid = uuid.uuid4()
        edge_uuid = uuid.uuid4()

        mock_loader.load_document = AsyncMock(return_value=doc_uuid)
        mock_loader.load_chunks = AsyncMock(
            return_value={src_chunk.path: src_uuid, tgt_chunk.path: tgt_uuid}
        )
        mock_loader.load_graph_edges = AsyncMock(
            return_value={(src_uuid, tgt_uuid, RelationType.REFERENCES.value): edge_uuid}
        )
        mock_loader.corpus_repo = MagicMock()
        mock_loader.corpus_repo.context_refs.batch_create_refs = AsyncMock()

        engine = HumanPromotionEngine(staging_manager=mgr)
        await engine.promote_session("doc_promo_test", compute_embeddings=False, pool=mock_pool)

        mock_loader.corpus_repo.context_refs.batch_create_refs.assert_awaited_once()
        created_refs = mock_loader.corpus_repo.context_refs.batch_create_refs.call_args[0][0]
        assert len(created_refs) == 1
        ref = created_refs[0]

        session_final = mgr.load_session("doc_promo_test")
        edge = session_final.edges[0]
        assert ref.char_start == edge.char_start
        assert ref.char_end == edge.char_end
        assert ref.char_start is not None
        assert ref.char_end is not None
        assert ref.edge_id == edge_uuid


