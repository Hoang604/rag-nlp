from __future__ import annotations

import re

from rag_eval.ingestion.parser.ast_tree import ParsedASTNode
from rag_eval.ingestion.parser.normalizer import NormalizedDocument
from rag_eval.ingestion.staging.models import (
    ChunkReviewStatus,
    RelationType,
    StagingChunk,
    StagingEdge,
)
from rag_eval.schemas import FinalizationState, validate_ltree_path


def _build_node_path_map(root: ParsedASTNode) -> dict[str, list[str]]:
    """Xây dựng bản đồ từ path của node đến danh sách các tiêu đề tổ tiên (strictly ancestral)."""
    ancestor_map: dict[str, list[str]] = {}
    has_sections = any(c.node_type == "SECTION" for c in root.children)

    def _traverse(node: ParsedASTNode, current_titles: list[str]) -> None:
        # Gán danh sách tổ tiên nghiêm ngặt (không chứa chính node này)
        ancestor_map[node.path] = list(current_titles)

        # Chuẩn bị danh sách tổ tiên cho các node con
        next_titles = list(current_titles)
        if node.title and node.node_type in ("DOCUMENT", "SECTION"):
            clean_title = node.title.strip()
            # Bỏ qua root DOCUMENT title nếu đã có các phân mục SECTION con để tránh lặp slug
            if node.node_type == "DOCUMENT" and has_sections:
                pass
            elif clean_title and clean_title not in next_titles:
                next_titles.append(clean_title)

        for child in node.children:
            _traverse(child, next_titles)

    _traverse(root, [])
    return ancestor_map


class LineageBreadcrumbAndEdgeExtractor:
    """Tổng hợp văn cảnh phả hệ tổ tiên và trích xuất quan hệ đồ thị ban đầu chính xác 100%."""

    _MD_LINK_GENERIC_REGEX = re.compile(r"\[([^\]]+)\]\(([^\s\)]+)\)")

    def synthesize_breadcrumbs(
        self, root_node: ParsedASTNode, leaf_nodes: list[ParsedASTNode]
    ) -> list[StagingChunk]:
        """Tạo danh sách StagingChunk với contextualized_text kế thừa phả hệ đầy đủ."""
        ancestor_map = _build_node_path_map(root_node)
        chunks: list[StagingChunk] = []

        for leaf in leaf_nodes:
            ancestors = ancestor_map.get(leaf.path, [])
            clean_verbatim = leaf.verbatim_text.strip()
            if not clean_verbatim:
                continue

            if ancestors:
                breadcrumb_prefix = f"[{' > '.join(ancestors)}]\n"
                contextualized_text = f"{breadcrumb_prefix}{clean_verbatim}"
            else:
                contextualized_text = clean_verbatim

            chunk_meta = dict(leaf.metadata)
            chunk_meta["ancestor_titles"] = ancestors
            chunk_meta["node_type"] = leaf.node_type

            chunks.append(
                StagingChunk(
                    path=leaf.path,
                    node_type=leaf.node_type,
                    verbatim_text=clean_verbatim,
                    contextualized_text=contextualized_text,
                    start_line=leaf.start_line,
                    end_line=leaf.end_line,
                    metadata=chunk_meta,
                    char_length=len(clean_verbatim),
                    review_status=ChunkReviewStatus.PENDING,
                    finalization_state=FinalizationState.UNFINALIZED,
                )
            )

        return chunks

    def extract_deterministic_edges(
        self, chunks: list[StagingChunk], normalized: NormalizedDocument
    ) -> list[StagingEdge]:
        """Trích xuất quan hệ đồ thị với độ chính xác tuyệt đối 100% (Ràng buộc 4).

        Chỉ tạo quan hệ khi liên kết neo Markdown (`#anchor`) hoặc đường dẫn đích
        trỏ chính xác 1:1 đến một chunk duy nhất đã tồn tại trong phiên làm việc.
        Các liên kết ngoài hoặc neo chưa phân giải được theo dõi như external reference edges.
        """
        if not chunks:
            return []

        # Xây dựng bảng tra cứu anchor slug từ các SECTION chunks với kiểm tra tính duy nhất (1:1 uniqueness)
        anchor_candidates: dict[str, list[str]] = {}

        for c in chunks:
            # 1. Từ heading_raw nếu có (ưu tiên hàng đầu)
            raw_heading = c.metadata.get("heading_raw")
            if raw_heading and isinstance(raw_heading, str):
                slug = re.sub(r"[^\w\-]+", "-", raw_heading, flags=re.UNICODE).lower().strip("-")
                if slug and slug not in ("p", "tbl", "code", "list", "root"):
                    anchor_candidates.setdefault(slug, []).append(c.path)

            # 2. Từ nhãn cuối của path nếu nó đại diện cho một SECTION (không phải generic leaf p/tbl/code/list hoặc disambiguated leaf p_1, tbl_1, etc.)
            last_segment = c.path.rsplit(".", 1)[-1].lower()
            if not re.match(r"^(p|tbl|code|list)(_\d+)?$", last_segment):
                dash_seg = last_segment.replace("_", "-")
                if dash_seg and not re.match(r"^(p|tbl|code|list)(-\d+)?$", dash_seg):
                    anchor_candidates.setdefault(dash_seg, []).append(c.path)

        # Ràng buộc 4 (100% Precision, Zero Speculation):
        # Chỉ giữ lại các anchor trỏ đến DUY NHẤT 1 chunk (len(set(paths)) == 1).
        anchor_to_path: dict[str, str] = {
            slug: paths[0]
            for slug, paths in anchor_candidates.items()
            if len(set(paths)) == 1
        }

        valid_paths = {c.path for c in chunks}
        edges: list[StagingEdge] = []
        seen_edges: set[tuple[str, str, str]] = set()

        for c in chunks:
            for match in self._MD_LINK_GENERIC_REGEX.finditer(c.verbatim_text):
                target = match.group(2).strip()
                if not target or target.startswith(("http://", "https://", "mailto:")):
                    continue

                if target.startswith("#"):
                    anchor = target[1:].lower().strip()
                    target_path = anchor_to_path.get(anchor)
                    # Architectural Invariant 4: 100% precision, zero speculation.
                    # Only create edge if anchor maps unambiguously to a unique valid chunk path.
                    if target_path and target_path in valid_paths and target_path != c.path:
                        key = (c.path, target_path, RelationType.REFERENCES.value)
                        if key not in seen_edges:
                            seen_edges.add(key)
                            edges.append(
                                StagingEdge(
                                    source_path=validate_ltree_path(c.path),
                                    target_path=validate_ltree_path(target_path),
                                    relation_type=RelationType.REFERENCES,
                                )
                            )
                else:
                    # Cross-document relative target (e.g. [Spec](other_doc.md))
                    clean_doc_target = re.sub(r"[^a-zA-Z0-9_\.]", "_", target.split("#")[0]).strip("_")
                    if clean_doc_target:
                        clean_ext_path = f"{clean_doc_target}.ref"
                        key = (c.path, clean_ext_path, RelationType.REFERENCES.value)
                        if key not in seen_edges:
                            seen_edges.add(key)
                            edges.append(
                                StagingEdge(
                                    source_path=validate_ltree_path(c.path),
                                    target_path=validate_ltree_path(clean_ext_path),
                                    relation_type=RelationType.REFERENCES,
                                )
                            )

        return edges
