// ================================================
// DebugSQL – Query Plan Adapter  (Phase 7)
//
// Single injection point for query plan fetch and node-update persistence.
// Components and contexts import ONLY from this file.
//
// To connect the real backend:
//   1. Set VITE_USE_MOCK_SERVICES=false in your .env
//   2. Uncomment the real API calls below
//   3. Remove the mock branches
//
// TODO: Replace mock adapter with real backend API
// TODO: Sync query plan edits to backend
// TODO: Connect websocket/live execution updates after node changes
// ================================================

import type { QueryPlanGraph } from '../../components/query-plan/queryPlan.types';
import type { FlowNodeData }   from '../../components/query-plan/queryPlan.types';
import {
  getInitialQueryPlan,
  fetchMockQueryPlan,
  saveMockNodeUpdate,
} from '../mocks/mockQueryPlanService';

// ---------------------------------------------------------------------------
// Feature flag
// ---------------------------------------------------------------------------

const USE_MOCK_SERVICES = import.meta.env.VITE_USE_MOCK_SERVICES === 'true';

// ---------------------------------------------------------------------------
// Adapter
// ---------------------------------------------------------------------------

/**
 * Returns the initial query plan synchronously for app bootstrap.
 * Used by QueryPlanProvider as the useState initial value.
 *
 * TODO: Replace with async session-restore fetch once backend is ready
 */
export function getInitialPlan(): QueryPlanGraph {
  return getInitialQueryPlan();
}

/**
 * Fetches a query plan graph by plan ID.
 * Called after the chat API returns a new planId.
 *
 * TODO: Replace mock adapter with getQueryPlan() from queryPlanApi.ts
 * TODO: Trigger on every AI response that returns a new planId
 */
export async function fetchQueryPlan(planId: string): Promise<QueryPlanGraph> {
  if (USE_MOCK_SERVICES) {
    return fetchMockQueryPlan(planId);
  }

  const { getQueryPlan } = await import('../api/queryPlanApi');
  return getQueryPlan(planId);
}

/**
 * Persists a node data edit to the backend.
 * Called by QueryPlanContext after the Inspector applies changes.
 *
 * Currently a no-op — local state is managed by QueryPlanContext.
 *
 * TODO: Sync query plan edits to backend via patchQueryPlanNode()
 * TODO: Trigger query-regeneration pipeline after applying node changes
 */
export async function updateQueryPlanNode(
  planId: string,
  nodeId: string,
  _data:  FlowNodeData,
): Promise<void> {
  if (USE_MOCK_SERVICES) {
    return saveMockNodeUpdate(planId, nodeId);
  }

  const { patchQueryPlanNode } = await import('../api/queryPlanApi');
  return patchQueryPlanNode(planId, nodeId, { nodeId, data: _data });
}
