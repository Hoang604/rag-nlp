from __future__ import annotations

from pathlib import Path

import pytest

from rag_eval.ingestion.registry import (
    BaseCodingParser,
    CodingParserRegistry,
    UnsupportedFrameworkError,
)
from rag_eval.schemas import ParsedDocumentDraft


class DummyMockParser(BaseCodingParser):
    name = "mock_framework"

    def can_handle(self, file_path: Path, raw_text: str = "") -> bool:
        return file_path.name.endswith(".mock")

    def parse(
        self,
        file_path: Path,
        doc_slug: str | None = None,
        corpus_root: Path | None = None,
    ) -> ParsedDocumentDraft:
        return ParsedDocumentDraft(
            doc_slug="mock_slug",
            title="Mock Title",
            raw_text="mock content",
            chunks=[],
            edges=[],
            metadata={},
        )


def test_registry_unregistered_file_raises_unsupported_framework() -> None:
    CodingParserRegistry.clear()
    unknown_file = Path("docs/unsupported.vue")

    with pytest.raises(UnsupportedFrameworkError) as exc_info:
        CodingParserRegistry.get_parser(unknown_file)

    assert "No framework parser registered" in str(exc_info.value)
    assert "unsupported.vue" in str(exc_info.value)


def test_registry_register_and_dispatch() -> None:
    CodingParserRegistry.clear()
    parser = DummyMockParser()
    CodingParserRegistry.register(parser)

    assert CodingParserRegistry.registered_parsers() == ["mock_framework"]

    mock_file = Path("guide.mock")
    matched = CodingParserRegistry.get_parser(mock_file)
    assert matched.name == "mock_framework"

    draft = matched.parse(mock_file)
    assert draft.doc_slug == "mock_slug"
