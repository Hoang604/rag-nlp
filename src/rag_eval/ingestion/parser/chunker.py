from __future__ import annotations

import logging

from rag_eval.ingestion.parser.ast_tree import MarkdownASTParser, ParsedASTNode
from rag_eval.ingestion.parser.normalizer import NormalizedDocument

logger = logging.getLogger(__name__)


class HierarchicalASTSegmenter:
    """Điều phối phân tách cây AST và làm phẳng thành danh sách các leaf chunks phục vụ Staging."""

    def __init__(self, max_chunk_chars: int = 1500) -> None:
        self.max_chunk_chars = max_chunk_chars
        self.parser = MarkdownASTParser(max_chunk_chars=max_chunk_chars)

    def parse_to_tree(
        self, doc_slug: str, normalized: NormalizedDocument
    ) -> ParsedASTNode:
        """Chuyển đổi NormalizedDocument thành cây ParsedASTNode."""
        return self.parser.parse(doc_slug=doc_slug, normalized=normalized)

    def flatten_leaf_chunks(self, root_node: ParsedASTNode) -> list[ParsedASTNode]:
        """Thu thập danh sách phẳng các leaf chunks có nội dung văn bản thực tế."""
        leaves: list[ParsedASTNode] = []

        def _collect(node: ParsedASTNode) -> None:
            # Nếu node là SECTION và có verbatim_text (tiêu đề phân cấp)
            if node.node_type == "SECTION" and node.verbatim_text.strip():
                leaves.append(node)

            # Nếu node là leaf (không có children)
            if not node.children:
                if node.node_type != "SECTION" and node.verbatim_text.strip():
                    leaves.append(node)
                return

            for child in node.children:
                _collect(child)

        _collect(root_node)

        # Nếu cây chỉ có root mà không có con (ví dụ tài liệu 1 dòng)
        if not leaves and root_node.verbatim_text.strip():
            leaves.append(root_node)

        # Đảm bảo các leaf chunks được sắp xếp theo đúng thứ tự xuất hiện trong tài liệu
        leaves.sort(key=lambda n: (n.start_line, n.path))
        return leaves
