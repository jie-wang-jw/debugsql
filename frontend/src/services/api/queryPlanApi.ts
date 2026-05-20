// ================================================
// DebugSQL - Query Plan API
//
// Typed request/response models and API functions for the live backend query
// plan endpoints. The active adapter calls these functions unless mock mode is
// explicitly enabled.
//
// Backend endpoints:
//   GET   /api/query-plan/:planId
//   PATCH /api/query-plan/:planId/nodes/:nodeId
//   POST  /api/query-plan/:planId/snapshot
// ================================================

import { apiGet, apiPatch, apiPost } from './client';
import type { RequestOptions } from './client';
import type { QueryPlanGraph } from '../../components/query-plan/queryPlan.types';
import type { FlowNodeData } from '../../components/query-plan/queryPlan.types';

export interface NodeUpdateRequest {
  nodeId: string;
  data: FlowNodeData;
}

export interface PlanSnapshotRequest {
  label?: string;
}

export interface PlanSnapshotMeta {
  snapshotId: string;
  label: string;
  createdAt: string;
}

/** Fetches the full query plan graph for the given plan ID. */
export async function getQueryPlan(
  planId: string,
  options?: RequestOptions,
): Promise<QueryPlanGraph> {
  return apiGet<QueryPlanGraph>(`/query-plan/${planId}`, options);
}

/**
 * Persists a node edit from the Inspector panel to the backend. The current
 * backend demo provider updates the in-memory plan and executable SQL.
 */
export async function patchQueryPlanNode(
  planId: string,
  nodeId: string,
  body: NodeUpdateRequest,
  options?: RequestOptions,
): Promise<void> {
  return apiPatch<void>(`/query-plan/${planId}/nodes/${nodeId}`, body, options);
}

/**
 * Saves the current plan state as a named snapshot.
 * TODO: Implement durable history storage in the backend.
 */
export async function postPlanSnapshot(
  planId: string,
  body: PlanSnapshotRequest,
  options?: RequestOptions,
): Promise<PlanSnapshotMeta> {
  return apiPost<PlanSnapshotMeta>(`/query-plan/${planId}/snapshot`, body, options);
}
