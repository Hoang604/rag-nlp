import pytest


@pytest.fixture
def sample_markdown_content() -> str:
    return (
        "# System Architecture Specification\n\n"
        "Section 1. System Scope\n"
        "This document defines the core architecture.\n\n"
        "## Subsystem Alpha\n"
        "All subsystem components must adhere to invariant contracts.\n"
    )
