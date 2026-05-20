// ================================================
// DebugSQL - Execution API
//
// Typed request/response models and API functions for the live backend
// execution pipeline. The active adapter calls these functions unless mock
// mode is explicitly enabled.
//
// Backend endpoints:
//   POST   /api/execute
//   GET    /api/execute/:runId/result
//   GET    /api/execute/:runId/stream
//   DELETE /api/execute/:runId
// ================================================

import { apiPost, apiGet, apiDelete } from './client';
import type { RequestOptions } from './client';
import type { ExecutionResult } from '../../types/execution.types';

export interface ExecutionRequest {
  /** The SQL string to execute, or an NL query for server-side demo execution. */
  sql: string;
  /** Active session ID used for audit logging and history. */
  sessionId: string;
  /** Optional plan ID to associate this run with a stored query plan. */
  planId?: string;
}

export interface ExecutionRunResponse {
  /** Opaque run identifier used to poll or stream results. */
  runId: string;
  status: 'queued' | 'running';
}

/**
 * Submits an execution request to the backend. The current backend returns
 * quickly with a runId; callers fetch the result with getExecutionResult().
 */
export async function postExecutionRun(
  body: ExecutionRequest,
  options?: RequestOptions,
): Promise<ExecutionRunResponse> {
  return apiPost<ExecutionRunResponse>('/execute', body, options);
}

/**
 * Fetches the final result payload for a completed execution run.
 * TODO: Replace polling with SSE/WebSocket progress updates.
 */
export async function getExecutionResult(
  runId: string,
  options?: RequestOptions,
): Promise<ExecutionResult> {
  return apiGet<ExecutionResult>(`/execute/${runId}/result`, options);
}

/**
 * Requests cancellation of a running query.
 * TODO: Wire a cancel button in ExecutionPanel to this endpoint.
 */
export async function deleteExecutionRun(
  runId: string,
  options?: RequestOptions,
): Promise<void> {
  return apiDelete<void>(`/execute/${runId}`, options);
}
