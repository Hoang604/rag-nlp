from __future__ import annotations

from typing import Annotated

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from rag_eval.ingestion.staging.models import (
    DEFAULT_STAGING_POLL_LIMIT,
    MAX_STAGING_POLL_LIMIT,
    MIN_STAGING_POLL_LIMIT,
    StagingChunkDelta,
    StagingEdgeFilter,
    StagingEdgeInput,
)
from rag_eval.mcp.tools import (
    HIERARCHICAL_DIRECTION_DESCRIPTION,
    ChunkBacklogResult,
    CorpusMCPTools,
    GraphDirection,
    GraphTraverseResult,
    HierarchicalDirection,
    HierarchicalNavigateResult,
    HybridSearchResult,
    StagingStatusFilter,
    StgAddEdgesResult,
    StgCommitResult,
    StgFinalizeResult,
    StgGetChunkResult,
    StgGetRawResult,
    StgGrepResult,
    StgGrepScope,
    StgListSessionsResult,
    StgPatchResult,
    StgPollPendingResult,
    StgRemoveEdgesResult,
    StgReopenResult,
    StgReparentResult,
    StgUncommitResult,
    StgUnfinalizeResult,
    VerbatimGrepResult,
)


def register_mcp_tools(server: MCPServer, tool_impl: CorpusMCPTools) -> None:
    """Registers all 20 canonical Agent-First corpus tools onto the MCPServer instance."""

    @server.tool(
        name="stg_validate",
        description="Kiểm tra tiền kiểm toán (pre-flight validation) các bất biến toàn vẹn của phiên staging trước khi cam kết.",
    )
    async def stg_validate(
        doc_slug: Annotated[
            str,
            Field(
                description="Mã định danh doc_slug của phiên làm việc trong vùng đệm staging.",
            ),
        ],
    ) -> dict[str, object]:
        return await tool_impl.stg_validate(doc_slug=doc_slug)

    @server.tool(
        name="hybrid_search",
        description=(
            "Truy xuất các chunk nội dung thông qua kết hợp xếp hạng ngữ nghĩa "
            "và đối sánh từ khóa."
        ),
    )
    async def hybrid_search(
        query: Annotated[
            str,
            Field(
                description=(
                    "Truy vấn chuẩn hóa: Chuyển hóa câu hỏi hoặc tình huống thành từ khóa cốt lõi."
                ),
            ),
        ],
        limit: Annotated[
            int,
            Field(
                default=10,
                ge=1,
                le=50,
                description="Số lượng chunk nội dung tối đa cần trả về, sắp xếp theo điểm hòa trộn tương đồng giảm dần.",
            ),
        ] = 10,
        doc_slugs: Annotated[
            list[str] | None,
            Field(
                default=None,
                description="Giới hạn phạm vi tìm kiếm theo danh sách doc_slug. Để None để tìm trên toàn bộ kho.",
            ),
        ] = None,
        rerank: Annotated[
            bool,
            Field(
                default=False,
                description="Bật hoặc tắt bước xếp hạng lại kết quả tìm kiếm. Mặc định tắt.",
            ),
        ] = False,
    ) -> HybridSearchResult:
        return await tool_impl.hybrid_search(
            query=query,
            limit=limit,
            doc_slugs=doc_slugs or None,
            rerank=rerank or None,
        )

    @server.tool(
        name="verbatim_grep",
        description=(
            "Tìm kiếm chính xác tuyệt đối theo chuỗi nguyên văn hoặc biểu thức chính quy POSIX "
            "trên toàn bộ kho tài liệu."
        ),
    )
    async def verbatim_grep(
        pattern: Annotated[
            str,
            Field(
                description="Chuỗi ký tự nguyên văn đặc trưng hoặc biểu thức chính quy POSIX.",
            ),
        ],
        is_regex: Annotated[
            bool,
            Field(
                default=False,
                description="Bật chế độ đánh giá biểu thức chính quy POSIX đối với chuỗi tìm kiếm.",
            ),
        ] = False,
        case_sensitive: Annotated[
            bool,
            Field(
                default=False,
                description="Bắt buộc phân biệt chữ hoa chữ thường khi so khớp chuỗi.",
            ),
        ] = False,
        limit: Annotated[
            int,
            Field(
                default=20,
                ge=1,
                le=100,
                description="Số lượng kết quả khớp tối đa cần trả về.",
            ),
        ] = 20,
    ) -> VerbatimGrepResult:
        return await tool_impl.verbatim_grep(
            pattern=pattern,
            is_regex=is_regex,
            case_sensitive=case_sensitive,
            limit=limit,
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
    ) -> GraphTraverseResult:
        return await tool_impl.graph_traverse(
            source_path=source_path,
            direction=direction,
            max_depth=max_depth,
            filter_relations=filter_relations,
        )

    @server.tool(
        name="stg_get_chunk",
        description=(
            "Đọc toàn bộ nội dung nguyên văn, ngữ cảnh tổng hợp, câu dẫn đề và siêu dữ liệu của một chunk "
            "từ vùng đệm staging theo đường dẫn phân cấp. Việc đọc chunk này (tương tự như qua stg_poll_pending hoặc stg_get_raw) "
            "sẽ đồng thời ghi nhận dấu vết nhận thức (inspected), làm tiền đề bắt buộc trước khi có thể chốt nghiệm thu (finalize)."
        ),
    )
    async def stg_get_chunk(
        doc_slug: Annotated[
            str,
            Field(
                description="Mã định danh doc_slug của phiên làm việc trong vùng đệm staging.",
            ),
        ],
        path: Annotated[
            str,
            Field(
                description="Đường dẫn phân cấp chính xác của chunk cần đọc toàn văn.",
            ),
        ],
    ) -> StgGetChunkResult:
        return await tool_impl.stg_get_chunk(doc_slug=doc_slug, path=path)

    @server.tool(
        name="stg_get_raw",
        description="Đọc tài liệu nguồn ban đầu được lưu trong phiên staging theo cửa sổ dòng (line window, tối đa 200 dòng mỗi lần gọi).",
    )
    async def stg_get_raw(
        doc_slug: Annotated[
            str,
            Field(
                description="Mã định danh doc_slug của phiên làm việc trong vùng đệm staging.",
            ),
        ],
        start_line: Annotated[
            int,
            Field(
                default=1,
                ge=1,
                description="Số thứ tự dòng bắt đầu (đánh số từ 1).",
            ),
        ] = 1,
        end_line: Annotated[
            int,
            Field(
                default=100,
                ge=1,
                description="Số thứ tự dòng kết thúc (bao gồm cả dòng này). Cửa sổ dòng (end_line - start_line + 1) tối đa là 200 dòng.",
            ),
        ] = 100,
    ) -> StgGetRawResult:
        return await tool_impl.stg_get_raw(
            doc_slug=doc_slug, start_line=start_line, end_line=end_line
        )

    @server.tool(
        name="stg_grep",
        description="Tìm kiếm chuỗi ký tự hoặc biểu thức chính quy Regex quét qua các chunk trong vùng đệm staging (một tài liệu hoặc toàn bộ phiên).",
    )
    async def stg_grep(
        pattern: Annotated[
            str,
            Field(
                description="Cụm từ tìm kiếm hoặc biểu thức chính quy (Regex).",
            ),
        ],
        doc_slug: Annotated[
            str | None,
            Field(
                default=None,
                description="Mã định danh doc_slug tùy chọn (để trống nếu muốn quét toàn bộ các phiên staging).",
            ),
        ] = None,
        is_regex: Annotated[
            bool,
            Field(
                default=False,
                description="Bật chế độ đánh giá biểu thức chính quy Regex.",
            ),
        ] = False,
        case_sensitive: Annotated[
            bool,
            Field(
                default=False,
                description="Bắt buộc phân biệt chữ hoa chữ thường.",
            ),
        ] = False,
        search_in: Annotated[
            StgGrepScope,
            Field(
                default="ALL",
                description="Phạm vi tìm kiếm: 'ALL', 'VERBATIM', 'CONTEXT', 'PATH', 'METADATA'.",
            ),
        ] = "ALL",
        limit: Annotated[
            int,
            Field(
                default=50,
                ge=1,
                le=200,
                description="Số lượng kết quả khớp tối đa cần trả về.",
            ),
        ] = 50,
    ) -> StgGrepResult:
        return await tool_impl.stg_grep(
            pattern=pattern,
            doc_slug=doc_slug,
            is_regex=is_regex,
            case_sensitive=case_sensitive,
            search_in=search_in,
            limit=limit,
        )

    @server.tool(
        name="stg_patch",
        description="Thực hiện vá lỗi vi phẫu, phân loại context_type kèm giải trình, tạo mới (upsert) hoặc xóa các chunk trong vùng đệm staging.",
    )
    async def stg_patch(
        doc_slug: Annotated[
            str,
            Field(
                description="Mã định danh doc_slug của phiên làm việc trong vùng đệm.",
            ),
        ],
        updated_chunks: Annotated[
            list[StagingChunkDelta] | None,
            Field(
                default=None,
                description="Danh sách các bản vá hoặc tạo mới chunk chi tiết theo StagingChunkDelta.",
            ),
        ] = None,
        removed_paths: Annotated[
            list[str] | None,
            Field(
                default=None,
                description="Danh sách các đường dẫn phân cấp của các chunk cần xóa khỏi phiên làm việc.",
            ),
        ] = None,
        cascade_breadcrumbs: Annotated[
            bool,
            Field(
                default=True,
                description="Tự động cập nhật ngữ cảnh contextualized_text cho các nút con khi câu dẫn đề của nút cha thay đổi.",
            ),
        ] = True,
    ) -> StgPatchResult:
        return await tool_impl.stg_patch(
            doc_slug=doc_slug,
            updated_chunks=updated_chunks or None,
            removed_paths=removed_paths or None,
            cascade_breadcrumbs=cascade_breadcrumbs,
        )

    @server.tool(
        name="stg_add_edges",
        description="Gắn kết các cạnh quan hệ đồ thị trong vùng đệm staging.",
    )
    async def stg_add_edges(
        doc_slug: Annotated[
            str,
            Field(
                description="Mã định danh doc_slug của phiên làm việc trong vùng đệm.",
            ),
        ],
        edges: Annotated[
            list[StagingEdgeInput],
            Field(
                description="Danh sách các cạnh quan hệ đồ thị tuân thủ StagingEdgeInput.",
            ),
        ],
    ) -> StgAddEdgesResult:
        return await tool_impl.stg_add_edges(
            doc_slug=doc_slug,
            edges=edges,
        )

    @server.tool(
        name="stg_reparent",
        description="Tái cấu trúc và di chuyển cả một nhánh cây sang vị trí cha mới trong vùng đệm staging.",
    )
    async def stg_reparent(
        doc_slug: Annotated[
            str,
            Field(
                description="Mã định danh doc_slug của phiên làm việc trong vùng đệm.",
            ),
        ],
        old_path_prefix: Annotated[
            str,
            Field(
                description="Đường dẫn phân cấp cũ cần di chuyển.",
            ),
        ],
        new_path_prefix: Annotated[
            str,
            Field(
                description="Đường dẫn phân cấp đích mới.",
            ),
        ],
        dry_run: Annotated[
            bool,
            Field(
                default=False,
                description="Nếu True, chỉ tính toán và mô phỏng số lượng node sẽ thay đổi mà không ghi xuống đĩa.",
            ),
        ] = False,
    ) -> StgReparentResult:
        return await tool_impl.stg_reparent(
            doc_slug=doc_slug,
            old_path_prefix=old_path_prefix,
            new_path_prefix=new_path_prefix,
            dry_run=dry_run,
        )

    @server.tool(
        name="stg_commit",
        description="Xác nhận hoàn tất phiên xử lý của Agent trong vùng đệm staging, chuyển trạng thái phiên sang AGENT_COMMITTED.",
    )
    async def stg_commit(
        doc_slug: Annotated[
            str,
            Field(
                description="Mã định danh doc_slug cần xác nhận hoàn tất trong vùng đệm staging.",
            ),
        ],
    ) -> StgCommitResult:
        return await tool_impl.stg_commit(
            doc_slug=doc_slug,
        )

    @server.tool(
        name="stg_uncommit",
        description="Mở lại phiên làm việc từ trạng thái AGENT_COMMITTED về trạng thái mở (DRAFT hoặc AMENDMENT) để tiếp tục hiệu chỉnh hoặc nghiệm thu lại chunk.",
    )
    async def stg_uncommit(
        doc_slug: Annotated[
            str,
            Field(
                description="Mã định danh doc_slug của phiên làm việc cần mở lại từ AGENT_COMMITTED.",
            ),
        ],
        reason: Annotated[
            str,
            Field(
                default="",
                description="Lý do mở lại phiên làm việc phục vụ nhật ký kiểm toán.",
            ),
        ] = "",
    ) -> StgUncommitResult:
        return await tool_impl.stg_uncommit(
            doc_slug=doc_slug,
            reason=reason,
        )

    @server.tool(
        name="stg_poll_pending",
        description=(
            "Lấy danh sách các chunk chưa chốt (PENDING) kèm thống kê tiến độ rà soát trong vùng đệm staging. "
            "Việc lấy danh sách qua tool này cũng đồng thời ghi nhận dấu vết nhận thức (inspected) cho các chunk được trả về."
        ),
    )
    async def stg_poll_pending(
        doc_slug: Annotated[
            str,
            Field(
                description="Mã định danh doc_slug của phiên làm việc.",
            ),
        ],
        limit: Annotated[
            int,
            Field(
                default=DEFAULT_STAGING_POLL_LIMIT,
                ge=MIN_STAGING_POLL_LIMIT,
                le=MAX_STAGING_POLL_LIMIT,
                description="Số lượng chunk yêu cầu lấy trong đợt này.",
            ),
        ] = DEFAULT_STAGING_POLL_LIMIT,
        path_prefix: Annotated[
            str,
            Field(
                default="",
                description="Tiền tố đường dẫn phân cấp tùy chọn để giới hạn phạm vi quét.",
            ),
        ] = "",
    ) -> StgPollPendingResult:
        return await tool_impl.stg_poll_pending_chunks(
            doc_slug=doc_slug,
            limit=limit,
            path_prefix=path_prefix or None,
        )

    @server.tool(
        name="stg_finalize_chunks",
        description=(
            "Chốt nghiệm thu các chunk trong phiên staging sang trạng thái REVIEWED. "
            "Yêu cầu 3 điều kiện tiên quyết: chunk đã được đọc kiểm tra (inspected) qua stg_poll_pending/stg_get_chunk/stg_get_raw, "
            "đã phân loại context_type qua stg_patch, và nhất quán cạnh quan hệ đồ thị."
        ),
    )
    async def stg_finalize_chunks(
        doc_slug: Annotated[
            str,
            Field(
                description="Mã định danh doc_slug của phiên làm việc trong vùng đệm staging.",
            ),
        ],
        paths: Annotated[
            list[str],
            Field(
                description="Danh sách đường dẫn phân cấp của các chunk cần chốt hoàn tất.",
            ),
        ],
    ) -> StgFinalizeResult:
        return await tool_impl.stg_finalize_chunks(
            doc_slug=doc_slug,
            paths=paths,
        )

    @server.tool(
        name="stg_unfinalize_chunks",
        description=(
            "Mở lại các chunk đã được nghiệm thu trong phiên staging về trạng thái PENDING và UNFINALIZED để chỉnh sửa hoặc bổ sung liên kết. "
            "Hành động này cũng đồng thời hủy trạng thái đã đọc kiểm tra (inspected) của các chunk này."
        ),
    )
    async def stg_unfinalize_chunks(
        doc_slug: Annotated[
            str,
            Field(
                description="Mã định danh doc_slug của phiên làm việc trong vùng đệm staging.",
            ),
        ],
        paths: Annotated[
            list[str],
            Field(
                description="Danh sách đường dẫn phân cấp của các chunk cần mở lại.",
            ),
        ],
    ) -> StgUnfinalizeResult:
        return await tool_impl.stg_unfinalize_chunks(
            doc_slug=doc_slug,
            paths=paths,
        )

    @server.tool(
        name="stg_list_sessions",
        description="Liệt kê danh sách tóm tắt toàn bộ các phiên làm việc đang có trong vùng đệm staging.",
    )
    async def stg_list_sessions(
        status: Annotated[
            StagingStatusFilter,
            Field(
                default="",
                description="Lọc danh sách theo trạng thái phiên làm việc. Để trống để lấy tất cả.",
            ),
        ] = "",
    ) -> StgListSessionsResult:
        return await tool_impl.stg_list_sessions(status=status or None)

    @server.tool(
        name="corpus_backlog_poll",
        description="Truy vấn danh sách các chunk chưa hoàn tất liên kết trên CSDL sản xuất.",
    )
    async def corpus_backlog_poll(
        doc_slug: Annotated[
            str,
            Field(
                default="",
                description="Lọc theo doc_slug tài liệu. Để trống để quét toàn bộ kho.",
            ),
        ] = "",
        limit: Annotated[
            int,
            Field(
                default=50,
                ge=1,
                le=100,
                description="Số lượng chunk tối đa cần trả về.",
            ),
        ] = 50,
    ) -> ChunkBacklogResult:
        return await tool_impl.corpus_backlog_poll(
            doc_slug=doc_slug or None,
            limit=limit,
        )

    @server.tool(
        name="stg_reopen_session",
        description="Mở lại phiên làm việc của một tài liệu đã lưu chính thức sang trạng thái AMENDMENT.",
    )
    async def stg_reopen_session(
        doc_slug: Annotated[
            str,
            Field(
                description="Mã định danh doc_slug cần mở lại phiên làm việc.",
            ),
        ],
        reason: Annotated[
            str,
            Field(
                default="",
                description="Lý do hoặc ghi chú mở lại phiên làm việc để phục vụ kiểm toán.",
            ),
        ] = "",
    ) -> StgReopenResult:
        return await tool_impl.stg_reopen_session(
            doc_slug=doc_slug,
            reason=reason,
        )

    @server.tool(
        name="stg_remove_edges",
        description="Xóa bỏ một hoặc nhiều cạnh quan hệ đồ thị khỏi phiên làm việc staging bằng danh sách bộ lọc StagingEdgeFilter.",
    )
    async def stg_remove_edges(
        doc_slug: Annotated[
            str,
            Field(
                description="Mã định danh doc_slug của phiên làm việc trong vùng đệm staging.",
            ),
        ],
        edges: Annotated[
            list[StagingEdgeFilter],
            Field(
                description="Danh sách các bộ lọc cạnh cần xóa hàng loạt trong 1 lần gọi.",
            ),
        ],
    ) -> StgRemoveEdgesResult:
        return await tool_impl.stg_remove_edges(
            doc_slug=doc_slug,
            edges=edges,
        )

