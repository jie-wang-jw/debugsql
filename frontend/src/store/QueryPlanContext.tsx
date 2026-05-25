import {
  createContext,
  useCallback,
  useContext,
  useState,
  type ReactNode,
} from 'react';
import type {
  FlowNode,
  FlowNodeData,
  QueryPlanGraph,
} from '../components/query-plan/queryPlan.types';
import {
  fetchQueryPlan,
  getInitialPlan,
  updateQueryPlanNode,
} from '../services/adapters/queryPlanAdapter';

const INITIAL_GRAPH: QueryPlanGraph = getInitialPlan();

export interface QueryPlanContextValue {
  graph: QueryPlanGraph;
  selectedNodeId: string | null;
  selectedNode: FlowNode | null;
  activePlanId: string | null;
  loadPlan: (planId: string) => Promise<void>;
  refreshActivePlan: () => Promise<void>;
  onNodeSelect: (id: string) => void;
  onNodeDataUpdate: (nodeId: string, updatedData: FlowNodeData) => Promise<QueryPlanGraph | null>;
}

const QueryPlanContext = createContext<QueryPlanContextValue | null>(null);

export function useQueryPlanContext(): QueryPlanContextValue {
  const ctx = useContext(QueryPlanContext);
  if (!ctx) {
    throw new Error('useQueryPlanContext must be used inside <QueryPlanProvider>');
  }
  return ctx;
}

export function QueryPlanProvider({ children }: { children: ReactNode }) {
  const [graph, setGraph] = useState<QueryPlanGraph>(INITIAL_GRAPH);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [activePlanId, setActivePlanId] = useState<string | null>(null);

  const selectedNode: FlowNode | null = selectedNodeId
    ? (graph.nodes.find((node) => node.id === selectedNodeId) ?? null)
    : null;

  const onNodeSelect = useCallback((id: string) => {
    setSelectedNodeId((prev) => (prev === id ? null : id));
  }, []);

  const loadPlan = useCallback(async (planId: string) => {
    const nextGraph = await fetchQueryPlan(planId);
    setGraph(nextGraph);
    setActivePlanId(planId);
    setSelectedNodeId(null);
  }, []);

  const refreshActivePlan = useCallback(async () => {
    if (!activePlanId) return;
    const nextGraph = await fetchQueryPlan(activePlanId);
    setGraph(nextGraph);
  }, [activePlanId]);

  const onNodeDataUpdate = useCallback(
    async (nodeId: string, updatedData: FlowNodeData) => {
      if (activePlanId) {
        const updatedGraph = await updateQueryPlanNode(activePlanId, nodeId, updatedData);
        if (updatedGraph) {
          setGraph(updatedGraph);
          setSelectedNodeId((prev) =>
            updatedGraph.nodes.some((node) => node.id === prev) ? prev : nodeId,
          );
          return updatedGraph;
        }
      }

      setGraph((prev) => ({
        ...prev,
        nodes: prev.nodes.map((node) =>
          node.id === nodeId ? { ...node, data: updatedData } : node
        ),
      }));
      return null;
    },
    [activePlanId]
  );

  return (
    <QueryPlanContext.Provider
      value={{
        graph,
        selectedNodeId,
        selectedNode,
        activePlanId,
        loadPlan,
        refreshActivePlan,
        onNodeSelect,
        onNodeDataUpdate,
      }}
    >
      {children}
    </QueryPlanContext.Provider>
  );
}
