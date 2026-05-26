import { motion } from 'framer-motion';
import { FiSearch, FiGitMerge, FiList, FiBarChart2, FiFilter, FiHash } from 'react-icons/fi';
import type { QueryNode } from '../../types';
import { getNodeTypeColor } from '../../utils';
import './PlanNode.css';

interface PlanNodeProps {
  node: QueryNode;
  isSelected?: boolean;
  onClick?: (id: string) => void;
}

// Map node types to appropriate icons
const NODE_ICONS: Record<string, React.ComponentType<{ size?: number }>> = {
  SeqScan:    FiSearch,
  IndexScan:  FiSearch,
  HashJoin:   FiGitMerge,
  MergeJoin:  FiGitMerge,
  NestedLoop: FiGitMerge,
  Sort:       FiList,
  Aggregate:  FiBarChart2,
  Filter:     FiFilter,
  Hash:       FiHash,
  Limit:      FiList,
};

/** A single node card in the query plan visualization tree. */
export function PlanNode({ node, isSelected = false, onClick }: PlanNodeProps) {
  const Icon = NODE_ICONS[node.type] ?? FiSearch;
  const color = getNodeTypeColor(node.type);

  return (
    <motion.div
      className={`plan-node ${isSelected ? 'plan-node--selected' : ''}`}
      style={{ '--node-color': color } as React.CSSProperties}
      onClick={() => onClick?.(node.id)}
      whileHover={{ scale: 1.025, y: -2 }}
      whileTap={{ scale: 0.98 }}
      transition={{ duration: 0.15, ease: 'easeOut' }}
      role="button"
      tabIndex={0}
      aria-selected={isSelected}
      onKeyDown={(e) => e.key === 'Enter' && onClick?.(node.id)}
    >
      <div className="plan-node__header">
        <div className="plan-node__icon">
          <Icon size={12} />
        </div>
        <span className="plan-node__type">{node.type}</span>
      </div>

      {node.relation && (
        <p className="plan-node__relation">{node.relation}</p>
      )}

      <div className="plan-node__stats">
        {node.totalCost !== undefined && (
          <span className="plan-node__stat">
            <span className="plan-node__stat-label">cost</span>
            <span className="plan-node__stat-value">{node.totalCost.toFixed(2)}</span>
          </span>
        )}
        {node.estimatedRows !== undefined && (
          <span className="plan-node__stat">
            <span className="plan-node__stat-label">rows</span>
            <span className="plan-node__stat-value">{node.estimatedRows.toLocaleString()}</span>
          </span>
        )}
      </div>
    </motion.div>
  );
}
