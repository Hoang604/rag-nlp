from __future__ import annotations

import dataclasses
import logging
import mimetypes
import re
import tempfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from rag_eval.exceptions import (
    E_CORPUS_INTEGRITY_VIOLATION,
    CorpusDomainError,
)

logger = logging.getLogger(__name__)


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
        self, text: str, format_hint: SupportedFormat = SupportedFormat.MARKDOWN
    ) -> NormalizedDocument:
        """Chuẩn hóa chuỗi văn bản thô trực tiếp."""
        clean_text = text.replace("\r\n", "\n").replace("\r", "\n")
        if not clean_text.strip():
            raise CorpusDomainError(
                error_code=E_CORPUS_INTEGRITY_VIOLATION,
                message="Tài liệu văn bản thô không chứa nội dung hợp lệ hoặc chỉ toàn khoảng trắng.",
                data={"format_hint": format_hint.value},
            )
        lines = clean_text.splitlines()
        tables = _extract_markdown_tables(clean_text)
        return NormalizedDocument(
            format_type=format_hint,
            raw_text=clean_text,
            total_lines=len(lines),
            tables=tables,
            metadata={"source_type": "raw_text"},
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

        clean_text = ""
        engine_used = "pymupdf4llm"

        try:
            markdown_content = pymupdf4llm.to_markdown(str(path))
            if markdown_content and markdown_content.strip():
                clean_text = markdown_content.replace("\r\n", "\n").replace("\r", "\n")
        except (RuntimeError, ValueError, OSError, TypeError, pymupdf.FileDataError, Exception) as exc:  # noqa: BLE001
            logger.warning("pymupdf4llm thất bại trên %s (%s), fallback sang pdfplumber", path, exc)
            clean_text = ""

        # Fallback sang pdfplumber nếu pymupdf4llm không trả về text
        if not clean_text:
            engine_used = "pdfplumber"
            page_blocks: list[str] = []
            try:
                with pdfplumber.open(path) as pdf:
                    for page in pdf.pages:
                        txt = page.extract_text() or ""
                        if txt.strip():
                            page_blocks.append(txt.strip())
                clean_text = "\n\n".join(page_blocks).replace("\r\n", "\n").replace("\r", "\n")
            except (RuntimeError, ValueError, OSError, TypeError, pymupdf.FileDataError, Exception) as exc:  # noqa: BLE001
                logger.warning("pdfplumber trích xuất text thất bại trên %s: %s", path, exc)
                clean_text = ""

        clean_text = clean_text.strip()
        if not clean_text:
            raise CorpusDomainError(
                error_code=E_CORPUS_INTEGRITY_VIOLATION,
                message=f"Tệp tin PDF '{path.name}' không chứa nội dung văn bản có thể trích xuất hoặc là tài liệu ảnh scan chưa qua OCR.",
                data={"source_path": str(path)},
            )

        lines = clean_text.splitlines()
        # Trích xuất bảng biểu trực tiếp từ clean_text để đảm bảo tọa độ dòng đồng bộ 100%
        tables = _extract_markdown_tables(clean_text)

        return NormalizedDocument(
            format_type=SupportedFormat.PDF,
            raw_text=clean_text,
            total_lines=len(lines),
            tables=tables,
            metadata={"source_path": str(path), "engine": engine_used},
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
        lines = clean_text.splitlines()
        tables = _extract_markdown_tables(clean_text)

        return NormalizedDocument(
            format_type=SupportedFormat.DOCX,
            raw_text=clean_text,
            total_lines=len(lines),
            tables=tables,
            metadata={"source_path": str(path), "engine": "markitdown"},
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
        lines = clean_text.splitlines()
        tables = _extract_markdown_tables(clean_text)

        return NormalizedDocument(
            format_type=SupportedFormat.HTML,
            raw_text=clean_text,
            total_lines=len(lines),
            tables=tables,
            metadata={"source_path": str(path), "engine": "markitdown"},
        )
