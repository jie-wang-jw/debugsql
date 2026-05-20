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
import type { ExecutionStatus, ExecutionResult } from '../types/execution.types';
import { executeQuery } from '../services/adapters/executionAdapter';

export interface ExecutionContextValue {
  /** Current pipeline status. */
  status: ExecutionStatus;
  /** Populated on success; null otherwise. */
  result: ExecutionResult | null;
  /** Populated on failure; null otherwise. */
  error: string | null;
  /**
   * Kick off backend execution for the given query/plan.
   * Sets status to "running", then resolves to "success" or "failed".
   */
  triggerExecution: (query: string, planId?: string | null) => Promise<void>;
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

  return (
    <ExecutionContext.Provider value={{ status, result, error, triggerExecution }}>
      {children}
    </ExecutionContext.Provider>
  );
}
