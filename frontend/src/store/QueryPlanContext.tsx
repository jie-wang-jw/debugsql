// ================================================
// DebugSQL – QueryPlan shared context (Phase 4)
//
// Lifts selectedNodeId + graph state above AppShell so both
// QueryPlanPanel (graph canvas) and InspectorPanel (editor) share
// the same source of truth without prop-drilling.
// ================================================

import {
  createContext,
  useContext,
  useState,
  useCallback,
  type ReactNode,
} from 'react';
import type {
  FlowNode,
  FlowNodeData,
  QueryPlanGraph,
} from '../components/query-plan/queryPlan.types';
import { getInitialPlan } from '../services/adapters/queryPlanAdapter';

// TODO: Replace INITIAL_GRAPH with a real fetch (GET /api/query-plan/:planId)
// TODO: Persist graph state across sessions via backend storage
const INITIAL_GRAPH: QueryPlanGraph = getInitialPlan();

// ---- Context shape ----

export interface QueryPlanContextValue {
  /** Full query plan graph (nodes + edges). */
  graph: QueryPlanGraph;
  /** ID of the currently selected node, or null. */
  selectedNodeId: string | null;
  /** Convenience — the full FlowNode for the selected ID (or null). */
  selectedNode: FlowNode | null;
  /** Toggle selection: clicking the same node deselects it. */
  onNodeSelect: (id: string) => void;
  /**
   * Merges `updatedData` into the matching graph node.
   * Triggers a re-render of the React Flow canvas so visual changes are immediate.
   *
   * TODO: PATCH /api/query-plan/:planId/nodes/:nodeId — sync edits to backend
   * TODO: Trigger query-regeneration pipeline after applying node changes
   */
  onNodeDataUpdate: (nodeId: string, updatedData: FlowNodeData) => void;
}

// ---- Context + hook ----

const QueryPlanContext = createContext<QueryPlanContextValue | null>(null);

export function useQueryPlanContext(): QueryPlanContextValue {
  const ctx = useContext(QueryPlanContext);
  if (!ctx) {
    throw new Error('useQueryPlanContext must be used inside <QueryPlanProvider>');
  }
  return ctx;
}

// ---- Provider ----

export function QueryPlanProvider({ children }: { children: ReactNode }) {
  const [graph, setGraph] = useState<QueryPlanGraph>(INITIAL_GRAPH);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  const selectedNode: FlowNode | null =
    selectedNodeId
      ? (graph.nodes.find((n) => n.id === selectedNodeId) ?? null)
      : null;

  const onNodeSelect = useCallback((id: string) => {
    setSelectedNodeId((prev) => (prev === id ? null : id));
  }, []);

  const onNodeDataUpdate = useCallback(
    (nodeId: string, updatedData: FlowNodeData) => {
      // TODO: PATCH /api/query-plan/:planId/nodes/:nodeId — sync node edits to backend
      // TODO: Trigger query regeneration pipeline after node data changes
      // TODO: Persist updated query plan state (POST /api/query-plan/:planId/snapshot)
      setGraph((prev) => ({
        ...prev,
        nodes: prev.nodes.map((n) =>
          n.id === nodeId ? { ...n, data: updatedData } : n
        ),
      }));
    },
    []
  );

  return (
    <QueryPlanContext.Provider
      value={{ graph, selectedNodeId, selectedNode, onNodeSelect, onNodeDataUpdate }}
    >
      {children}
    </QueryPlanContext.Provider>
  );
}
