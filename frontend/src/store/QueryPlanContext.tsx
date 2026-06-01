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
  mergeQueryPlanNodes,
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
  onNodeDeselect: () => void;
  onNodeDataUpdate: (nodeId: string, updatedData: FlowNodeData) => Promise<QueryPlanGraph | null>;
  onSelectedNodeMergeWithNext: () => Promise<QueryPlanGraph | null>;
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
    setSelectedNodeId(id);
  }, []);

  const onNodeDeselect = useCallback(() => {
    setSelectedNodeId(null);
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

  const onSelectedNodeMergeWithNext = useCallback(async () => {
    if (!activePlanId || !selectedNodeId) return null;
    const nextOperationId = graph.edges
      .filter((edge) => edge.source === selectedNodeId)
      .map((edge) => edge.target)
      .find((targetId) => graph.nodes.find((node) => node.id === targetId)?.data.kind === 'operation');
    if (!nextOperationId) return null;

    const updatedGraph = await mergeQueryPlanNodes(activePlanId, [selectedNodeId, nextOperationId]);
    if (updatedGraph) {
      setGraph(updatedGraph);
      setSelectedNodeId((prev) =>
        updatedGraph.nodes.some((node) => node.id === prev) ? prev : selectedNodeId,
      );
      return updatedGraph;
    }
    return null;
  }, [activePlanId, graph.edges, graph.nodes, selectedNodeId]);

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
        onNodeDeselect,
        onNodeDataUpdate,
        onSelectedNodeMergeWithNext,
      }}
    >
      {children}
    </QueryPlanContext.Provider>
  );
}
