from __future__ import annotations

from typing import Annotated

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from rag_eval.mcp.tools import (
    CorpusMCPTools,
)
from rag_eval.schemas import (
    CurateEdgesResult,
    EdgeKey,
    EdgeProposal,
    GraphDirection,
    HierarchicalDirection,
    RawDocumentSliceResult,
    RelationType,
    UnifiedGraphTraverseResult,
    UnifiedHierarchyResult,
    UnifiedSearchResult,
    format_graph_direction_docs,
    format_hierarchical_direction_docs,
    format_hierarchical_direction_values,
    format_relation_type_docs,
)


def register_mcp_tools(server: MCPServer, tool_impl: CorpusMCPTools) -> None:
    """Registers the 5 canonical Agent-First corpus tools onto the MCPServer instance."""

    @server.tool(
        name="hybrid_search",
        description=(
            "Truy xuất nội dung đa chiều kết hợp: Đồng thời tìm kiếm ngữ nghĩa theo `query` "
            "và đối sánh ký tự chính xác theo từ khóa neo `pattern`. "
            "Trả về kết quả hợp nhất gom nhóm theo tài liệu và ngữ cảnh với thứ hạng toàn cục 1..N."
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
    ) -> UnifiedSearchResult:
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
            "Duyệt cấu trúc cây phân cấp tài liệu xoay quanh một nút/chunk được chỉ định "
            f"theo các hướng {format_hierarchical_direction_values()}. "
            "Trả về các provisions gom nhóm theo ngữ cảnh phả hệ theo thứ tự đọc tự nhiên."
        ),
    )
    async def hierarchical_navigate(
        path: Annotated[
            str,
            Field(
                description="Đường dẫn phân cấp LTree của nút mục tiêu.",
            ),
        ],
        direction: Annotated[
            HierarchicalDirection,
            Field(
                default=HierarchicalDirection.CHILDREN,
                description=format_hierarchical_direction_docs(),
            ),
        ] = HierarchicalDirection.CHILDREN,
        limit: Annotated[
            int,
            Field(
                default=15,
                ge=1,
                le=50,
                description="Số lượng provisions tối đa trả về (mặc định 15, tối đa 50).",
            ),
        ] = 15,
    ) -> UnifiedHierarchyResult:
        return await tool_impl.hierarchical_navigate(
            path=path,
            direction=direction,
            limit=limit,
        )

    @server.tool(
        name="graph_traverse",
        description=(
            "Duyệt đồ thị tri thức đệ quy qua các liên kết quan hệ giữa các chunk/nút, "
            "gom nhóm theo bằng chứng trích dẫn (citation_text) kèm hạn mức công bằng."
        ),
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
                default=GraphDirection.OUTGOING,
                description=format_graph_direction_docs(),
            ),
        ] = GraphDirection.OUTGOING,
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
            list[RelationType] | None,
            Field(
                default=None,
                description=format_relation_type_docs(),
            ),
        ] = None,
        limit_per_link: Annotated[
            int,
            Field(
                default=20,
                ge=1,
                le=100,
                description="Hạn mức tối đa số provisions trả về cho mỗi liên kết trích dẫn.",
            ),
        ] = 20,
    ) -> UnifiedGraphTraverseResult:
        return await tool_impl.graph_traverse(
            source_path=source_path,
            direction=direction,
            max_depth=max_depth,
            filter_relations=filter_relations,
            limit_per_link=limit_per_link,
        )

    @server.tool(
        name="graph_curate_edges",
        description=(
            "Thực thi cập nhật quan hệ tri thức theo lô (batch proposal) nguyên tử trong một transaction: "
            "Thêm các cạnh mới với kiểm tra neo trích dẫn (citation_text) nguyên văn và mở rộng nút container, "
            "Gỡ bỏ các cạnh cũ đối xứng theo container, và ghi log kiểm toán bắt buộc vào graph_edge_log."
        ),
    )
    async def graph_curate_edges(
        reason: Annotated[
            str,
            Field(
                min_length=1,
                description="Lý do / ngữ cảnh nhiệm vụ bắt buộc phục vụ kiểm toán.",
            ),
        ],
        add_edges: Annotated[
            list[EdgeProposal] | None,
            Field(
                default=None,
                description="Danh sách các cạnh quan hệ đề xuất thêm kèm bằng chứng trích dẫn.",
            ),
        ] = None,
        remove_edges: Annotated[
            list[EdgeKey] | None,
            Field(
                default=None,
                description="Danh sách các cạnh quan hệ yêu cầu gỡ bỏ.",
            ),
        ] = None,
    ) -> CurateEdgesResult:
        return await tool_impl.graph_curate_edges(
            add_edges=add_edges,
            remove_edges=remove_edges,
            reason=reason,
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
