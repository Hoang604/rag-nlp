from __future__ import annotations

from typing import Annotated

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from rag_eval.mcp.tools import (
    HIERARCHICAL_DIRECTION_DESCRIPTION,
    CorpusMCPTools,
    GraphDirection,
    GraphTraverseResult,
    HierarchicalDirection,
    HierarchicalNavigateResult,
    RelationType,
)
from rag_eval.schemas import RawDocumentSliceResult, VennSearchResult


def register_mcp_tools(server: MCPServer, tool_impl: CorpusMCPTools) -> None:
    """Registers the 5 canonical Agent-First corpus tools onto the MCPServer instance."""

    @server.tool(
        name="hybrid_search",
        description=(
            "Truy xuất nội dung đa chiều kết hợp: Đồng thời tìm kiếm ngữ nghĩa theo `query` "
            "và đối sánh ký tự chính xác theo từ khóa neo `pattern`. "
            "Trả về 3 nhóm kết quả Venn (both_hits, semantic_only_hits, verbatim_only_hits) "
            "đã khử trùng 100%."
        ),
    )
    async def hybrid_search(
        query: Annotated[
            str,
            Field(
                min_length=1,
                description="Ngữ cảnh / ý niệm cần tìm kiếm (dense vector + sparse FTS).",
            ),
        ],
        pattern: Annotated[
            str,
            Field(
                min_length=1,
                description="Từ khóa neo cứng, mã số hiệu, thuật ngữ cần khớp chính xác (verbatim grep).",
            ),
        ],
        is_regex: Annotated[
            bool,
            Field(
                default=False,
                description="Bật chế độ đánh giá biểu thức chính quy POSIX cho pattern.",
            ),
        ] = False,
        case_sensitive: Annotated[
            bool,
            Field(
                default=False,
                description="Phân biệt chữ hoa / chữ thường khi so khớp ký tự.",
            ),
        ] = False,
        order_by_reading_order: Annotated[
            bool,
            Field(
                default=False,
                description="Sắp xếp kết quả verbatim theo thứ tự đọc trong tài liệu (start_line, path) thay vì điểm tương đồng.",
            ),
        ] = False,
        limit: Annotated[
            int,
            Field(
                default=10,
                ge=1,
                le=50,
                description="Số lượng kết quả tối đa cho mỗi nhánh tìm kiếm.",
            ),
        ] = 10,
        doc_slugs: Annotated[
            list[str] | None,
            Field(
                default=None,
                description="Giới hạn phạm vi tìm kiếm theo danh sách doc_slug. Để None để tìm trên toàn bộ kho.",
            ),
        ] = None,
        path_prefix: Annotated[
            str | None,
            Field(
                default=None,
                description="Giới hạn phân cấp cây LTree (None để tìm toàn cây).",
            ),
        ] = None,
        rerank: Annotated[
            bool | None,
            Field(
                default=None,
                description="Bật hoặc tắt bước xếp hạng lại kết quả tìm kiếm (để None dùng cấu hình hệ thống).",
            ),
        ] = None,
    ) -> VennSearchResult:
        return await tool_impl.hybrid_search(
            query=query,
            pattern=pattern,
            limit=limit,
            rerank=rerank,
            doc_slugs=doc_slugs or None,
            path_prefix=path_prefix or None,
            is_regex=is_regex,
            case_sensitive=case_sensitive,
            order_by_reading_order=order_by_reading_order,
        )

    @server.tool(
        name="hierarchical_navigate",
        description=(
            "Duyệt cấu trúc cây phân cấp tài liệu xoay quanh một nút/chunk được chỉ định. "
            "Duyệt các hướng: CHILDREN, PARENT_CHAIN, SIBLINGS, SUBTREE."
        ),
    )
    async def hierarchical_navigate(
        path: Annotated[
            str,
            Field(
                description="Đường dẫn phân cấp của nút mục tiêu.",
            ),
        ],
        direction: Annotated[
            HierarchicalDirection,
            Field(
                default=HierarchicalDirection.CHILDREN,
                description=HIERARCHICAL_DIRECTION_DESCRIPTION,
            ),
        ] = HierarchicalDirection.CHILDREN,
    ) -> HierarchicalNavigateResult:
        return await tool_impl.hierarchical_navigate(
            path=path,
            direction=direction,
        )

    @server.tool(
        name="graph_traverse",
        description="Duyệt đồ thị tri thức đệ quy qua các liên kết quan hệ giữa các chunk/nút.",
    )
    async def graph_traverse(
        source_path: Annotated[
            str,
            Field(
                description="Đường dẫn phân cấp của nút gốc bắt đầu duyệt.",
            ),
        ],
        direction: Annotated[
            GraphDirection,
            Field(
                default="OUTGOING",
                description="Hướng duyệt đồ thị: 'OUTGOING', 'INCOMING', 'BOTH'.",
            ),
        ] = "OUTGOING",
        max_depth: Annotated[
            int,
            Field(
                default=2,
                ge=1,
                le=4,
                description="Độ sâu bước nhảy tối đa trên đồ thị quan hệ.",
            ),
        ] = 2,
        filter_relations: Annotated[
            list[str] | None,
            Field(
                default=None,
                description="Danh sách các mã quan hệ cần lọc (REFERENCES, SUPPORTS, DEPENDS_ON, v.v.). Để None để duyệt tất cả.",
            ),
        ] = None,
        limit: Annotated[
            int,
            Field(
                default=20,
                ge=1,
                le=100,
                description="Số bước nhảy tối đa trả về.",
            ),
        ] = 20,
    ) -> GraphTraverseResult:
        return await tool_impl.graph_traverse(
            source_path=source_path,
            direction=direction,
            max_depth=max_depth,
            filter_relations=filter_relations,
            limit=limit,
        )

    @server.tool(
        name="link_chunks",
        description=(
            "Thiết lập cạnh quan hệ đồ thị tri thức ngữ nghĩa giữa 2 chunk dựa trên đường dẫn LTree phân cấp. "
            "Bắt buộc cung cấp citation_text được trích dẫn chính xác từ chunk nguồn. "
            "Mã quan hệ phải thuộc danh mục hợp lệ (REFERENCES, SUPPORTS, CONTRADICTS, DEFINES, EXTENDS, EXEMPLIFIES, DEPENDS_ON, SUPERSEDES, SEE_ALSO)."
        ),
    )
    async def link_chunks(
        source_path: Annotated[
            str,
            Field(
                description="Đường dẫn phân cấp LTree của chunk nguồn.",
            ),
        ],
        target_path: Annotated[
            str,
            Field(
                description="Đường dẫn phân cấp LTree của chunk đích.",
            ),
        ],
        relation_type: Annotated[
            RelationType,
            Field(
                description="Mã quan hệ hệ thống hợp lệ kết nối hai chunk.",
            ),
        ],
        citation_text: Annotated[
            str,
            Field(
                min_length=1,
                description="Đoạn văn trích dẫn nguyên văn từ chunk nguồn chứng minh quan hệ.",
            ),
        ],
        rationale: Annotated[
            str | None,
            Field(
                default=None,
                description="Lý do / bằng chứng luận cứ kết nối hai chunk.",
            ),
        ] = None,
    ) -> dict[str, object]:
        return await tool_impl.link_chunks(
            source_path=source_path,
            target_path=target_path,
            relation_type=relation_type,
            citation_text=citation_text,
            rationale=rationale,
        )

    @server.tool(
        name="unlink_chunks",
        description=(
            "Gỡ bỏ cạnh quan hệ đồ thị tri thức giữa 2 chunk dựa trên đường dẫn LTree phân cấp. "
            "Nếu relation_type không được cung cấp (None), toàn bộ các cạnh nối giữa 2 chunk này sẽ được gỡ bỏ."
        ),
    )
    async def unlink_chunks(
        source_path: Annotated[
            str,
            Field(
                description="Đường dẫn phân cấp LTree của chunk nguồn.",
            ),
        ],
        target_path: Annotated[
            str,
            Field(
                description="Đường dẫn phân cấp LTree của chunk đích.",
            ),
        ],
        relation_type: Annotated[
            RelationType | None,
            Field(
                default=None,
                description="Mã loại quan hệ cần gỡ (để None nếu muốn xóa toàn bộ mọi cạnh nối giữa 2 chunk).",
            ),
        ] = None,
    ) -> dict[str, object]:
        return await tool_impl.unlink_chunks(
            source_path=source_path,
            target_path=target_path,
            relation_type=relation_type,
        )

    @server.tool(
        name="get_raw",
        description=(
            "Đọc văn bản gốc nguyên bản của tài liệu theo phạm vi dòng [start_line, end_line]. "
            "Hỗ trợ truyền mã doc_slug hoặc đường dẫn LTree path của chunk để tự động nhận diện tài liệu. "
            "Tối đa 200 dòng mỗi lần gọi để chống tràn context."
        ),
    )
    async def get_raw(
        path_or_slug: Annotated[
            str,
            Field(
                min_length=1,
                description="Mã định danh doc_slug của tài liệu hoặc LTree path của chunk bất kỳ trong tài liệu.",
            ),
        ],
        start_line: Annotated[
            int,
            Field(
                default=1,
                ge=1,
                description="Dòng bắt đầu cần đọc (1-indexed, mặc định là 1).",
            ),
        ] = 1,
        end_line: Annotated[
            int | None,
            Field(
                default=None,
                ge=1,
                description="Dòng kết thúc cần đọc (1-indexed). Để None để đọc tối đa 200 dòng kể từ start_line.",
            ),
        ] = None,
    ) -> RawDocumentSliceResult:
        return await tool_impl.get_raw(
            path_or_slug=path_or_slug,
            start_line=start_line,
            end_line=end_line,
        )
