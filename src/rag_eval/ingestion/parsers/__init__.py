from __future__ import annotations

from rag_eval.ingestion.parsers.baohiem_md import BaoHiemMarkdownParser
from rag_eval.ingestion.parsers.nextjs_mdx import NextJSMDXParser
from rag_eval.ingestion.parsers.nodejs_md import NodeJSMarkdownParser
from rag_eval.ingestion.registry import CodingParserRegistry

# Automatically register framework parsers upon importing parsers package
CodingParserRegistry.register(NodeJSMarkdownParser())
CodingParserRegistry.register(NextJSMDXParser())
CodingParserRegistry.register(BaoHiemMarkdownParser())

__all__ = ["BaoHiemMarkdownParser", "NextJSMDXParser", "NodeJSMarkdownParser"]
