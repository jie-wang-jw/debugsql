import { useCallback, useState } from 'react';
import { FiCpu, FiRefreshCw, FiMaximize2, FiMinimize2, FiAlertCircle } from 'react-icons/fi';
import { StatusBadge } from '../ui/StatusBadge';
import { SkeletonLoader } from '../ui/SkeletonLoader';
import { QueryPlanFlow } from './QueryPlanFlow';
import { useQueryPlanContext } from '../../store/QueryPlanContext';
import './queryPlan.styles.css';

/**
 * Top-right panel that renders the backend-provided query plan graph.
 * Node selection is shared through QueryPlanContext so InspectorPanel can
 * inspect and edit the selected node.
 */
export function QueryPlanPanel() {
  const {
    graph,
    selectedNodeId,
    activePlanId,
    planLoadStatus,
    planLoadError,
    loadPlan,
    retryLoadPlan,
    onNodeSelect,
    onNodeDeselect,
  } = useQueryPlanContext();
  const [isExpanded, setIsExpanded] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const isLoading = planLoadStatus === 'loading' || isRefreshing;

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

  const handleRetry = useCallback(async () => {
    await retryLoadPlan();
  }, [retryLoadPlan]);

  return (
    <div className={`qplan ${isExpanded ? 'qplan--expanded' : ''}`}>
      <QueryPlanPanelHeader
        queryLabel={graph.queryLabel}
        nodeCount={graph.nodes.length}
        totalCost={graph.totalCost}
        selectedNodeId={selectedNodeId}
        hasActivePlan={Boolean(activePlanId)}
        isRefreshing={isLoading}
        isExpanded={isExpanded}
        onRefresh={handleRefresh}
        onToggleExpanded={() => setIsExpanded((prev) => !prev)}
      />

      <div className="qplan__canvas">
        {isLoading ? (
          <div className="qplan__loading" role="status" aria-live="polite" aria-busy="true">
            <SkeletonLoader
              className="qplan__loading-skeleton"
              lines={[
                { width: 'medium', size: 'lg' },
                { width: 'long' },
                { width: 'long' },
                { width: 'short' },
              ]}
            />
            <p className="qplan__loading-text">Loading query plan…</p>
          </div>
        ) : planLoadStatus === 'error' ? (
          <div className="qplan__error" role="alert">
            <div className="qplan__error-icon" aria-hidden="true">
              <FiAlertCircle size={20} />
            </div>
            <p className="qplan__error-title">Could not load query plan</p>
            <p className="qplan__error-copy">{planLoadError ?? 'An unexpected error occurred.'}</p>
            <button
              className="qplan__retry-btn"
              type="button"
              onClick={handleRetry}
              disabled={!activePlanId}
            >
              Retry
            </button>
          </div>
        ) : graph.nodes.length > 0 ? (
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
        {nodeCount > 0 && (
          <>
            <StatusBadge label={`${nodeCount} nodes`} variant="gray" />
            <StatusBadge label={`cost ${totalCost.toFixed(1)}`} variant="orange" />
          </>
        )}
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
