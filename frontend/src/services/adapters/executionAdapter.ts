// ================================================
// DebugSQL – Execution Adapter  (Phase 7)
//
// Single injection point for the query execution pipeline.
// ExecutionContext imports ONLY from this file, not from the mock service.
//
// To connect the real backend:
//   1. Set VITE_USE_MOCK_SERVICES=false in your .env
//   2. Uncomment the real API call below
//   3. Remove the mock branch
//
// TODO: Replace mock adapter with real backend API
// TODO: Add query cancellation support (AbortController)
// TODO: Connect websocket/live execution updates for streaming progress
// TODO: Validate SQL against backend schema before sending
// ================================================

import type { ExecutionResult } from '../../types/execution.types';
import { runMockExecution }     from '../mocks/mockExecutionService';

// ---------------------------------------------------------------------------
// Feature flag
// ---------------------------------------------------------------------------

const USE_MOCK_SERVICES = import.meta.env.VITE_USE_MOCK_SERVICES === 'true';

// ---------------------------------------------------------------------------
// Adapter
// ---------------------------------------------------------------------------

/**
 * Executes a query and returns the full result payload.
 *
 * Currently routes to the mock execution service.
 * When the backend is ready, flip USE_MOCK_SERVICES and uncomment the real call.
 *
 * @param query  Natural-language or SQL query string.
 * @param signal Optional AbortSignal for cancellation.
 *
 * TODO: Replace mock adapter with postExecutionRun() + getExecutionResult()
 * TODO: Add query cancellation support (AbortController)
 * TODO: Stream execution step progress from backend (SSE / WebSocket)
 */
export async function executeQuery(
  query:   string,
  _signal?: AbortSignal,
): Promise<ExecutionResult> {
  if (USE_MOCK_SERVICES) {
    return runMockExecution(query);
  }

  const { postExecutionRun, getExecutionResult } = await import('../api/executionApi');
  const { runId } = await postExecutionRun(
    { sql: query, sessionId: 'dev-session' },
    { signal: _signal },
  );
  return getExecutionResult(runId, { signal: _signal });
}
