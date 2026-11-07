from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from rag_eval.ingestion.parsers.baohiem_md import BaoHiemMarkdownParser
from rag_eval.ingestion.parsers.nextjs_mdx import NextJSMDXParser
from rag_eval.ingestion.parsers.nodejs_md import NodeJSMarkdownParser
from rag_eval.ingestion.registry import CodingParserRegistry, UnsupportedFrameworkError
from rag_eval.schemas import split_context_and_text


def test_baohiem_parser_extracts_frontmatter_and_preserves_exact_line_numbers() -> None:
    """Verifies YAML frontmatter extraction, canonical statutory ltree paths (chuong_i, muc_1, dieu_1),
    pure container pruning, and exact 1:1 [start_line, end_line] mapping against raw_text.
    """
    content = """---
title: "Luật Kinh doanh bảo hiểm mẫu"
doc_code: "08/2022/QH15"
issued_date: "2022-06-16"
source: "https://vbpl.vn/sample"
---

# Luật Kinh doanh bảo hiểm mẫu

## Chương I: NHỮNG QUY ĐỊNH CHUNG

#### Điều 1. Phạm vi điều chỉnh

Luật này quy định về tổ chức và hoạt động kinh doanh bảo hiểm; quyền và nghĩa vụ của tổ chức, cá nhân tham gia bảo hiểm.

#### Điều 2. Đối tượng áp dụng

1. Doanh nghiệp bảo hiểm, doanh nghiệp tái bảo hiểm.

2. Đại lý bảo hiểm, doanh nghiệp môi giới bảo hiểm.

## Chương II: HỢP ĐỒNG BẢO HIỂM

### Mục 1: QUY ĐỊNH CHUNG VỀ HỢP ĐỒNG BẢO HIỂM

#### Điều 3. Hợp đồng bảo hiểm

a) Hợp đồng bảo hiểm nhân thọ;

b) Hợp đồng bảo hiểm sức khỏe.
"""
    raw_lines = content.splitlines()
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(content)
        path = Path(f.name)

    try:
        parser = BaoHiemMarkdownParser()
        assert parser.can_handle(path, content) is True

        draft = parser.parse(path, doc_slug="baohiem.luat_mau")
        assert draft.doc_slug == "baohiem.luat_mau"
        assert draft.title == "Luật Kinh doanh bảo hiểm mẫu"
        assert draft.metadata["doc_code"] == "08/2022/QH15"
        assert draft.metadata["issued_date"] == "2022-06-16"
        assert draft.metadata["format_type"] == "baohiem_md"
        assert draft.metadata["framework"] == "baohiem"

        assert len(draft.chunks) == 3
        c1, c2, c3 = draft.chunks

        assert c1.path == "baohiem.luat_mau.chuong_i.dieu_1"
        assert c1.start_line == 12
        assert c1.end_line == 14
        assert "\n".join(raw_lines[c1.start_line - 1 : c1.end_line]) == c1.verbatim_text
        assert c1.metadata["ancestor_titles"] == [
            "Luật Kinh doanh bảo hiểm mẫu",
            "Chương I: NHỮNG QUY ĐỊNH CHUNG",
            "Điều 1. Phạm vi điều chỉnh",
        ]
        assert c1.metadata["doc_code"] == "08/2022/QH15"
        ctx1, txt1 = split_context_and_text(c1.contextualized_text, c1.verbatim_text)
        assert ctx1 == "Luật Kinh doanh bảo hiểm mẫu > Chương I: NHỮNG QUY ĐỊNH CHUNG > Điều 1. Phạm vi điều chỉnh"
        assert txt1 == c1.verbatim_text

        assert c2.path == "baohiem.luat_mau.chuong_i.dieu_2"
        assert c2.start_line == 16
        assert c2.end_line == 20
        assert "\n".join(raw_lines[c2.start_line - 1 : c2.end_line]) == c2.verbatim_text

        assert c3.path == "baohiem.luat_mau.chuong_ii.muc_1.dieu_3"
        assert c3.start_line == 26
        assert c3.end_line == 30
        assert "\n".join(raw_lines[c3.start_line - 1 : c3.end_line]) == c3.verbatim_text
        assert c3.metadata["ancestor_titles"] == [
            "Luật Kinh doanh bảo hiểm mẫu",
            "Chương II: HỢP ĐỒNG BẢO HIỂM",
            "Mục 1: QUY ĐỊNH CHUNG VỀ HỢP ĐỒNG BẢO HIỂM",
            "Điều 3. Hợp đồng bảo hiểm",
        ]
    finally:
        path.unlink(missing_ok=True)


def test_baohiem_parser_normalizes_bare_tieu_muc_containers_without_line_drift() -> None:
    """Verifies that bare 'Tiểu mục <N>' + ALL-CAPS title lines (as in Nghị định 46/2023/NĐ-CP)
    become level-3 structural containers without bleeding into preceding Điều chunks or drifting line numbers.
    """
    content = """---
title: "Nghị định mẫu"
doc_code: "46/2023/NĐ-CP"
---

# Nghị định mẫu

## Chương VII: NGHIỆP VỤ BẢO HIỂM LIÊN KẾT ĐẦU TƯ

### Mục 2: NGHIỆP VỤ BẢO HIỂM LIÊN KẾT ĐẦU TƯ

Tiểu mục 1

ĐẶC ĐIỂM NGHIỆP VỤ, QUYỀN LỢI BẢO HIỂM

#### Điều 101. Đặc điểm của nghiệp vụ

1. Nghiệp vụ bảo hiểm liên kết đầu tư bao gồm bảo hiểm liên kết chung và đơn vị.

Tiểu mục 2

BẢO HIỂM LIÊN KẾT CHUNG

#### Điều 103. Tên gọi và thiết kế sản phẩm

1. Tên của sản phẩm bảo hiểm liên kết chung phải phù hợp.
"""
    raw_lines = content.splitlines()
    parser = BaoHiemMarkdownParser()
    draft = parser.parse_text(content, doc_slug="baohiem.nd_mau")

    assert len(draft.chunks) == 2
    c101, c103 = draft.chunks

    assert c101.path == "baohiem.nd_mau.chuong_vii.muc_2.tieu_muc_1.dieu_101"
    assert c101.start_line == 16
    assert c101.end_line == 18
    assert "Tiểu mục 2" not in c101.verbatim_text
    assert "\n".join(raw_lines[c101.start_line - 1 : c101.end_line]) == c101.verbatim_text
    assert c101.metadata["ancestor_titles"] == [
        "Nghị định mẫu",
        "Chương VII: NGHIỆP VỤ BẢO HIỂM LIÊN KẾT ĐẦU TƯ",
        "Mục 2: NGHIỆP VỤ BẢO HIỂM LIÊN KẾT ĐẦU TƯ",
        "Tiểu mục 1: ĐẶC ĐIỂM NGHIỆP VỤ, QUYỀN LỢI BẢO HIỂM",
        "Điều 101. Đặc điểm của nghiệp vụ",
    ]

    assert c103.path == "baohiem.nd_mau.chuong_vii.muc_2.tieu_muc_2.dieu_103"
    assert c103.start_line == 24
    assert c103.end_line == 26
    assert "\n".join(raw_lines[c103.start_line - 1 : c103.end_line]) == c103.verbatim_text


def test_registry_dispatches_baohiem_alongside_nodejs_and_nextjs(tmp_path: Path) -> None:
    """Verifies that CodingParserRegistry dispatches baohiem, nodejs, and nextjs accurately without generic fallback."""
    CodingParserRegistry.clear()
    CodingParserRegistry.register(NodeJSMarkdownParser())
    CodingParserRegistry.register(NextJSMDXParser())
    CodingParserRegistry.register(BaoHiemMarkdownParser())

    bh_dir = tmp_path / "baohiem"
    bh_dir.mkdir()
    bh_file = bh_dir / "luat.md"
    bh_file.write_text(
        "---\ntitle: \"Luật\"\ndoc_code: \"08/2022/QH15\"\n---\n\n# Luật\n\n## Chương I\n\n#### Điều 1. Phạm vi\n\nNội dung.\n",
        encoding="utf-8",
    )

    unknown_dir = tmp_path / "unknown"
    unknown_dir.mkdir()
    unknown_file = unknown_dir / "notes.md"
    unknown_file.write_text("# Notes\n\nGeneric markdown notes.\n", encoding="utf-8")

    parser = CodingParserRegistry.get_parser(bh_file)
    assert parser.name == "baohiem_md"
    draft = parser.parse(bh_file, corpus_root=bh_dir)
    assert draft.doc_slug == "baohiem.luat"
    assert len(draft.chunks) == 1
    assert draft.chunks[0].path == "baohiem.luat.chuong_i.dieu_1"

    with pytest.raises(UnsupportedFrameworkError):
        CodingParserRegistry.get_parser(unknown_file)
