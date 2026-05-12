import { useState, useCallback } from 'react';
import { FiCpu, FiRefreshCw, FiMaximize2 } from 'react-icons/fi';
import { StatusBadge } from '../ui/StatusBadge';
import { QueryPlanFlow } from './QueryPlanFlow';
import { generateDemoQueryPlan } from '../../utils/mockQueryPlanGenerator';
import './queryPlan.styles.css';

// TODO: Load query plan graph from backend API (GET /api/query-plan/:planId)
// TODO: Sync graph with assistant-generated query plans from chat panel
const DEMO_GRAPH = generateDemoQueryPlan();

/**
 * QueryPlanPanel – Top-right panel housing the React Flow visualization.
 *
 * Replaces the Phase 1 static tree placeholder.
 * Manages selected-node state that will be forwarded to the Inspector in Phase 4.
 */
export function QueryPlanPanel() {
  // TODO: Lift selectedNodeId into shared context so InspectorPanel can react
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  const handleNodeSelect = useCallback((id: string) => {
    setSelectedNodeId((prev) => (prev === id ? null : id));
  }, []);

  return (
    <div className="qplan">
      <QueryPlanPanelHeader
        queryLabel={DEMO_GRAPH.queryLabel}
        nodeCount={DEMO_GRAPH.nodes.length}
        totalCost={DEMO_GRAPH.totalCost}
        selectedNodeId={selectedNodeId}
      />

      {/* React Flow canvas fills remaining height */}
      <div className="qplan__canvas">
        <QueryPlanFlow
          graph={DEMO_GRAPH}
          selectedNodeId={selectedNodeId}
          onNodeSelect={handleNodeSelect}
        />
      </div>
    </div>
  );
}

/* ---- Header ---- */
interface HeaderProps {
  queryLabel: string;
  nodeCount: number;
  totalCost: number;
  selectedNodeId: string | null;
}

function QueryPlanPanelHeader({ queryLabel, nodeCount, totalCost, selectedNodeId }: HeaderProps) {
  return (
    <div className="qplan__header">
      <div className="qplan__header-left">
        <div className="qplan__header-icon">
          <FiCpu size={13} />
        </div>
        <div>
          <span className="qplan__title">Query Plan</span>
          <span className="qplan__query-preview" title={queryLabel}>
            {queryLabel}
          </span>
        </div>
      </div>

      <div className="qplan__header-right">
        {selectedNodeId && (
          <StatusBadge label={`selected: ${selectedNodeId}`} variant="blue" />
        )}
        <StatusBadge label={`${nodeCount} nodes`} variant="gray" />
        <StatusBadge label={`cost ${totalCost.toFixed(1)}`} variant="orange" />
        <button className="qplan__icon-btn" aria-label="Refresh plan" title="Refresh plan">
          <FiRefreshCw size={12} />
        </button>
        <button className="qplan__icon-btn" aria-label="Expand view" title="Expand view">
          <FiMaximize2 size={12} />
        </button>
      </div>
    </div>
  );
}
