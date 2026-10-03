from __future__ import annotations

import logging
from pathlib import Path

from rag_eval.ingestion.parser.chunker import HierarchicalASTSegmenter
from rag_eval.ingestion.parser.edges import LineageBreadcrumbAndEdgeExtractor
from rag_eval.ingestion.parser.normalizer import (
    DocumentNormalizer,
    NormalizedDocument,
    SupportedFormat,
)
from rag_eval.ingestion.staging.models import StagingChunk, StagingEdge

logger = logging.getLogger(__name__)


class DocumentIngestionEngine:
    """Điều phối toàn diện quy trình chuyển hóa tài liệu thô thành Staging chunks và edges."""

    def __init__(self) -> None:
        self.normalizer = DocumentNormalizer()
        self.segmenter = HierarchicalASTSegmenter()
        self.extractor = LineageBreadcrumbAndEdgeExtractor()

    def _process_normalized(
        self, doc_slug: str, normalized: NormalizedDocument, metadata: dict[str, object] | None = None
    ) -> tuple[list[StagingChunk], list[StagingEdge], dict[str, object]]:
        # 1. Bóc tách cây AST phân cấp
        root_node = self.segmenter.parse_to_tree(doc_slug=doc_slug, normalized=normalized)

        # 2. Làm phẳng thành leaf chunks
        leaf_nodes = self.segmenter.flatten_leaf_chunks(root_node)

        # 3. Kế thừa văn cảnh phả hệ tổ tiên
        stg_chunks = self.extractor.synthesize_breadcrumbs(root_node=root_node, leaf_nodes=leaf_nodes)

        # 4. Trích xuất quan hệ đồ thị 100% chính xác
        stg_edges = self.extractor.extract_deterministic_edges(chunks=stg_chunks, normalized=normalized)

        doc_meta = dict(metadata or {})
        doc_meta["total_lines"] = normalized.total_lines
        doc_meta["tables_count"] = len(normalized.tables)
        doc_meta["format_type"] = normalized.format_type.value

        return stg_chunks, stg_edges, doc_meta

    def process_raw(
        self,
        doc_slug: str,
        title: str,
        raw_text: str,
        metadata: dict[str, object] | None = None,
    ) -> tuple[list[StagingChunk], list[StagingEdge], dict[str, object]]:
        """Xử lý văn bản thô trực tiếp thành danh sách StagingChunk và StagingEdge."""
        normalized = self.normalizer.normalize_text(raw_text, format_hint=SupportedFormat.MARKDOWN)
        return self._process_normalized(doc_slug=doc_slug, normalized=normalized, metadata=metadata)

    def process_file(
        self,
        doc_slug: str,
        title: str,
        file_path: Path | str,
        metadata: dict[str, object] | None = None,
    ) -> tuple[str, list[StagingChunk], list[StagingEdge], dict[str, object]]:
        """Xử lý tệp tin từ đĩa thành văn bản thô, danh sách StagingChunk và StagingEdge."""
        path = Path(file_path).resolve()
        normalized = self.normalizer.normalize_file(path)
        chunks, edges, doc_meta = self._process_normalized(
            doc_slug=doc_slug, normalized=normalized, metadata=metadata
        )
        return normalized.raw_text, chunks, edges, doc_meta

    def process_bytes(
        self,
        doc_slug: str,
        title: str,
        content: bytes,
        file_name: str,
        mime_type: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> tuple[str, list[StagingChunk], list[StagingEdge], dict[str, object]]:
        """Xử lý tệp tin nhị phân trong RAM thành văn bản thô, danh sách StagingChunk và StagingEdge."""
        normalized = self.normalizer.normalize_bytes(
            content=content, file_name=file_name, mime_type=mime_type
        )
        chunks, edges, doc_meta = self._process_normalized(
            doc_slug=doc_slug, normalized=normalized, metadata=metadata
        )
        return normalized.raw_text, chunks, edges, doc_meta
