import { useCallback, useEffect, useState } from 'react';
import { api } from '../services/api';
import { PreFlightValidationResponse } from '../types/preflight';

export function usePreFlightCheck(docSlug?: string) {
  const [validationResult, setValidationResult] =
    useState<PreFlightValidationResponse | null>(null);
  const [validating, setValidating] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  const runValidation = useCallback(async () => {
    if (!docSlug) {
      setValidationResult(null);
      return null;
    }
    setValidating(true);
    setValidationError(null);
    try {
      const res = await api.validateSession(docSlug);
      setValidationResult(res);
      return res;
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : 'Lỗi chạy kiểm tra tính toàn vẹn';
      setValidationError(msg);
      return null;
    } finally {
      setValidating(false);
    }
  }, [docSlug]);

  useEffect(() => {
    if (docSlug) {
      void runValidation();
    }
  }, [docSlug, runValidation]);

  return {
    validationResult,
    validating,
    validationError,
    runValidation,
  };
}
