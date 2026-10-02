export type ValidationSeverity = 'ERROR' | 'WARNING';

export interface ValidationIssue {
  rule: string;
  severity: ValidationSeverity;
  path?: string | null;
  message: string;
  blocking: boolean;
}

export interface RuleCheckSummary {
  passed: boolean;
  message: string;
  severity?: string;
  issues_count?: number;
}

export interface PreFlightValidationResponse {
  status: 'PASSED' | 'FAILED';
  passed: boolean;
  total_checks: number;
  doc_slug?: string;
  issues: ValidationIssue[];
  summary: {
    total_issues?: number;
    blocking_errors?: number;
    warnings?: number;
    passed_rules?: string[];
    failed_rules?: string[];
    rule_status?: Record<string, RuleCheckSummary>;
    [key: string]: unknown;
  };
}
