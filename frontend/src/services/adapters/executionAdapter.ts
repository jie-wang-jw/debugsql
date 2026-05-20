// ================================================
// DebugSQL - Execution Adapter
//
// Single injection point for the query execution pipeline.
// ExecutionContext imports only from this file.
//
// Default mode calls the real backend API. Set VITE_USE_MOCK_SERVICES=true
// only when intentionally running isolated frontend mock services.
//
// TODO: Add query cancellation support with AbortController.
// TODO: Connect websocket/live execution updates for streaming progress.
// TODO: Replace backend demo execution with real SQLite benchmark execution.
// ================================================

import type { ExecutionResult } from '../../types/execution.types';
import { runMockExecution } from '../mocks/mockExecutionService';

const USE_MOCK_SERVICES = import.meta.env.VITE_USE_MOCK_SERVICES === 'true';

/**
 * Executes a query and returns the full result payload.
 *
 * Real-backend mode submits a run, then fetches the completed result. The mock
 * branch is kept only for frontend-only development and visual testing.
 */
export async function executeQuery(
  query: string,
  planId?: string,
  _signal?: AbortSignal,
): Promise<ExecutionResult> {
  if (USE_MOCK_SERVICES) {
    return runMockExecution(query);
  }

  const { postExecutionRun, getExecutionResult } = await import('../api/executionApi');
  const { runId } = await postExecutionRun(
    { sql: query, sessionId: 'dev-session', planId },
    { signal: _signal },
  );
  return getExecutionResult(runId, { signal: _signal });
}
