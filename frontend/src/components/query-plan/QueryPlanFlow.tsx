import { useCallback, useEffect, useMemo } from 'react';
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

// React Flow base styles; overridden in queryPlan.styles.css.
import 'reactflow/dist/style.css';

import { IntentNode } from './nodes/IntentNode';
import { OperationNode } from './nodes/OperationNode';
import { DataNode } from './nodes/DataNode';
import type { QueryPlanGraph } from './queryPlan.types';

const NODE_TYPES: NodeTypes = {
  intent: IntentNode,
  operation: OperationNode,
  data: DataNode,
};

function getMinimapColor(node: Node): string {
  const map: Record<string, string> = {
    intent: '#6b8fbf',
    operation: '#8878c0',
    data: '#67a07a',
  };
  return map[node.type ?? ''] ?? '#3a3a3f';
}

export interface QueryPlanFlowProps {
  graph: QueryPlanGraph;
  /** Currently selected node ID; synced into React Flow's internal selection. */
  selectedNodeId: string | null;
  /** Fired when the user clicks a node. */
  onNodeSelect: (id: string) => void;
}

function QueryPlanFlowInner({ graph, selectedNodeId, onNodeSelect }: QueryPlanFlowProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState(graph.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(graph.edges);
  const nodeTypes = useMemo(() => NODE_TYPES, []);

  useEffect(() => {
    setNodes(graph.nodes.map((node) => ({
      ...node,
      selected: node.id === selectedNodeId,
    })));
    setEdges(graph.edges);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedNodeId, graph.nodes, graph.edges]);

  const handleNodeClick: NodeMouseHandler = useCallback(
    (_, node) => {
      onNodeSelect(node.id);
    },
    [onNodeSelect],
  );

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      nodeTypes={nodeTypes}
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
        color="rgba(255,255,255,0.03)"
        gap={24}
        size={1}
      />
      <Controls showInteractive={false} className="qplan-controls" />
      <MiniMap
        nodeColor={getMinimapColor}
        maskColor="rgba(0,0,0,0.70)"
        className="qplan-minimap"
        pannable
        zoomable
      />
    </ReactFlow>
  );
}

export function QueryPlanFlow(props: QueryPlanFlowProps) {
  return (
    <ReactFlowProvider>
      <QueryPlanFlowInner {...props} />
    </ReactFlowProvider>
  );
}
