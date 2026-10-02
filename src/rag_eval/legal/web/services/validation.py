from __future__ import annotations

from rag_eval.legal.ingestion.staging.session import StagingDocumentSession
from rag_eval.legal.schemas import (
    LTREE_PATH_REGEX,
    sanitize_ltree_label,
)
from rag_eval.legal.web.schemas import (
    PreFlightValidationResponse,
    ValidationIssue,
)


class PreFlightValidator:
    """Runs automated integrity checks against a StagingDocumentSession before promotion."""

    TOTAL_CHECKS = 7

    def validate(self, session: StagingDocumentSession) -> PreFlightValidationResponse:
        """Executes all 7 integrity validation rules against the session."""
        issues: list[ValidationIssue] = []
        summary: dict[str, object] = {}

        invalid_path_count = 0
        for chunk in session.chunks:
            if not chunk.path or not LTREE_PATH_REGEX.match(chunk.path.strip()):
                invalid_path_count += 1
                issues.append(
                    ValidationIssue(
                        rule="LTREE_PATH_SYNTAX",
                        severity="ERROR",
                        path=chunk.path,
                        message=f"Chunk path '{chunk.path}' violates LTREE dot-syntax regex.",
                        blocking=True,
                    )
                )
        summary["ltree_path_syntax"] = {
            "passed": invalid_path_count == 0,
            "violations": invalid_path_count,
        }

        sanitized_doc_slug = sanitize_ltree_label(session.doc_slug)
        mismatched_root_count = 0
        for chunk in session.chunks:
            prefix = chunk.path.split(".")[0] if "." in chunk.path else chunk.path
            if prefix != sanitized_doc_slug and not prefix.startswith(sanitized_doc_slug):
                mismatched_root_count += 1
                issues.append(
                    ValidationIssue(
                        rule="ROOT_CODE_ALIGNMENT",
                        severity="ERROR",
                        path=chunk.path,
                        message=(
                            f"Chunk root prefix '{prefix}' does not align with sanitized "
                            f"document code '{sanitized_doc_slug}'."
                        ),
                        blocking=True,
                    )
                )
        summary["root_code_alignment"] = {
            "passed": mismatched_root_count == 0,
            "violations": mismatched_root_count,
        }

        continuity_violations = 0
        staged_paths = {c.path for c in session.chunks}
        if not session.chunks:
            continuity_violations += 1
            issues.append(
                ValidationIssue(
                    rule="PARENT_CHILD_CONTINUITY",
                    severity="ERROR",
                    path=None,
                    message="Staging session contains zero chunks.",
                    blocking=True,
                )
            )

        summary["parent_child_continuity"] = {
            "passed": continuity_violations == 0,
            "violations": continuity_violations,
        }

        date_violations = 0
        if (
            session.valid_from is not None
            and session.valid_to is not None
            and session.valid_to < session.valid_from
        ):
            date_violations += 1
            issues.append(
                ValidationIssue(
                    rule="VALIDITY_DATES",
                    severity="ERROR",
                    path=None,
                    message=(
                        f"Document valid_to ({session.valid_to}) cannot be earlier "
                        f"than valid_from ({session.valid_from})."
                    ),
                    blocking=True,
                )
            )

        summary["validity_dates"] = {
            "passed": date_violations == 0,
            "violations": date_violations,
        }

        empty_text_violations = 0
        for chunk in session.chunks:
            if not chunk.verbatim_text or not chunk.verbatim_text.strip():
                empty_text_violations += 1
                issues.append(
                    ValidationIssue(
                        rule="CONTENT_GROUNDING",
                        severity="ERROR",
                        path=chunk.path,
                        message=f"Chunk '{chunk.path}' has empty verbatim_text.",
                        blocking=True,
                    )
                )
            if not chunk.contextualized_text or not chunk.contextualized_text.strip():
                empty_text_violations += 1
                issues.append(
                    ValidationIssue(
                        rule="CONTENT_GROUNDING",
                        severity="ERROR",
                        path=chunk.path,
                        message=f"Chunk '{chunk.path}' has empty contextualized_text.",
                        blocking=True,
                    )
                )

        summary["content_grounding"] = {
            "passed": empty_text_violations == 0,
            "violations": empty_text_violations,
        }

        edge_violations = 0
        for edge in session.edges:
            if edge.source_path not in staged_paths:
                edge_violations += 1
                issues.append(
                    ValidationIssue(
                        rule="GRAPH_EDGE_INTEGRITY",
                        severity="ERROR",
                        path=edge.source_path,
                        message=(
                            f"Graph edge source_path '{edge.source_path}' does not exist "
                            f"in staged chunks for this document."
                        ),
                        blocking=True,
                    )
                )
            if not edge.target_path and not edge.target_external_ref:
                edge_violations += 1
                issues.append(
                    ValidationIssue(
                        rule="GRAPH_EDGE_INTEGRITY",
                        severity="ERROR",
                        path=edge.source_path,
                        message=(
                            f"Graph edge from source '{edge.source_path}' must specify either "
                            f"a target_path or target_external_ref."
                        ),
                        blocking=True,
                    )
                )

        summary["graph_edge_integrity"] = {
            "passed": edge_violations == 0,
            "violations": edge_violations,
        }

        seen_paths: set[str] = set()
        duplicate_paths: set[str] = set()
        for chunk in session.chunks:
            if chunk.path in seen_paths:
                duplicate_paths.add(chunk.path)
            seen_paths.add(chunk.path)

        if duplicate_paths:
            for dp in duplicate_paths:
                issues.append(
                    ValidationIssue(
                        rule="DUPLICATE_PATH_COLLISION",
                        severity="ERROR",
                        path=dp,
                        message=f"Duplicate chunk path collision detected: '{dp}'.",
                        blocking=True,
                    )
                )
        summary["duplicate_path_collision"] = {
            "passed": len(duplicate_paths) == 0,
            "violations": len(duplicate_paths),
        }

        blocking_issues = [i for i in issues if i.blocking]
        passed = len(blocking_issues) == 0
        status = "PASSED" if passed else "FAILED"

        return PreFlightValidationResponse(
            status=status,
            passed=passed,
            total_checks=7,
            issues=issues,
            summary=summary,
        )
