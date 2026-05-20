// ================================================
// DebugSQL - Query Plan Adapter
//
// Single injection point for query plan fetch and node-update persistence.
// Components and contexts import only from this file.
//
// Default mode calls the real backend API. Set VITE_USE_MOCK_SERVICES=true
// only when intentionally running isolated frontend mock services.
//
// TODO: Connect websocket/live execution updates after node changes.
// TODO: Add persisted session restore for the initial plan.
// ================================================

import type { QueryPlanGraph } from '../../components/query-plan/queryPlan.types';
import type { FlowNodeData } from '../../components/query-plan/queryPlan.types';
import {
  getInitialQueryPlan,
  fetchMockQueryPlan,
  saveMockNodeUpdate,
} from '../mocks/mockQueryPlanService';

const USE_MOCK_SERVICES = import.meta.env.VITE_USE_MOCK_SERVICES === 'true';

/**
 * Returns the initial placeholder plan synchronously for app bootstrap.
 * Real backend plans are loaded later via fetchQueryPlan(planId).
 */
export function getInitialPlan(): QueryPlanGraph {
  return getInitialQueryPlan();
}

/**
 * Fetches a query plan graph by plan ID.
 * Called after the chat API returns a backend-generated planId.
 */
export async function fetchQueryPlan(planId: string): Promise<QueryPlanGraph> {
  if (USE_MOCK_SERVICES) {
    return fetchMockQueryPlan(planId);
  }

  const { getQueryPlan } = await import('../api/queryPlanApi');
  return getQueryPlan(planId);
}

/**
 * Persists a node data edit.
 * In real-backend mode this PATCHes the node to the backend; in mock mode it
 * intentionally does not persist beyond local frontend state.
 */
export async function updateQueryPlanNode(
  planId: string,
  nodeId: string,
  _data: FlowNodeData,
): Promise<void> {
  if (USE_MOCK_SERVICES) {
    return saveMockNodeUpdate(planId, nodeId);
  }

  const { patchQueryPlanNode } = await import('../api/queryPlanApi');
  return patchQueryPlanNode(planId, nodeId, { nodeId, data: _data });
}
