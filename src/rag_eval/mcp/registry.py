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
from rag_eval.schemas import VennSearchResult


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
        )

    @server.tool(
        name="hierarchical_navigate",
        description=(
            "Duyệt cấu trúc cây phân cấp tài liệu xoay quanh một nút/chunk được chỉ định. "
            "Duyệt các hướng: CHILDREN, PARENT_CHAIN, SIBLINGS."
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
