from __future__ import annotations


class CorpusDomainError(Exception):
    """Ngoại lệ miền nghiệp vụ chuẩn mực cho toàn bộ hệ thống RAG."""

    def __init__(
        self,
        error_code: int,
        message: str,
        data: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.data: dict[str, object] = data or {}


# ---------------------------------------------------------------------------
# Discrete Error Codes
# ---------------------------------------------------------------------------

E_STORAGE_CONNECTION: int = 1001
E_CORPUS_INTEGRITY_VIOLATION: int = 1002
E_INVALID_DOCUMENT_HIERARCHY: int = 1003
E_AST_GROUNDING_VALIDATION: int = 1004
