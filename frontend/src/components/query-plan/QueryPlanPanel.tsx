import { useCallback, useState } from 'react';
import { FiCpu, FiRefreshCw, FiMaximize2, FiMinimize2 } from 'react-icons/fi';
import { StatusBadge } from '../ui/StatusBadge';
import { QueryPlanFlow } from './QueryPlanFlow';
import { useQueryPlanContext } from '../../store/QueryPlanContext';
import './queryPlan.styles.css';

/**
 * Top-right panel that renders the backend-provided query plan graph.
 * Node selection is shared through QueryPlanContext so InspectorPanel can
 * inspect and edit the selected node.
 */
export function QueryPlanPanel() {
  const { graph, selectedNodeId, activePlanId, loadPlan, onNodeSelect, onNodeDeselect } =
    useQueryPlanContext();
  const [isExpanded, setIsExpanded] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const handleRefresh = useCallback(async () => {
    if (!activePlanId || isRefreshing) {
      return;
    }

    setIsRefreshing(true);
    try {
      await loadPlan(activePlanId);
    } finally {
      setIsRefreshing(false);
    }
  }, [activePlanId, isRefreshing, loadPlan]);

  return (
    <div className={`qplan ${isExpanded ? 'qplan--expanded' : ''}`}>
      <QueryPlanPanelHeader
        queryLabel={graph.queryLabel}
        nodeCount={graph.nodes.length}
        totalCost={graph.totalCost}
        selectedNodeId={selectedNodeId}
        hasActivePlan={Boolean(activePlanId)}
        isRefreshing={isRefreshing}
        isExpanded={isExpanded}
        onRefresh={handleRefresh}
        onToggleExpanded={() => setIsExpanded((prev) => !prev)}
      />

      <div className="qplan__canvas">
        {graph.nodes.length > 0 ? (
          <QueryPlanFlow
            graph={graph}
            selectedNodeId={selectedNodeId}
            onNodeSelect={onNodeSelect}
            onNodeDeselect={onNodeDeselect}
          />
        ) : (
          <div className="qplan__empty">
            <p className="qplan__empty-title">No query plan yet</p>
            <p className="qplan__empty-copy">
              Enter a natural language question in the chat to generate an editable plan.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

interface HeaderProps {
  queryLabel: string;
  nodeCount: number;
  totalCost: number;
  selectedNodeId: string | null;
  hasActivePlan: boolean;
  isRefreshing: boolean;
  isExpanded: boolean;
  onRefresh: () => void;
  onToggleExpanded: () => void;
}

function QueryPlanPanelHeader({
  queryLabel,
  nodeCount,
  totalCost,
  selectedNodeId,
  hasActivePlan,
  isRefreshing,
  isExpanded,
  onRefresh,
  onToggleExpanded,
}: HeaderProps) {
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
        <button
          className={`qplan__icon-btn ${isRefreshing ? 'qplan__icon-btn--spinning' : ''}`}
          type="button"
          aria-label="Refresh plan"
          title={hasActivePlan ? 'Refresh current plan from backend' : 'No active backend plan to refresh'}
          disabled={!hasActivePlan || isRefreshing}
          onClick={onRefresh}
        >
          <FiRefreshCw size={12} />
        </button>
        <button
          className={`qplan__icon-btn ${isExpanded ? 'qplan__icon-btn--active' : ''}`}
          type="button"
          aria-label={isExpanded ? 'Exit expanded view' : 'Expand view'}
          aria-pressed={isExpanded}
          title={isExpanded ? 'Exit expanded view' : 'Expand query plan view'}
          onClick={onToggleExpanded}
        >
          {isExpanded ? <FiMinimize2 size={12} /> : <FiMaximize2 size={12} />}
        </button>
      </div>
    </div>
  );
}
