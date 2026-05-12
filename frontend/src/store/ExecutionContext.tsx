// ================================================
// DebugSQL – Execution Context  (Phase 5)
//
// Provides execution state + triggerExecution to all panels.
// Wraps the entire AppShell so both ChatPanel (left) and
// InspectorPanel (right) can trigger and observe execution.
//
// TODO: Replace runMockExecution with real backend API calls
// TODO: Add query cancellation via AbortController
// TODO: Persist execution history for session replay
// TODO: Stream execution step progress from backend
// ================================================

import {
  createContext,
  useContext,
  useState,
  useCallback,
  type ReactNode,
} from 'react';
import type { ExecutionStatus, ExecutionResult } from '../types/execution.types';
import { runMockExecution } from '../services/mocks/mockExecutionService';

// ---- Context shape ----

export interface ExecutionContextValue {
  /** Current pipeline status. */
  status:  ExecutionStatus;
  /** Populated on success; null otherwise. */
  result:  ExecutionResult | null;
  /** Populated on failure; null otherwise. */
  error:   string | null;
  /**
   * Kick off a mock execution for the given natural-language query.
   * Sets status → 'running', then resolves to 'success' or 'failed'.
   *
   * TODO: POST /api/execute { query, sessionId } and stream progress
   * TODO: Integrate with backend query validation before execution
   */
  triggerExecution: (query: string) => Promise<void>;
}

// ---- Context + hook ----

const ExecutionContext = createContext<ExecutionContextValue | null>(null);

export function useExecutionContext(): ExecutionContextValue {
  const ctx = useContext(ExecutionContext);
  if (!ctx) {
    throw new Error('useExecutionContext must be used inside <ExecutionProvider>');
  }
  return ctx;
}

// ---- Provider ----

export function ExecutionProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<ExecutionStatus>('idle');
  const [result, setResult] = useState<ExecutionResult | null>(null);
  const [error,  setError]  = useState<string | null>(null);

  const triggerExecution = useCallback(async (query: string) => {
    // Ignore concurrent runs
    if (!query.trim()) return;

    setStatus('running');
    setResult(null);
    setError(null);

    try {
      // TODO: Replace with: await fetch('/api/execute', { method: 'POST', body: ... })
      const execResult = await runMockExecution(query);
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
