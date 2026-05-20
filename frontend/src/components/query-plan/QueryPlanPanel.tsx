import { FiCpu, FiRefreshCw, FiMaximize2 } from 'react-icons/fi';
import { StatusBadge } from '../ui/StatusBadge';
import { QueryPlanFlow } from './QueryPlanFlow';
import { useQueryPlanContext } from '../../store/QueryPlanContext';
import './queryPlan.styles.css';

/**
 * QueryPlanPanel – Top-right panel housing the React Flow visualization.
 *
 * Phase 4: selectedNodeId and onNodeSelect are now sourced from
 * QueryPlanContext so the InspectorPanel can react to selection changes.
 *
 * TODO: Load query plan graph from backend API (GET /api/query-plan/:planId)
 * TODO: Sync graph with assistant-generated query plans from chat panel
 */
export function QueryPlanPanel() {
  const { graph, selectedNodeId, onNodeSelect } = useQueryPlanContext();

  return (
    <div className="qplan">
      <QueryPlanPanelHeader
        queryLabel={graph.queryLabel}
        nodeCount={graph.nodes.length}
        totalCost={graph.totalCost}
        selectedNodeId={selectedNodeId}
      />

      {/* React Flow canvas fills remaining height */}
      <div className="qplan__canvas">
        <QueryPlanFlow
          graph={graph}
          selectedNodeId={selectedNodeId}
          onNodeSelect={onNodeSelect}
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
            <span className="qplan__query-prefix">Question:</span> {queryLabel}
          </span>
        </div>
      </div>

      <div className="qplan__header-right">
        {selectedNodeId && (
          <StatusBadge label={`node: ${selectedNodeId}`} variant="blue" dot />
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
