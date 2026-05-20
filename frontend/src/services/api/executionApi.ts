// ================================================
// DebugSQL – Execution API  (Phase 7)
//
// Typed request/response models and API functions for the execution pipeline.
// These functions are NOT called yet — the mock is used via executionAdapter.ts.
//
// Target endpoints:
//   POST /api/execute               → submit a run
//   GET  /api/execute/:runId/result → fetch completed results
//   GET  /api/execute/:runId/stream → live SSE progress stream
//   DELETE /api/execute/:runId      → cancel a running query
// ================================================

import { apiPost, apiGet, apiDelete } from './client';
import type { RequestOptions } from './client';
import type { ExecutionResult } from '../../types/execution.types';

// ---- Request types ----

export interface ExecutionRequest {
  /** The SQL string to execute (or a natural-language query for server-side parsing). */
  sql:        string;
  /** Active session ID — used for audit logging and history. */
  sessionId:  string;
  /** Optional plan ID to associate this run with a stored query plan. */
  planId?:    string;
}

// ---- Response types ----

/** Immediate response after submitting an execution request. */
export interface ExecutionRunResponse {
  /** Opaque run identifier — used to poll or stream results. */
  runId:  string;
  status: 'queued' | 'running';
}

// ---- API functions ----

/**
 * POST /api/execute
 *
 * Submits a SQL execution request to the backend.
 * Returns a runId immediately; the caller should then stream or poll
 * for the final result via getExecutionResult().
 *
 * TODO: Replace mock adapter with real backend API
 * TODO: Add query cancellation support (AbortController)
 * TODO: Connect database connection pooling configuration
 */
export async function postExecutionRun(
  body:     ExecutionRequest,
  options?: RequestOptions,
): Promise<ExecutionRunResponse> {
  return apiPost<ExecutionRunResponse>('/execute', body, options);
}

/**
 * GET /api/execute/:runId/result
 *
 * Fetches the final result payload for a completed execution run.
 * Use after polling or receiving a completion event over SSE.
 *
 * TODO: Connect websocket/live execution updates instead of polling
 * TODO: Stream result rows progressively from backend
 */
export async function getExecutionResult(
  runId:    string,
  options?: RequestOptions,
): Promise<ExecutionResult> {
  return apiGet<ExecutionResult>(`/execute/${runId}/result`, options);
}

/**
 * DELETE /api/execute/:runId
 *
 * Requests cancellation of a running query.
 *
 * TODO: Wire up cancel button in ExecutionPanel to this endpoint
 */
export async function deleteExecutionRun(
  runId:    string,
  options?: RequestOptions,
): Promise<void> {
  return apiDelete<void>(`/execute/${runId}`, options);
}
