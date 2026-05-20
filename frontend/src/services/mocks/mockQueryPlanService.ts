// ================================================
// DebugSQL – Mock Query Plan Service  (Phase 7)
//
// Wraps the demo query plan generator in a service interface
// that matches the shape expected by queryPlanAdapter.ts.
// Keeping the generator in utils/ preserves its original location;
// this file is the mock-service boundary.
//
// TODO: Replace fetchMockQueryPlan with GET /api/query-plan/:planId
// TODO: Sync query plan edits to backend via PATCH endpoint
// ================================================

import type { QueryPlanGraph } from '../../components/query-plan/queryPlan.types';
import { generateDemoQueryPlan } from '../../utils/mockQueryPlanGenerator';

/** Simulated network delay so the mock feels realistic. */
const MOCK_LATENCY_MS = 120;

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Returns the initial query plan graph synchronously.
 * Used by QueryPlanProvider to avoid an async initial state.
 *
 * TODO: Replace with a real fetch on session restore once backend is ready
 */
export function getInitialQueryPlan(): QueryPlanGraph {
  return generateDemoQueryPlan();
}

/**
 * Simulates fetching a query plan graph by ID from the backend.
 *
 * Currently always returns the demo plan regardless of planId.
 *
 * TODO: Replace mock adapter with GET /api/query-plan/:planId
 * TODO: Map the planId returned from the chat API to the correct plan graph
 */
export async function fetchMockQueryPlan(_planId: string): Promise<QueryPlanGraph> {
  await sleep(MOCK_LATENCY_MS);
  return generateDemoQueryPlan();
}

/**
 * No-op stub for node update persistence.
 * In the real backend this would call PATCH /api/query-plan/:planId/nodes/:nodeId.
 *
 * TODO: Sync query plan edits to backend
 * TODO: Trigger query-regeneration pipeline after applying node changes
 */
export async function saveMockNodeUpdate(
  _planId: string,
  _nodeId: string,
): Promise<void> {
  // No-op — local state is managed by QueryPlanContext
}
