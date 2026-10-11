from __future__ import annotations

from rag_eval.ingestion.parsers.nextjs_mdx import NextJSMDXParser
from rag_eval.ingestion.registry import CodingParserRegistry

# Automatically register NextJSMDXParser upon importing parsers package
CodingParserRegistry.register(NextJSMDXParser())

__all__ = ["NextJSMDXParser"]
