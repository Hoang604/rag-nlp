from __future__ import annotations

import dataclasses
import logging
import mimetypes
import re
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Literal

from rag_eval.exceptions import (
    E_CORPUS_INTEGRITY_VIOLATION,
    CorpusDomainError,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PageBoundaryArtifact:
    line_text: str
    position: Literal["HEADER", "FOOTER", "BOUNDARY", "DELIMITER"]
    occurrences: int


class PageLayoutSanitizer:
    """Domain-agnostic detector and sanitizer of periodic boundary layout artifacts across document streams."""

    _CODE_BLOCK_PATTERN = re.compile(r"(?ms)^```[^\n]*\n.*?^```(?:\n|$)")
    _NUMERIC_COUNTER_PATTERN = re.compile(
        r"^\s*(?:[^\W\d_]+\s+)?\d+(?:\s*(?:/|-|of)\s*\d+)?\s*$", re.UNICODE
    )
    _DELIMITER_PATTERN = re.compile(r"^\s*[-_=*~]{1,3}\s*$")
    _MARKDOWN_BLOCK_START = re.compile(r"^\s*(?:#{1,6}\s+|\||```|[-*+]\s+|\d+\.\s+|>)")

    @classmethod
    def sanitize_document(
        cls, raw_text: str, min_repetition: int = 3, boundary_window: int = 3
    ) -> tuple[str, list[PageBoundaryArtifact]]:
        """Single canonical layout sanitizer for all incoming document streams.

        Operates with code-fence masking, discrete page boundary handling when \\x0c is present,
        periodic anchor & non-leaking cluster scanning across continuous text, and standalone delimiter cleanup.
        """
        # Step 1: Code-Fence Masking
        masked_code_blocks: list[str] = []

        def _mask_code(match: re.Match[str]) -> str:
            idx = len(masked_code_blocks)
            masked_code_blocks.append(match.group(0))
            return f"<!-- MASKED_CODE_BLOCK_{idx} -->\n"

        text_masked = cls._CODE_BLOCK_PATTERN.sub(_mask_code, raw_text)

        artifacts: list[PageBoundaryArtifact] = []

        # Step 2: Dual-Mode Boundary Sanitization
        if "\x0c" in text_masked:
            pages = [p for p in text_masked.split("\x0c") if p.strip()]
            if len(pages) >= min_repetition:
                sanitized_text, page_artifacts = cls._sanitize_discrete_pages(
                    pages, min_repetition=min_repetition, boundary_window=boundary_window
                )
                artifacts.extend(page_artifacts)
            else:
                sanitized_text = "\n\n".join(pages)
        else:
            sanitized_text, stream_artifacts = cls._sanitize_continuous_stream(
                text_masked, min_repetition=min_repetition, boundary_window=boundary_window
            )
            artifacts.extend(stream_artifacts)

        # Step 3: Standalone Delimiter Normalization outside code blocks
        lines = sanitized_text.splitlines()
        cleaned_lines: list[str] = []
        delimiter_count = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            prev_empty = (i == 0) or not lines[i - 1].strip()
            next_empty = (i == len(lines) - 1) or not lines[i + 1].strip()
            if cls._DELIMITER_PATTERN.fullmatch(stripped) and prev_empty and next_empty:
                delimiter_count += 1
                continue
            cleaned_lines.append(line)

        if delimiter_count > 0:
            artifacts.append(
                PageBoundaryArtifact(
                    line_text="-",
                    position="DELIMITER",
                    occurrences=delimiter_count,
                )
            )

        sanitized_text = "\n".join(cleaned_lines)

        # Collapse excessive newlines in the document stream before unmasking code fences
        sanitized_text = re.sub(r"\n{3,}", "\n\n", sanitized_text).strip()

        # Step 4: Code-Fence Unmasking (preserving code block contents 100% verbatim)
        for idx, original_code in enumerate(masked_code_blocks):
            placeholder = f"<!-- MASKED_CODE_BLOCK_{idx} -->\n"
            if placeholder in sanitized_text:
                sanitized_text = sanitized_text.replace(placeholder, original_code)
            else:
                # Fallback without trailing newline if stripped
                sanitized_text = sanitized_text.replace(f"<!-- MASKED_CODE_BLOCK_{idx} -->", original_code)

        return sanitized_text, artifacts

    @classmethod
    def _sanitize_discrete_pages(
        cls, pages: Sequence[str], min_repetition: int, boundary_window: int
    ) -> tuple[str, list[PageBoundaryArtifact]]:
        page_line_lists: list[list[str]] = [p.splitlines() for p in pages]
        header_counts: dict[str, int] = {}
        footer_counts: dict[str, int] = {}

        for lines in page_line_lists:
            ne_indices = [i for i, l in enumerate(lines) if l.strip()]
            if not ne_indices:
                continue
            n = len(ne_indices)
            hw = min(boundary_window, max(1, n // 2)) if n > 1 else 0

            page_headers = {lines[i].strip() for i in ne_indices[:hw]}
            for h in page_headers:
                header_counts[h] = header_counts.get(h, 0) + 1

            page_footers = {lines[i].strip() for i in ne_indices[-hw:]} if hw > 0 else set()
            for f in page_footers:
                footer_counts[f] = footer_counts.get(f, 0) + 1

        header_artifacts_set = {
            line for line, cnt in header_counts.items() if cnt >= min_repetition
        }
        footer_artifacts_set = {
            line for line, cnt in footer_counts.items() if cnt >= min_repetition
        }

        artifacts: list[PageBoundaryArtifact] = []
        for line in sorted(header_artifacts_set):
            artifacts.append(
                PageBoundaryArtifact(
                    line_text=line,
                    position="HEADER",
                    occurrences=header_counts[line],
                )
            )
        for line in sorted(footer_artifacts_set):
            if line not in header_artifacts_set:
                artifacts.append(
                    PageBoundaryArtifact(
                        line_text=line,
                        position="FOOTER",
                        occurrences=footer_counts[line],
                    )
                )

        sanitized_pages: list[str] = []
        for lines in page_line_lists:
            ne_indices = [i for i, l in enumerate(lines) if l.strip()]
            if not ne_indices:
                continue
            n = len(ne_indices)
            hw = min(boundary_window, max(1, n // 2)) if n > 1 else 0

            top_indices = set(ne_indices[:hw])
            bottom_indices = set(ne_indices[-hw:]) if hw > 0 else set()

            remove_indices: set[int] = set()
            for i in top_indices:
                if lines[i].strip() in header_artifacts_set:
                    remove_indices.add(i)
            for i in bottom_indices:
                if lines[i].strip() in footer_artifacts_set:
                    remove_indices.add(i)

            cleaned_lines = [l for i, l in enumerate(lines) if i not in remove_indices]
            cleaned_page = "\n".join(cleaned_lines).strip()
            if cleaned_page:
                sanitized_pages.append(cleaned_page)

        return "\n\n".join(sanitized_pages), artifacts

    @classmethod
    def _sanitize_continuous_stream(
        cls, text: str, min_repetition: int, boundary_window: int
    ) -> tuple[str, list[PageBoundaryArtifact]]:
        lines = text.splitlines()
        candidate_counts: dict[str, int] = {}

        # Pass 1: Identify periodic boundary anchors
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or len(stripped) >= 120:
                continue
            if cls._MARKDOWN_BLOCK_START.match(stripped) or stripped.endswith(":"):
                continue
            if cls._DELIMITER_PATTERN.fullmatch(stripped):
                continue

            prev_empty = (i == 0) or not lines[i - 1].strip()
            next_empty = (i == len(lines) - 1) or not lines[i + 1].strip()
            if prev_empty and next_empty:
                candidate_counts[stripped] = candidate_counts.get(stripped, 0) + 1

        confirmed_anchors = {
            txt for txt, cnt in candidate_counts.items() if cnt >= min_repetition
        }

        if not confirmed_anchors:
            return text, []

        remove_indices: set[int] = set()
        anchor_occurrences: dict[str, int] = {}
        boundary_occurrences: dict[str, int] = {}

        # Pass 2: Boundary Cluster Scanning around confirmed anchors
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped in confirmed_anchors:
                prev_empty = (i == 0) or not lines[i - 1].strip()
                next_empty = (i == len(lines) - 1) or not lines[i + 1].strip()
                if not (prev_empty and next_empty):
                    continue

                remove_indices.add(i)
                anchor_occurrences[stripped] = anchor_occurrences.get(stripped, 0) + 1

                # Scan backward up to boundary_window non-empty lines
                backward_non_empty = 0
                for target_idx in range(i - 1, -1, -1):
                    t_stripped = lines[target_idx].strip()
                    if not t_stripped:
                        continue
                    backward_non_empty += 1
                    if backward_non_empty > boundary_window:
                        break
                    # Non-leaking halt guardrail
                    if (
                        cls._MARKDOWN_BLOCK_START.match(t_stripped)
                        or t_stripped.endswith(":")
                        or len(t_stripped) >= 120
                    ):
                        break
                    if cls._NUMERIC_COUNTER_PATTERN.fullmatch(t_stripped) or cls._DELIMITER_PATTERN.fullmatch(t_stripped):
                        remove_indices.add(target_idx)
                        boundary_occurrences[t_stripped] = boundary_occurrences.get(t_stripped, 0) + 1
                    else:
                        break

                # Scan forward up to boundary_window non-empty lines
                forward_non_empty = 0
                for target_idx in range(i + 1, len(lines)):
                    t_stripped = lines[target_idx].strip()
                    if not t_stripped:
                        continue
                    forward_non_empty += 1
                    if forward_non_empty > boundary_window:
                        break
                    # Non-leaking halt guardrail
                    if (
                        cls._MARKDOWN_BLOCK_START.match(t_stripped)
                        or t_stripped.endswith(":")
                        or len(t_stripped) >= 120
                    ):
                        break
                    if cls._NUMERIC_COUNTER_PATTERN.fullmatch(t_stripped) or cls._DELIMITER_PATTERN.fullmatch(t_stripped):
                        remove_indices.add(target_idx)
                        boundary_occurrences[t_stripped] = boundary_occurrences.get(t_stripped, 0) + 1
                    else:
                        break

        artifacts: list[PageBoundaryArtifact] = []
        for anchor_text, cnt in sorted(anchor_occurrences.items()):
            artifacts.append(
                PageBoundaryArtifact(
                    line_text=anchor_text,
                    position="BOUNDARY",
                    occurrences=cnt,
                )
            )
        for bound_text, cnt in sorted(boundary_occurrences.items()):
            if bound_text not in anchor_occurrences:
                artifacts.append(
                    PageBoundaryArtifact(
                        line_text=bound_text,
                        position="DELIMITER" if cls._DELIMITER_PATTERN.fullmatch(bound_text) else "BOUNDARY",
                        occurrences=cnt,
                    )
                )

        cleaned = [l for i, l in enumerate(lines) if i not in remove_indices]
        return "\n".join(cleaned), artifacts


class SupportedFormat(str, Enum):
    MARKDOWN = "markdown"
    PDF = "pdf"
    DOCX = "docx"
    HTML = "html"
    PLAINTEXT = "plaintext"


@dataclass(frozen=True)
class RawTableBlock:
    """Khối bảng biểu được trích xuất nguyên vẹn không cắt vụn."""

    table_index: int
    start_line: int
    end_line: int
    markdown_content: str
    headers: list[str]
    row_count: int
    col_count: int
    summary: str


@dataclass(frozen=True)
class NormalizedDocument:
    """Kết quả chuẩn hóa tài liệu đa định dạng."""

    format_type: SupportedFormat
    raw_text: str
    total_lines: int
    tables: list[RawTableBlock] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)


def _detect_format_from_name_or_mime(
    file_name: str, mime_type: str | None = None
) -> SupportedFormat:
    ext = Path(file_name).suffix.lower()
    if ext in (".md", ".markdown", ".mdown"):
        return SupportedFormat.MARKDOWN
    if ext == ".pdf":
        return SupportedFormat.PDF
    if ext in (".docx", ".doc"):
        return SupportedFormat.DOCX
    if ext in (".html", ".htm", ".xhtml"):
        return SupportedFormat.HTML
    if ext in (".txt", ".text", ".log"):
        return SupportedFormat.PLAINTEXT

    if mime_type:
        mime_lower = mime_type.lower()
        if "pdf" in mime_lower:
            return SupportedFormat.PDF
        if "wordprocessingml" in mime_lower or "msword" in mime_lower:
            return SupportedFormat.DOCX
        if "markdown" in mime_lower:
            return SupportedFormat.MARKDOWN
        if "html" in mime_lower:
            return SupportedFormat.HTML

    return SupportedFormat.PLAINTEXT


def _extract_markdown_tables(text: str) -> list[RawTableBlock]:
    """Tìm và nhận diện các bảng biểu định dạng Markdown trong văn bản."""
    lines = text.splitlines()
    tables: list[RawTableBlock] = []
    in_table = False
    table_start = 0
    table_lines: list[str] = []
    table_idx = 0

    table_sep_regex = re.compile(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$")

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        is_table_line = "|" in stripped and not stripped.startswith("```")

        if is_table_line:
            if not in_table:
                in_table = True
                table_start = i
                table_lines = [line]
            else:
                table_lines.append(line)
        else:
            if in_table:
                if len(table_lines) >= 2 and any(table_sep_regex.match(l) for l in table_lines[1:3]):
                    table_idx += 1
                    raw_content = "\n".join(table_lines)
                    header_line = table_lines[0].strip()
                    headers = [h.strip() for h in header_line.strip("|").split("|") if h.strip()]
                    col_count = len(headers)
                    row_count = max(0, len(table_lines) - 2)
                    summary = f"Bảng {table_idx}: {row_count} hàng, {col_count} cột. Các cột: {', '.join(headers)}"
                    tables.append(
                        RawTableBlock(
                            table_index=table_idx,
                            start_line=table_start,
                            end_line=i - 1,
                            markdown_content=raw_content,
                            headers=headers,
                            row_count=row_count,
                            col_count=col_count,
                            summary=summary,
                        )
                    )
                in_table = False
                table_lines = []

    if in_table and len(table_lines) >= 2 and any(table_sep_regex.match(l) for l in table_lines[1:3]):
        table_idx += 1
        raw_content = "\n".join(table_lines)
        header_line = table_lines[0].strip()
        headers = [h.strip() for h in header_line.strip("|").split("|") if h.strip()]
        col_count = len(headers)
        row_count = max(0, len(table_lines) - 2)
        summary = f"Bảng {table_idx}: {row_count} hàng, {col_count} cột. Các cột: {', '.join(headers)}"
        tables.append(
            RawTableBlock(
                table_index=table_idx,
                start_line=table_start,
                end_line=len(lines),
                markdown_content=raw_content,
                headers=headers,
                row_count=row_count,
                col_count=col_count,
                summary=summary,
            )
        )

    return tables


class DocumentNormalizer:
    """Boundary seam chuẩn hóa mọi định dạng văn bản thành NormalizedDocument."""

    def __init__(self) -> None:
        self._mime_init = False

    def _ensure_mime(self) -> None:
        if not self._mime_init:
            mimetypes.init()
            self._mime_init = True

    def normalize_text(
        self,
        text: str,
        format_hint: SupportedFormat = SupportedFormat.MARKDOWN,
        extra_metadata: dict[str, object] | None = None,
    ) -> NormalizedDocument:
        """Chuẩn hóa chuỗi văn bản thô trực tiếp."""
        clean_text = text.replace("\r\n", "\n").replace("\r", "\n")
        if not clean_text.strip():
            raise CorpusDomainError(
                error_code=E_CORPUS_INTEGRITY_VIOLATION,
                message="Tài liệu văn bản thô không chứa nội dung hợp lệ hoặc chỉ toàn khoảng trắng.",
                data={"format_hint": format_hint.value},
            )

        sanitized_text, artifacts = PageLayoutSanitizer.sanitize_document(clean_text)

        metadata: dict[str, object] = {"source_type": format_hint.value}
        if extra_metadata:
            metadata.update(extra_metadata)
        if artifacts:
            metadata["sanitized_page_artifacts"] = [
                {"line_text": a.line_text, "position": a.position, "occurrences": a.occurrences}
                for a in artifacts
            ]

        lines = sanitized_text.splitlines()
        tables = _extract_markdown_tables(sanitized_text)
        return NormalizedDocument(
            format_type=format_hint,
            raw_text=sanitized_text,
            total_lines=len(lines),
            tables=tables,
            metadata=metadata,
        )

    def normalize_file(self, file_path: Path | str) -> NormalizedDocument:
        """Đọc và chuẩn hóa tệp tin từ đường dẫn trên đĩa."""
        path = Path(file_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Tệp tin không tồn tại: {path}")

        fmt = _detect_format_from_name_or_mime(path.name)
        if fmt == SupportedFormat.PDF:
            return self._normalize_pdf(path)
        if fmt == SupportedFormat.DOCX:
            return self._normalize_docx(path)
        if fmt == SupportedFormat.HTML:
            return self._normalize_html(path)

        content = path.read_text(encoding="utf-8", errors="replace")
        return self.normalize_text(content, format_hint=fmt)

    def normalize_bytes(
        self, content: bytes, file_name: str, mime_type: str | None = None
    ) -> NormalizedDocument:
        """Chuẩn hóa tệp tin nhị phân từ bộ đệm bytes trong RAM."""
        fmt = _detect_format_from_name_or_mime(file_name, mime_type)

        if fmt in (SupportedFormat.MARKDOWN, SupportedFormat.PLAINTEXT):
            decoded = content.decode("utf-8", errors="replace")
            doc = self.normalize_text(decoded, format_hint=fmt)
            meta = dict(doc.metadata)
            meta["original_filename"] = file_name
            return dataclasses.replace(doc, metadata=meta)

        format_to_ext = {
            SupportedFormat.PDF: ".pdf",
            SupportedFormat.DOCX: ".docx",
            SupportedFormat.HTML: ".html",
            SupportedFormat.MARKDOWN: ".md",
            SupportedFormat.PLAINTEXT: ".txt",
        }
        suffix = Path(file_name).suffix
        if not suffix:
            suffix = format_to_ext.get(fmt, ".bin")
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)

        try:
            doc = self.normalize_file(tmp_path)
            meta = dict(doc.metadata)
            meta["original_filename"] = file_name
            meta.pop("source_path", None)
            return dataclasses.replace(doc, metadata=meta)
        except CorpusDomainError as err:
            clean_msg = err.message.replace(tmp_path.name, file_name)
            data_dict = dict(err.data or {})
            data_dict["original_filename"] = file_name
            raise CorpusDomainError(
                error_code=err.error_code,
                message=clean_msg,
                data=data_dict,
            ) from err
        finally:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)

    def _normalize_pdf(self, path: Path) -> NormalizedDocument:
        import pdfplumber
        import pymupdf
        import pymupdf4llm

        clean_markdown = ""
        engine_used = "pymupdf4llm"

        try:
            chunks = pymupdf4llm.to_markdown(str(path), page_chunks=True)
            if chunks and isinstance(chunks, list):
                raw_pages = [
                    str(c.get("text", "")).replace("\r\n", "\n").replace("\r", "\n")
                    for c in chunks
                    if isinstance(c, dict) and str(c.get("text", "")).strip()
                ]
                if raw_pages:
                    clean_markdown = "\x0c".join(raw_pages)
            elif isinstance(chunks, str) and chunks.strip():
                clean_markdown = chunks.replace("\r\n", "\n").replace("\r", "\n")
        except (RuntimeError, ValueError, OSError, TypeError, pymupdf.FileDataError, Exception) as exc:  # noqa: BLE001
            logger.warning("pymupdf4llm thất bại trên %s (%s), fallback sang pdfplumber", path, exc)
            clean_markdown = ""

        # Fallback sang pdfplumber nếu pymupdf4llm không trả về text
        if not clean_markdown:
            engine_used = "pdfplumber"
            page_blocks: list[str] = []
            try:
                with pdfplumber.open(path) as pdf:
                    for page in pdf.pages:
                        txt = page.extract_text() or ""
                        if txt.strip():
                            page_blocks.append(txt.strip())
                if page_blocks:
                    clean_markdown = "\x0c".join(page_blocks)
            except (RuntimeError, ValueError, OSError, TypeError, pymupdf.FileDataError, Exception) as exc:  # noqa: BLE001
                logger.warning("pdfplumber trích xuất text thất bại trên %s: %s", path, exc)
                clean_markdown = ""

        clean_markdown = clean_markdown.strip()
        if not clean_markdown:
            raise CorpusDomainError(
                error_code=E_CORPUS_INTEGRITY_VIOLATION,
                message=f"Tệp tin PDF '{path.name}' không chứa nội dung văn bản có thể trích xuất hoặc là tài liệu ảnh scan chưa qua OCR.",
                data={"source_path": str(path)},
            )

        return self.normalize_text(
            clean_markdown,
            format_hint=SupportedFormat.PDF,
            extra_metadata={"source_path": str(path), "engine": engine_used},
        )

    def _normalize_docx(self, path: Path) -> NormalizedDocument:
        import zipfile

        from markitdown import MarkItDown

        if not zipfile.is_zipfile(path):
            raise CorpusDomainError(
                error_code=E_CORPUS_INTEGRITY_VIOLATION,
                message=f"Tệp tin DOCX '{path.name}' không phải là định dạng ZIP/DOCX hợp lệ hoặc đã bị hỏng.",
                data={"source_path": str(path)},
            )

        try:
            md = MarkItDown()
            result = md.convert(str(path))
            raw_md = result.text_content or ""
        except Exception as exc:
            raise CorpusDomainError(
                error_code=E_CORPUS_INTEGRITY_VIOLATION,
                message=f"Không thể xử lý tệp tin DOCX '{path.name}': {exc}",
                data={"source_path": str(path), "error": str(exc)},
            ) from exc

        clean_text = raw_md.replace("\r\n", "\n").replace("\r", "\n")
        if not clean_text.strip():
            raise CorpusDomainError(
                error_code=E_CORPUS_INTEGRITY_VIOLATION,
                message=f"Tệp tin DOCX '{path.name}' không chứa nội dung văn bản hợp lệ hoặc rỗng.",
                data={"source_path": str(path)},
            )

        return self.normalize_text(
            clean_text,
            format_hint=SupportedFormat.DOCX,
            extra_metadata={"source_path": str(path), "engine": "markitdown"},
        )

    def _normalize_html(self, path: Path) -> NormalizedDocument:
        from markitdown import MarkItDown

        try:
            md = MarkItDown()
            result = md.convert(str(path))
            raw_md = result.text_content or ""
        except Exception as exc:
            raise CorpusDomainError(
                error_code=E_CORPUS_INTEGRITY_VIOLATION,
                message=f"Không thể xử lý tệp tin HTML '{path.name}': {exc}",
                data={"source_path": str(path), "error": str(exc)},
            ) from exc

        clean_text = raw_md.replace("\r\n", "\n").replace("\r", "\n")
        if not clean_text.strip():
            raise CorpusDomainError(
                error_code=E_CORPUS_INTEGRITY_VIOLATION,
                message=f"Tệp tin HTML '{path.name}' không chứa nội dung văn bản hợp lệ hoặc rỗng.",
                data={"source_path": str(path)},
            )

        return self.normalize_text(
            clean_text,
            format_hint=SupportedFormat.HTML,
            extra_metadata={"source_path": str(path), "engine": "markitdown"},
        )
