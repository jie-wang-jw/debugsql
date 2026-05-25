// ================================================
// DebugSQL - Execution Context
//
// Provides execution state and triggerExecution to all panels.
// Uses executionAdapter, which calls the real backend API by default and can
// still run isolated frontend mocks when VITE_USE_MOCK_SERVICES=true.
//
// TODO: Add query cancellation via AbortController.
// TODO: Persist execution history for session replay.
// TODO: Stream execution step progress from backend.
// ================================================

import {
  createContext,
  useContext,
  useState,
  useCallback,
  type ReactNode,
} from 'react';
import type {
  ExecutionStatus,
  ExecutionResult,
  ExecutionResultPreview,
  PlanRun,
} from '../types/execution.types';
import { executeQuery } from '../services/adapters/executionAdapter';
import {
  postPlanRun,
  postPlanRunFull,
  postPlanRunReset,
  postPlanRunStep,
} from '../services/api/queryPlanApi';

export interface ExecutionContextValue {
  /** Current pipeline status. */
  status: ExecutionStatus;
  /** Populated on success; null otherwise. */
  result: ExecutionResult | null;
  /** Populated on failure; null otherwise. */
  error: string | null;
  /** Current step-by-step plan run, if one has been started. */
  planRun: PlanRun | null;
  /**
   * Kick off backend execution for the given query/plan.
   * Sets status to "running", then resolves to "success" or "failed".
   */
  triggerExecution: (query: string, planId?: string | null) => Promise<void>;
  startPlanRun: (planId: string) => Promise<void>;
  stepPlanRun: () => Promise<void>;
  runFullPlan: () => Promise<void>;
  resetPlanRun: () => Promise<void>;
  restoreExecution: (
    preview?: ExecutionResultPreview | null,
    status?: string | null,
  ) => void;
}

const ExecutionContext = createContext<ExecutionContextValue | null>(null);

export function useExecutionContext(): ExecutionContextValue {
  const ctx = useContext(ExecutionContext);
  if (!ctx) {
    throw new Error('useExecutionContext must be used inside <ExecutionProvider>');
  }
  return ctx;
}

export function ExecutionProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<ExecutionStatus>('idle');
  const [result, setResult] = useState<ExecutionResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [planRun, setPlanRun] = useState<PlanRun | null>(null);

  const triggerExecution = useCallback(async (query: string, planId?: string | null) => {
    if (!query.trim()) return;

    setStatus('running');
    setResult(null);
    setError(null);

    try {
      const execResult = await executeQuery(query, planId ?? undefined);
      setResult(execResult);
      setStatus('success');
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Unknown execution error';
      setError(msg);
      setStatus('failed');
    }
  }, []);

  const restoreExecution = useCallback((
    preview?: ExecutionResultPreview | null,
    restoredStatus?: string | null,
  ) => {
    setError(null);
    setPlanRun(null);

    if (!preview) {
      setResult(null);
      setStatus('idle');
      return;
    }

    const rows = preview.rows ?? [];
    const columns = preview.columns ?? [];
    const metrics = {
      planningTimeMs: preview.metrics?.planningTimeMs ?? 0,
      executionTimeMs: preview.metrics?.executionTimeMs ?? 0,
      rowCount: preview.metrics?.rowCount ?? preview.rowCount ?? rows.length,
      estimatedRows: preview.metrics?.estimatedRows ?? preview.rowCount ?? rows.length,
    };

    setResult({
      sql: preview.sql ?? '',
      columns,
      rows,
      metrics,
    });
    setStatus(restoredStatus === 'error' || restoredStatus === 'failed' ? 'failed' : 'success');
  }, []);

  const applyPlanRun = useCallback((nextRun: PlanRun) => {
    setPlanRun(nextRun);
    if (nextRun.result) {
      setResult(nextRun.result);
      setStatus('success');
    } else if (nextRun.status === 'error') {
      setError(nextRun.error ?? 'Plan run failed');
      setStatus('failed');
    } else if (nextRun.status === 'running') {
      setStatus('running');
    } else {
      setStatus('idle');
    }
  }, []);

  const startPlanRun = useCallback(async (planId: string) => {
    setError(null);
    setResult(null);
    const nextRun = await postPlanRun(planId);
    applyPlanRun(nextRun);
  }, [applyPlanRun]);

  const stepPlanRun = useCallback(async () => {
    if (!planRun) return;
    setError(null);
    const nextRun = await postPlanRunStep(planRun.planId, planRun.runId);
    applyPlanRun(nextRun);
  }, [applyPlanRun, planRun]);

  const runFullPlan = useCallback(async () => {
    if (!planRun) return;
    setError(null);
    setStatus('running');
    const nextRun = await postPlanRunFull(planRun.planId, planRun.runId);
    applyPlanRun(nextRun);
  }, [applyPlanRun, planRun]);

  const resetPlanRun = useCallback(async () => {
    if (!planRun) return;
    setError(null);
    setResult(null);
    const nextRun = await postPlanRunReset(planRun.planId, planRun.runId);
    applyPlanRun(nextRun);
  }, [applyPlanRun, planRun]);

  return (
    <ExecutionContext.Provider
      value={{
        status,
        result,
        error,
        planRun,
        triggerExecution,
        startPlanRun,
        stepPlanRun,
        runFullPlan,
        resetPlanRun,
        restoreExecution,
      }}
    >
      {children}
    </ExecutionContext.Provider>
  );
}
