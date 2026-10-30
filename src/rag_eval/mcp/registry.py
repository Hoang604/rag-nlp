from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Annotated, TypeVar

from mcp.server.mcpserver import MCPServer
from pydantic import BaseModel, Field

from rag_eval.exceptions import CorpusDomainError
from rag_eval.mcp.tools import (
    CitationInput,
    CorpusMCPTools,
    SubmitGroundedAnswerResult,
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

logger = logging.getLogger(__name__)
T = TypeVar("T")
WebhookEmitter = Callable[[str, dict[str, object]], Awaitable[None]]


def register_mcp_tools(
    server: MCPServer,
    tool_impl: CorpusMCPTools,
    *,
    enable_answer_tool: bool = False,
    event_emitter: WebhookEmitter | None = None,
) -> None:
    """Registers the canonical Agent-First corpus tools (and optional submit_grounded_answer) onto the MCPServer instance."""

    async def _run_with_telemetry(
        tool_name: str,
        args: dict[str, object],
        coro: Awaitable[T],
    ) -> T:
        logger.info("[TOOL] START name=%s args=%s", tool_name, args)
        started = time.perf_counter()
        if event_emitter is not None:
            await event_emitter("tool_start", {"tool": tool_name, "args": args})
        try:
            result = await coro
        except Exception as exc:
            elapsed_ms = round((time.perf_counter() - started) * 1000.0, 1)
            err_msg = exc.message if isinstance(exc, CorpusDomainError) else str(exc)
            logger.error("[TOOL] ERROR name=%s: %s", tool_name, err_msg)
            if event_emitter is not None:
                await event_emitter(
                    "tool_error",
                    {
                        "tool": tool_name,
                        "args": args,
                        "error": err_msg,
                        "elapsed_ms": elapsed_ms,
                    },
                )
            raise

        elapsed_ms = round((time.perf_counter() - started) * 1000.0, 1)
        logger.info("[TOOL] SUCCESS name=%s (%.1fms)", tool_name, elapsed_ms)
        if event_emitter is not None:
            serialized_result = (
                result.model_dump(mode="json")
                if isinstance(result, BaseModel)
                else result
            )
            await event_emitter(
                "tool_done",
                {
                    "tool": tool_name,
                    "args": args,
                    "elapsed_ms": elapsed_ms,
                    "result": serialized_result,
                },
            )
            if (
                tool_name == "submit_grounded_answer"
                and isinstance(result, SubmitGroundedAnswerResult)
            ):
                await event_emitter(
                    "answer_submitted",
                    {
                        "tool": tool_name,
                        "elapsed_ms": elapsed_ms,
                        "payload": serialized_result,
                    },
                )
        return result

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
        return await _run_with_telemetry(
            "hybrid_search",
            {
                "query": query,
                "pattern": pattern,
                "limit": limit,
                "rerank": rerank,
                "doc_slugs": doc_slugs,
                "path_prefix": path_prefix,
                "is_regex": is_regex,
                "case_sensitive": case_sensitive,
                "order_by_reading_order": order_by_reading_order,
            },
            tool_impl.hybrid_search(
                query=query,
                pattern=pattern,
                limit=limit,
                rerank=rerank,
                doc_slugs=doc_slugs or None,
                path_prefix=path_prefix or None,
                is_regex=is_regex,
                case_sensitive=case_sensitive,
                order_by_reading_order=order_by_reading_order,
            ),
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
        return await _run_with_telemetry(
            "hierarchical_navigate",
            {"path": path, "direction": str(direction), "limit": limit},
            tool_impl.hierarchical_navigate(
                path=path,
                direction=direction,
                limit=limit,
            ),
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
        return await _run_with_telemetry(
            "graph_traverse",
            {
                "source_path": source_path,
                "direction": str(direction),
                "max_depth": max_depth,
            },
            tool_impl.graph_traverse(
                source_path=source_path,
                direction=direction,
                max_depth=max_depth,
                filter_relations=filter_relations,
                limit_per_link=limit_per_link,
            ),
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
        return await _run_with_telemetry(
            "graph_curate_edges",
            {"reason": reason},
            tool_impl.graph_curate_edges(
                add_edges=add_edges,
                remove_edges=remove_edges,
                reason=reason,
            ),
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
        return await _run_with_telemetry(
            "get_raw",
            {
                "path_or_slug": path_or_slug,
                "start_line": start_line,
                "end_line": end_line,
            },
            tool_impl.get_raw(
                path_or_slug=path_or_slug,
                start_line=start_line,
                end_line=end_line,
            ),
        )

    if enable_answer_tool:

        @server.tool(
            name="submit_grounded_answer",
            description=(
                "Nộp câu trả lời cuối cùng cho người dùng kèm danh sách trích dẫn đường dẫn LTree `path`. "
                "Hệ thống xác thực từng `path` tồn tại trong kho tài liệu trước khi chấp nhận và phát kết quả."
            ),
        )
        async def submit_grounded_answer(
            answer: Annotated[
                str,
                Field(
                    min_length=1,
                    description=(
                        "Nội dung câu trả lời bằng tiếng Việt cho câu hỏi của người dùng, "
                        "đánh dấu trích dẫn inline bằng [#1], [#2], ... tương ứng với thứ tự trong `citations`."
                    ),
                ),
            ],
            citations: Annotated[
                list[CitationInput | str] | None,
                Field(
                    default=None,
                    description=(
                        "Danh sách các trích dẫn chứng thực câu trả lời (mỗi phần tử là chuỗi `path` "
                        "hoặc object `{\"path\": \"...\", \"citation_text\": \"...\"}`). "
                        "Bắt buộc có ít nhất 1 phần tử khi `abstained=False`."
                    ),
                ),
            ] = None,
            abstained: Annotated[
                bool,
                Field(
                    default=False,
                    description=(
                        "Đặt True nếu kho tài liệu không chứa thông tin để trả lời câu hỏi "
                        "(khi đó `citations` được phép để rỗng)."
                    ),
                ),
            ] = False,
        ) -> SubmitGroundedAnswerResult:
            serialized_citations = [
                c.model_dump(mode="json") if isinstance(c, CitationInput) else c
                for c in (citations or [])
            ]
            return await _run_with_telemetry(
                "submit_grounded_answer",
                {
                    "answer": answer,
                    "citations": serialized_citations,
                    "abstained": abstained,
                },
                tool_impl.submit_grounded_answer(
                    answer=answer,
                    citations=citations,
                    abstained=abstained,
                ),
            )
