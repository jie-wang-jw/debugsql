// ================================================
// DebugSQL – Query Plan API  (Phase 7)
//
// Typed request/response models and API functions for query plan endpoints.
// These functions are NOT called yet — the mock is used via queryPlanAdapter.ts.
//
// Target endpoints:
//   GET   /api/query-plan/:planId
//   PATCH /api/query-plan/:planId/nodes/:nodeId
//   POST  /api/query-plan/:planId/snapshot
// ================================================

import { apiGet, apiPatch, apiPost } from './client';
import type { RequestOptions } from './client';
import type { QueryPlanGraph } from '../../components/query-plan/queryPlan.types';
import type { FlowNodeData }   from '../../components/query-plan/queryPlan.types';

// ---- Request types ----

/** Payload sent when persisting a node edit from the Inspector panel. */
export interface NodeUpdateRequest {
  nodeId: string;
  data:   FlowNodeData;
}

/** Payload for saving a named plan snapshot. */
export interface PlanSnapshotRequest {
  label?: string;
}

// ---- Response types ----

/** Lightweight plan snapshot metadata (for history list). */
export interface PlanSnapshotMeta {
  snapshotId: string;
  label:      string;
  createdAt:  string;
}

// ---- API functions ----

/**
 * GET /api/query-plan/:planId
 *
 * Fetches the full query plan graph for the given plan ID.
 * The response shape matches QueryPlanGraph for direct rendering
 * in QueryPlanFlow — no transformation needed.
 *
 * TODO: Replace mock adapter with real backend API
 * TODO: Trigger on every AI response that returns a new planId
 */
export async function getQueryPlan(
  planId:   string,
  options?: RequestOptions,
): Promise<QueryPlanGraph> {
  return apiGet<QueryPlanGraph>(`/query-plan/${planId}`, options);
}

/**
 * PATCH /api/query-plan/:planId/nodes/:nodeId
 *
 * Persists a node edit from the Inspector panel to the backend.
 * The backend may trigger query re-planning after applying the change.
 *
 * TODO: Sync query plan edits to backend
 * TODO: Trigger query-regeneration pipeline after applying node changes
 */
export async function patchQueryPlanNode(
  planId:   string,
  nodeId:   string,
  body:     NodeUpdateRequest,
  options?: RequestOptions,
): Promise<void> {
  return apiPatch<void>(`/query-plan/${planId}/nodes/${nodeId}`, body, options);
}

/**
 * POST /api/query-plan/:planId/snapshot
 *
 * Saves the current plan state as a named snapshot for history replay.
 *
 * TODO: Persist query history — allow users to revisit previous plans
 */
export async function postPlanSnapshot(
  planId:   string,
  body:     PlanSnapshotRequest,
  options?: RequestOptions,
): Promise<PlanSnapshotMeta> {
  return apiPost<PlanSnapshotMeta>(`/query-plan/${planId}/snapshot`, body, options);
}
