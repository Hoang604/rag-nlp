from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar

from rag_eval.exceptions import E_CORPUS_INTEGRITY_VIOLATION, CorpusDomainError
from rag_eval.schemas import ParsedDocumentDraft

logger = logging.getLogger(__name__)


class UnsupportedFrameworkError(CorpusDomainError):
    """Raised when no dedicated framework parser is registered for a given technical documentation file."""

    def __init__(self, message: str) -> None:
        super().__init__(error_code=E_CORPUS_INTEGRITY_VIOLATION, message=message)


class BaseCodingParser(ABC):
    """Abstract base contract for framework-specific technical documentation parsers."""

    name: str

    @abstractmethod
    def can_handle(self, file_path: Path, raw_text: str = "") -> bool:
        """Returns True if this parser is explicitly designed for the given file and framework."""
        ...

    @abstractmethod
    def parse(
        self,
        file_path: Path,
        doc_slug: str | None = None,
        corpus_root: Path | None = None,
    ) -> ParsedDocumentDraft:
        """Parses the technical documentation file into a complete ParsedDocumentDraft."""
        ...


class CodingParserRegistry:
    """Central registry managing dedicated framework technical documentation parsers."""

    _parsers: ClassVar[list[BaseCodingParser]] = []

    @classmethod
    def register(cls, parser: BaseCodingParser) -> None:
        """Registers a framework parser instance in the registry."""
        # Avoid duplicate registrations of the same parser name
        for existing in cls._parsers:
            if existing.name == parser.name:
                return
        cls._parsers.append(parser)
        logger.info("Registered framework parser: %s", parser.name)

    @classmethod
    def get_parser(cls, file_path: Path, raw_text: str = "") -> BaseCodingParser:
        """Dispatches to the matching framework parser, or raises UnsupportedFrameworkError.

        Enforces zero silent fallbacks: any document format without a registered
        dedicated parser fails fast.
        """
        resolved_path = Path(file_path).resolve()
        for parser in cls._parsers:
            if parser.can_handle(resolved_path, raw_text):
                return parser

        raise UnsupportedFrameworkError(
            f"No framework parser registered for '{resolved_path.name}'. "
            f"Implement and register a dedicated BaseCodingParser in CodingParserRegistry."
        )

    @classmethod
    def registered_parsers(cls) -> list[str]:
        """Returns the list of currently registered parser names."""
        return [p.name for p in cls._parsers]

    @classmethod
    def clear(cls) -> None:
        """Clears all registered parsers (strictly for isolated testing)."""
        cls._parsers.clear()
