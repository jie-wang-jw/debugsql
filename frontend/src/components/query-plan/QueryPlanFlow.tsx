import { useCallback } from 'react';
import ReactFlow, {
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type NodeTypes,
  type NodeMouseHandler,
  ReactFlowProvider,
  type Node,
} from 'reactflow';

// React Flow base styles — overridden in queryPlan.styles.css
import 'reactflow/dist/style.css';

import { IntentNode }    from './nodes/IntentNode';
import { OperationNode } from './nodes/OperationNode';
import { DataNode }      from './nodes/DataNode';
import type { QueryPlanGraph } from './queryPlan.types';

/**
 * nodeTypes MUST be defined outside the component (module scope) to maintain
 * a stable reference across renders and avoid React Flow's nodeTypes warning.
 */
const NODE_TYPES: NodeTypes = {
  intent:    IntentNode,
  operation: OperationNode,
  data:      DataNode,
};

/** Derive minimap node dot colour from its type string. */
function getMinimapColor(node: Node): string {
  const map: Record<string, string> = {
    intent:    '#3b82f6',
    operation: '#6366f1',
    data:      '#10b981',
  };
  return map[node.type ?? ''] ?? '#444466';
}

export interface QueryPlanFlowProps {
  graph: QueryPlanGraph;
  /**
   * Currently selected node ID passed down from QueryPlanPanel.
   * TODO: Forward to InspectorPanel via shared context (Phase 4)
   */
  selectedNodeId: string | null;
  /** Fired when the user clicks a node. */
  onNodeSelect: (id: string) => void;
}

/**
 * Inner canvas — must live inside ReactFlowProvider.
 *
 * TODO: Load query plan graph from backend API instead of static mock
 * TODO: Enable real query execution pipeline visualization with step-by-step replay
 */
function QueryPlanFlowInner({ graph, onNodeSelect }: QueryPlanFlowProps) {
  const [nodes, , onNodesChange] = useNodesState(graph.nodes);
  const [edges, , onEdgesChange] = useEdgesState(graph.edges);

  const handleNodeClick: NodeMouseHandler = useCallback(
    (_, node) => {
      // TODO: Connect selected node state to Inspector panel (Phase 4)
      onNodeSelect(node.id);
    },
    [onNodeSelect]
  );

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      nodeTypes={NODE_TYPES}
      onNodeClick={handleNodeClick}
      fitView
      fitViewOptions={{ padding: 0.18, minZoom: 0.35, maxZoom: 1 }}
      minZoom={0.2}
      maxZoom={2}
      deleteKeyCode={null}
      selectionKeyCode={null}
      multiSelectionKeyCode={null}
      proOptions={{ hideAttribution: true }}
      className="qplan-flow"
    >
      <Background
        variant={BackgroundVariant.Dots}
        color="rgba(255,255,255,0.04)"
        gap={22}
        size={1.2}
      />
      <Controls showInteractive={false} className="qplan-controls" />
      <MiniMap
        nodeColor={getMinimapColor}
        maskColor="rgba(0,0,5,0.65)"
        className="qplan-minimap"
        pannable
        zoomable
      />
    </ReactFlow>
  );
}

/** Public wrapper — provides ReactFlowProvider context. */
export function QueryPlanFlow(props: QueryPlanFlowProps) {
  return (
    <ReactFlowProvider>
      <QueryPlanFlowInner {...props} />
    </ReactFlowProvider>
  );
}
