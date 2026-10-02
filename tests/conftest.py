from pathlib import Path

import pytest

from rag_eval.legal.ingestion.staging.manager import StagingManager
from rag_eval.legal.ingestion.staging.models import StagingChunk
from rag_eval.legal.ingestion.staging.session import StagingDocumentSession


@pytest.fixture
def temp_staging_dir(tmp_path: Path) -> Path:
    staging_path = tmp_path / "staging"
    staging_path.mkdir(parents=True, exist_ok=True)
    return staging_path


@pytest.fixture
def temp_staging_manager(temp_staging_dir: Path) -> StagingManager:
    return StagingManager(staging_dir=temp_staging_dir)


@pytest.fixture
def sample_staging_session(temp_staging_manager: StagingManager) -> StagingDocumentSession:
    doc_slug = "test_doc_01"
    raw_text = (
        "Section 1. System Scope\n"
        "This document defines the core architecture.\n"
        "Section 2. Applicability\n"
        "All subsystem components must adhere to invariant contracts."
    )
    temp_staging_manager.create_session_from_raw(
        doc_slug=doc_slug,
        title="Technical Architecture Specification",
        raw_text=raw_text,
    )
    chunks = [
        StagingChunk(
            path=f"{doc_slug}.sec_1",
            verbatim_text="Section 1. System Scope\nThis document defines the core architecture.",
            contextualized_text="[Document: test_doc_01] Section 1. System Scope",
            start_line=1,
            end_line=2,
        ),
        StagingChunk(
            path=f"{doc_slug}.sec_2",
            verbatim_text="Section 2. Applicability\nAll subsystem components must adhere to invariant contracts.",
            contextualized_text="[Document: test_doc_01] Section 2. Applicability",
            start_line=3,
            end_line=4,
        ),
    ]
    temp_staging_manager.patch_chunks(doc_slug=doc_slug, updated_chunks=chunks)
    return temp_staging_manager.load_session(doc_slug)
