from __future__ import annotations

from typing import Annotated

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from rag_eval.ingestion.staging.models import (
    StagingChunkDelta,
    StagingEdge,
    StagingEdgeFilter,
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
    RelationTypeFilter,
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
    StgPreviewResult,
    StgRemoveEdgeResult,
    StgReopenResult,
    StgReparentResult,
    VerbatimGrepResult,
)


def register_mcp_tools(server: MCPServer, tool_impl: CorpusMCPTools) -> None:
    """Registers all 19 canonical Agent-First corpus tools onto the MCPServer instance."""

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
            "Truy xuất các chunk nội dung thông qua kết hợp xếp hạng ngữ nghĩa (Dense Vector) "
            "và đối sánh từ khóa (Sparse Full-Text Search RRF)."
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
                description="Bật hoặc tắt bước xếp hạng lại bằng cross-encoder. Mặc định tắt.",
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
            "trên toàn bộ kho tài liệu. Tối ưu hóa bằng chỉ mục Trigram GIN làm điểm neo."
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
            "Duyệt cấu trúc cây phân cấp tài liệu xoay quanh một nút/chunk được chỉ định thông qua toán tử ltree. "
            "Duyệt các hướng: CHILDREN, PARENT_CHAIN, SIBLINGS."
        ),
    )
    async def hierarchical_navigate(
        path: Annotated[
            str | None,
            Field(
                default=None,
                description="Đường dẫn cây phân cấp ltree của nút mục tiêu. Cung cấp 'path' hoặc 'chunk_id'.",
            ),
        ] = None,
        chunk_id: Annotated[
            str | None,
            Field(
                default=None,
                description="Mã định danh UUID tùy chọn của chunk cần duyệt mở rộng (dùng khi không có path).",
            ),
        ] = None,
        direction: Annotated[
            HierarchicalDirection,
            Field(
                default=HierarchicalDirection.CHILDREN,
                description=HIERARCHICAL_DIRECTION_DESCRIPTION,
            ),
        ] = HierarchicalDirection.CHILDREN,
    ) -> HierarchicalNavigateResult:
        return await tool_impl.hierarchical_navigate(
            path=path or None,
            chunk_id=chunk_id or None,
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
                description="Đường dẫn cây phân cấp ltree của nút gốc bắt đầu duyệt.",
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
        name="stg_preview",
        description="Xem trước tóm tắt cấu trúc, nội dung nguyên văn và ngữ cảnh tổng hợp của các chunk trong vùng đệm staging.",
    )
    async def stg_preview(
        doc_slug: Annotated[
            str,
            Field(
                description="Mã định danh doc_slug của phiên làm việc trong vùng đệm.",
            ),
        ],
        path_prefix: Annotated[
            str,
            Field(
                default="",
                description="Tiền tố đường dẫn ltree tùy chọn để lọc danh sách xem trước.",
            ),
        ] = "",
        limit: Annotated[
            int,
            Field(
                default=50,
                ge=1,
                le=200,
                description="Số lượng chunk tối đa cần xem trước trên mỗi trang.",
            ),
        ] = 50,
        offset: Annotated[
            int,
            Field(
                default=0,
                ge=0,
                description="Vị trí bắt đầu phân trang danh sách xem trước.",
            ),
        ] = 0,
    ) -> StgPreviewResult:
        return await tool_impl.stg_preview(
            doc_slug=doc_slug,
            path_prefix=path_prefix or None,
            limit=limit,
            offset=offset,
        )

    @server.tool(
        name="stg_get_chunk",
        description="Đọc toàn bộ nội dung nguyên văn, ngữ cảnh tổng hợp, câu dẫn đề và siêu dữ liệu của một chunk từ vùng đệm staging theo đường dẫn ltree.",
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
                description="Đường dẫn phân cấp ltree chính xác của chunk cần đọc toàn văn.",
            ),
        ],
    ) -> StgGetChunkResult:
        return await tool_impl.stg_get_chunk(doc_slug=doc_slug, path=path)

    @server.tool(
        name="stg_get_raw",
        description="Đọc tài liệu nguồn ban đầu được lưu trong phiên staging theo cửa sổ dòng (line window).",
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
                description="Số thứ tự dòng kết thúc (bao gồm cả dòng này).",
            ),
        ] = 100,
    ) -> StgGetRawResult:
        return await tool_impl.stg_get_raw(
            doc_slug=doc_slug, start_line=start_line, end_line=end_line
        )

    @server.tool(
        name="stg_grep",
        description="Tìm kiếm chuỗi ký tự hoặc biểu thức chính quy Regex quét qua toàn bộ các chunk trong vùng đệm staging.",
    )
    async def stg_grep(
        doc_slug: Annotated[
            str,
            Field(
                description="Mã định danh doc_slug của phiên làm việc trong vùng đệm staging.",
            ),
        ],
        pattern: Annotated[
            str,
            Field(
                description="Cụm từ tìm kiếm hoặc biểu thức chính quy (Regex).",
            ),
        ],
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
            doc_slug=doc_slug,
            pattern=pattern,
            is_regex=is_regex,
            case_sensitive=case_sensitive,
            search_in=search_in,
            limit=limit,
        )

    @server.tool(
        name="stg_patch",
        description="Thực hiện vá lỗi vi phẫu, tạo mới (upsert) hoặc xóa các chunk trong vùng đệm staging.",
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
                description="Danh sách các đường dẫn ltree của các chunk cần xóa khỏi phiên làm việc.",
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
            list[StagingEdge],
            Field(
                description="Danh sách các cạnh quan hệ đồ thị tuân thủ StagingEdge.",
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
                description="Đường dẫn ltree cũ cần di chuyển.",
            ),
        ],
        new_path_prefix: Annotated[
            str,
            Field(
                description="Đường dẫn ltree đích mới.",
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
        name="stg_poll_pending",
        description="Lấy danh sách các chunk chưa chốt (PENDING) kèm thống kê tiến độ rà soát tổng thể trong vùng đệm staging.",
    )
    async def stg_poll_pending(
        doc_slug: Annotated[
            str,
            Field(
                description="Mã định danh doc_slug của phiên làm việc trong vùng đệm staging.",
            ),
        ],
        limit: Annotated[
            int,
            Field(
                default=10,
                ge=1,
                le=50,
                description="Số lượng chunk tối đa cần lấy ra trong đợt này.",
            ),
        ] = 10,
        path_prefix: Annotated[
            str,
            Field(
                default="",
                description="Tiền tố đường dẫn ltree tùy chọn để giới hạn phạm vi quét.",
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
        description="Đánh dấu danh sách các chunk sang trạng thái đã rà soát (review_status = 'REVIEWED').",
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
                description="Danh sách đường dẫn ltree của các chunk cần chốt hoàn tất.",
            ),
        ],
    ) -> StgFinalizeResult:
        return await tool_impl.stg_finalize_chunks(
            doc_slug=doc_slug,
            paths=paths,
        )

    @server.tool(
        name="stg_list_sessions",
        description="Liệt kê danh sách tóm tắt toàn bộ các phiên làm việc đang có trong vùng đệm staging (.cache/stg).",
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
        description="Mở lại phiên làm việc của một tài liệu đã promote vào PostgreSQL sang trạng thái AMENDMENT.",
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
                description="Lý do hoặc ghi chú mở lại phiên làm việc để phục vụ kiểm toán WAL.",
            ),
        ] = "",
    ) -> StgReopenResult:
        return await tool_impl.stg_reopen_session(
            doc_slug=doc_slug,
            reason=reason,
        )

    @server.tool(
        name="stg_remove_edge",
        description="Xóa bỏ một hoặc nhiều cạnh quan hệ đồ thị khỏi phiên làm việc staging.",
    )
    async def stg_remove_edge(
        doc_slug: Annotated[
            str,
            Field(
                description="Mã định danh doc_slug của phiên làm việc trong vùng đệm staging.",
            ),
        ],
        source_path: Annotated[
            str,
            Field(
                default="",
                description="Đường dẫn ltree của chunk nguồn.",
            ),
        ] = "",
        target_path: Annotated[
            str | None,
            Field(
                default=None,
                description="Đường dẫn ltree của chunk đích nội bộ cần xóa.",
            ),
        ] = None,
        relation_type: Annotated[
            RelationTypeFilter | None,
            Field(
                default=None,
                description="Loại quan hệ cần xóa. Nếu để trống/None, sẽ xóa cạnh khớp nguồn và đích bất kể loại quan hệ.",
            ),
        ] = None,
        clear_all_targets: Annotated[
            bool,
            Field(
                default=False,
                description="Xác nhận tường minh việc xóa toàn bộ mọi cạnh xuất phát từ source_path bất kể đích đến.",
            ),
        ] = False,
        edges: Annotated[
            list[StagingEdgeFilter] | None,
            Field(
                default=None,
                description="Danh sách các bộ lọc cạnh cần xóa hàng loạt trong 1 lần gọi.",
            ),
        ] = None,
    ) -> StgRemoveEdgeResult:
        return await tool_impl.stg_remove_edge(
            doc_slug=doc_slug,
            source_path=source_path,
            target_path=target_path,
            relation_type=relation_type or None,
            clear_all_targets=clear_all_targets,
            edges=edges,
        )
