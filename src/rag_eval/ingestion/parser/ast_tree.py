from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from rag_eval.ingestion.parser.normalizer import NormalizedDocument, RawTableBlock
from rag_eval.schemas import sanitize_ltree_label, validate_ltree_path

NodeType = Literal["DOCUMENT", "SECTION", "PARAGRAPH", "TABLE", "LIST", "CODE"]


@dataclass
class ParsedASTNode:
    """Nút trong cây phân cấp tài liệu AST."""

    path: str
    title: str
    node_type: NodeType
    depth: int
    verbatim_text: str
    start_line: int
    end_line: int
    parent_path: str | None
    children: list[ParsedASTNode] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)


def _disambiguate_label(candidate: str, used_labels: set[str]) -> str:
    """Đảm bảo nhãn phân cấp là duy nhất trong cùng danh mục để tránh đụng độ ltree."""
    clean = sanitize_ltree_label(candidate)
    if clean not in used_labels:
        used_labels.add(clean)
        return clean

    counter = 1
    while f"{clean}_{counter}" in used_labels:
        counter += 1
    unique_label = f"{clean}_{counter}"
    used_labels.add(unique_label)
    return unique_label


class MarkdownASTParser:
    """Phân tích cú pháp văn bản Markdown thành cây AST phân cấp không phụ thuộc domain."""

    _HEADING_REGEX = re.compile(r"^(#{1,6})\s+(.+)$")
    _FENCE_REGEX = re.compile(r"^```")

    def __init__(self, max_chunk_chars: int = 1500) -> None:
        self.max_chunk_chars = max_chunk_chars

    def parse(self, doc_slug: str, normalized: NormalizedDocument) -> ParsedASTNode:
        """Xây dựng toàn bộ cây AST từ văn bản đã chuẩn hóa."""
        sanitized_slug = sanitize_ltree_label(doc_slug)
        lines = normalized.raw_text.splitlines()

        root = ParsedASTNode(
            path=sanitized_slug,
            title=doc_slug,
            node_type="DOCUMENT",
            depth=0,
            verbatim_text="",
            start_line=1,
            end_line=max(1, len(lines)),
            parent_path=None,
            metadata={"doc_slug": doc_slug, **normalized.metadata},
        )

        if not lines:
            return root

        # Bảng tra cứu table bounds từ normalized.tables
        table_line_map: dict[int, RawTableBlock] = {}
        for tbl in normalized.tables:
            for l_num in range(tbl.start_line, tbl.end_line + 1):
                table_line_map[l_num] = tbl

        # Stack quản lý các node tổ tiên: [(level, ParsedASTNode, set_of_child_labels)]
        stack: list[tuple[int, ParsedASTNode, set[str]]] = [(0, root, set())]

        in_code_block = False
        current_content_lines: list[str] = []
        content_start_line = 1

        def _flush_content_block(end_line_num: int, force_type: NodeType | None = None) -> None:
            nonlocal current_content_lines, content_start_line
            if not current_content_lines:
                return

            text_block = "\n".join(current_content_lines).strip()
            if not text_block:
                current_content_lines = []
                return

            parent_level, parent_node, child_labels = stack[-1]

            # Kiểm tra xem khối này có chứa bảng biểu không
            matched_table = next(
                (
                    table_line_map[l_idx]
                    for l_idx in range(content_start_line, end_line_num + 1)
                    if l_idx in table_line_map
                ),
                None,
            )
            is_table_block = matched_table is not None

            if force_type:
                node_type: NodeType = force_type
            elif is_table_block:
                node_type = "TABLE"
            elif all(
                l.strip().startswith(("* ", "- ", "+ ")) or bool(re.match(r"^\d+\.\s", l.strip()))
                for l in current_content_lines
                if l.strip()
            ):
                node_type = "LIST"
            else:
                node_type = "PARAGRAPH"

            base_label = (
                "tbl"
                if node_type == "TABLE"
                else "code"
                if node_type == "CODE"
                else "list"
                if node_type == "LIST"
                else "p"
            )

            # Chia nhỏ khối paragraph nếu vượt quá max_chunk_chars
            if (
                node_type == "PARAGRAPH"
                and len(text_block) > self.max_chunk_chars
            ):
                sub_chunks: list[tuple[str, int, int]] = []
                if len(current_content_lines) > 1:
                    sub_lines: list[str] = []
                    sub_start = content_start_line
                    for offset, c_line in enumerate(current_content_lines):
                        sub_lines.append(c_line)
                        sub_len = sum(len(sl) for sl in sub_lines)
                        if sub_len >= self.max_chunk_chars or offset == len(current_content_lines) - 1:
                            sub_text = "\n".join(sub_lines).strip()
                            if sub_text:
                                sub_chunks.append((sub_text, sub_start, content_start_line + offset))
                            sub_lines = []
                            sub_start = content_start_line + offset + 1
                else:
                    # Single continuous long line paragraph
                    words = text_block.split(" ")
                    buf: list[str] = []
                    for word in words:
                        buf.append(word)
                        if sum(len(w) + 1 for w in buf) >= self.max_chunk_chars:
                            sub_chunks.append((" ".join(buf), content_start_line, end_line_num))
                            buf = []
                    if buf:
                        sub_chunks.append((" ".join(buf), content_start_line, end_line_num))

                for sub_text, sub_start, sub_end in sub_chunks:
                    sub_label = _disambiguate_label(base_label, child_labels)
                    sub_path = validate_ltree_path(f"{parent_node.path}.{sub_label}")
                    content_node = ParsedASTNode(
                        path=sub_path,
                        title=f"{parent_node.title} - {sub_label}",
                        node_type="PARAGRAPH",
                        depth=parent_level + 1,
                        verbatim_text=sub_text,
                        start_line=sub_start,
                        end_line=sub_end,
                        parent_path=parent_node.path,
                        metadata={},
                    )
                    parent_node.children.append(content_node)
                current_content_lines = []
                return

            unique_label = _disambiguate_label(base_label, child_labels)
            child_path = validate_ltree_path(f"{parent_node.path}.{unique_label}")

            node_meta: dict[str, object] = {}
            if node_type == "TABLE" and matched_table:
                node_meta["is_table"] = True
                node_meta["table_summary"] = matched_table.summary
                node_meta["headers"] = matched_table.headers
                node_meta["table_headers"] = matched_table.headers
                node_meta["row_count"] = matched_table.row_count
                node_meta["col_count"] = matched_table.col_count
            elif node_type == "TABLE":
                node_meta["is_table"] = True
                node_meta["table_summary"] = "Bảng dữ liệu trích xuất từ tài liệu."

            content_node = ParsedASTNode(
                path=child_path,
                title=f"{parent_node.title} - {unique_label}",
                node_type=node_type,
                depth=parent_level + 1,
                verbatim_text=text_block,
                start_line=content_start_line,
                end_line=end_line_num,
                parent_path=parent_node.path,
                metadata=node_meta,
            )
            parent_node.children.append(content_node)
            current_content_lines = []

        for line_idx, line in enumerate(lines, start=1):
            stripped = line.strip()

            if self._FENCE_REGEX.match(stripped):
                if in_code_block:
                    current_content_lines.append(line)
                    _flush_content_block(line_idx, force_type="CODE")
                    in_code_block = False
                    content_start_line = line_idx + 1
                    continue
                else:
                    _flush_content_block(line_idx - 1)
                    in_code_block = True
                    content_start_line = line_idx
                    current_content_lines.append(line)
                    continue

            if in_code_block:
                current_content_lines.append(line)
                continue

            heading_match = self._HEADING_REGEX.match(line)
            if heading_match:
                # Flush nội dung của mục trước đó
                _flush_content_block(line_idx - 1)

                h_level = len(heading_match.group(1))
                h_title = heading_match.group(2).strip()

                # Unwind stack về node có level nhỏ hơn h_level
                while len(stack) > 1 and stack[-1][0] >= h_level:
                    stack.pop()

                _, parent_node, child_labels = stack[-1]
                slug_label = _disambiguate_label(h_title, child_labels)
                new_path = validate_ltree_path(f"{parent_node.path}.{slug_label}")

                section_node = ParsedASTNode(
                    path=new_path,
                    title=h_title,
                    node_type="SECTION",
                    depth=h_level,
                    verbatim_text=line,
                    start_line=line_idx,
                    end_line=line_idx,
                    parent_path=parent_node.path,
                    metadata={"heading_level": h_level, "heading_raw": h_title},
                )
                parent_node.children.append(section_node)
                stack.append((h_level, section_node, set()))
                content_start_line = line_idx + 1
            else:
                tbl = table_line_map.get(line_idx)
                if tbl and line_idx == tbl.start_line:
                    _flush_content_block(line_idx - 1)
                    content_start_line = line_idx

                if not stripped and not tbl:
                    if current_content_lines:
                        _flush_content_block(line_idx - 1)
                        content_start_line = line_idx + 1
                    continue

                if not current_content_lines:
                    content_start_line = line_idx
                current_content_lines.append(line)

                if tbl and line_idx == tbl.end_line:
                    _flush_content_block(line_idx)
                    content_start_line = line_idx + 1

        # Flush khối nội dung cuối cùng
        _flush_content_block(len(lines))

        return root
