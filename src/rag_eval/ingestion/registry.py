from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar

from rag_eval.exceptions import E_CORPUS_INTEGRITY_VIOLATION, CorpusDomainError
from rag_eval.schemas import ParsedDocumentDraft, canonicalize_ltree_path

logger = logging.getLogger(__name__)


class UnsupportedFrameworkError(CorpusDomainError):
    """Raised when no dedicated framework parser is registered for a given technical documentation file."""

    def __init__(self, message: str) -> None:
        super().__init__(error_code=E_CORPUS_INTEGRITY_VIOLATION, message=message)


class BaseCodingParser(ABC):
    """Abstract base contract for framework-specific technical documentation parsers."""

    name: str
    framework_prefix: str = ""

    def resolve_doc_slug(
        self,
        file_path: Path,
        doc_slug: str | None = None,
        corpus_root: Path | None = None,
    ) -> str:
        """Resolves the canonical ltree document slug, enforcing the framework namespace prefix when derived from file_path."""
        if doc_slug is not None:
            return canonicalize_ltree_path(doc_slug)

        resolved_path = Path(file_path).resolve()
        if corpus_root is not None and resolved_path.is_relative_to(corpus_root.resolve()):
            rel = resolved_path.relative_to(corpus_root.resolve())
            stem_path = rel.with_suffix("").as_posix()
            slug = canonicalize_ltree_path(stem_path)
        else:
            slug = canonicalize_ltree_path(resolved_path.stem)

        prefix = self.framework_prefix.strip()
        if prefix:
            clean_prefix = canonicalize_ltree_path(prefix)
            if slug != clean_prefix and not slug.startswith(f"{clean_prefix}."):
                slug = f"{clean_prefix}.{slug}"
        return slug

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
        effective_text = raw_text
        if not effective_text and resolved_path.exists() and resolved_path.is_file():
            try:
                effective_text = resolved_path.read_text("utf-8", errors="replace")
            except OSError:
                effective_text = ""

        for parser in cls._parsers:
            if parser.can_handle(resolved_path, effective_text):
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
