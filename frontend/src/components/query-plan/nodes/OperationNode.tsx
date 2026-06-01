import { memo } from 'react';
import { Handle, Position, type NodeProps } from 'reactflow';
import { motion } from 'framer-motion';
import {
  FiFilter, FiGitMerge, FiLayers, FiBarChart2,
  FiList, FiDatabase, FiCheckCircle, FiLoader, FiClock, FiAlertCircle,
} from 'react-icons/fi';
import type { OperationNodeData, OperationType, ExecutionState } from '../queryPlan.types';

/**
 * OperationNode – Represents a SQL operation in the execution pipeline.
 * Covers: FILTER, JOIN, GROUP_BY, AGGREGATE, SORT, SELECT, LIMIT.
 *
 * TODO: Connect selected state to Inspector panel for node editing
 * TODO: Animate execution state transitions when real execution is wired
 */
export const OperationNode = memo(function OperationNode({
  data,
  selected,
}: NodeProps<OperationNodeData>) {
  const isJoin = data.operationType === 'JOIN';
  const colorVar = OP_COLOR[data.operationType] ?? 'var(--text-secondary)';
  const Icon = OP_ICON[data.operationType] ?? FiDatabase;

  return (
    <motion.div
      className={`flow-node flow-node--operation flow-node--op-${data.operationType.toLowerCase()} ${selected ? 'flow-node--selected' : ''}`}
      style={{ '--op-color': colorVar } as React.CSSProperties}
      initial={{ opacity: 0, scale: 0.93 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
      whileHover={{ scale: 1.02, y: -2 }}
    >
      {/* Handles */}
      <Handle type="target" position={Position.Top} id="top" className="flow-handle" />
      {isJoin && (
        <>
          <Handle type="target" position={Position.Left}  id="left"  className="flow-handle flow-handle--side" />
          <Handle type="target" position={Position.Right} id="right" className="flow-handle flow-handle--side" />
        </>
      )}
      <Handle type="source" position={Position.Bottom} id="bottom" className="flow-handle" />

      {/* Header */}
      <div className="flow-node__header">
        <div className="flow-node__icon flow-node__icon--operation" style={{ background: `color-mix(in srgb, ${colorVar} 14%, transparent)`, color: colorVar }}>
          <Icon size={12} />
        </div>
        <div className="flow-node__titles">
          <span className="flow-node__kind" style={{ color: colorVar }}>
            {OP_LABEL[data.operationType] ?? data.operationType}
          </span>
          <span className="flow-node__label">{data.label}</span>
        </div>
        <ExecutionBadge state={data.executionState} />
      </div>

      {/* Detail */}
      {data.detail && (
        <p className="flow-node__detail">{data.detail}</p>
      )}

      {/* Stats row */}
      {(data.estimatedRows !== undefined || data.cost !== undefined) && (
        <div className="flow-node__stats">
          {data.estimatedRows !== undefined && (
            <span className="flow-node__stat">
              <span className="flow-node__stat-key">rows</span>
              <span className="flow-node__stat-val">{data.estimatedRows.toLocaleString()}</span>
            </span>
          )}
          {data.cost !== undefined && (
            <span className="flow-node__stat">
              <span className="flow-node__stat-key">cost</span>
              <span className="flow-node__stat-val">{data.cost.toFixed(2)}</span>
            </span>
          )}
        </div>
      )}
    </motion.div>
  );
});

/* ---- Execution state badge ---- */
function ExecutionBadge({ state }: { state?: ExecutionState }) {
  if (!state) return null;

  const config: Record<ExecutionState, { icon: React.ReactNode; className: string }> = {
    done:    { icon: <FiCheckCircle size={10} />, className: 'exec-badge--done'    },
    success: { icon: <FiCheckCircle size={10} />, className: 'exec-badge--done'    },
    running: { icon: <FiLoader    size={10} />, className: 'exec-badge--running'  },
    pending: { icon: <FiClock     size={10} />, className: 'exec-badge--pending'  },
    skipped: { icon: <FiClock     size={10} />, className: 'exec-badge--pending'  },
    error:   { icon: <FiAlertCircle size={10} />, className: 'exec-badge--error'  },
  };

  const { icon, className } = config[state];
  return <span className={`exec-badge ${className}`}>{icon}</span>;
}

/* ---- Look-up tables ---- */
const OP_ICON: Record<OperationType, React.ComponentType<{ size?: number }>> = {
  SELECT:    FiDatabase,
  FILTER:    FiFilter,
  GROUP_BY:  FiLayers,
  JOIN:      FiGitMerge,
  SORT:      FiList,
  AGGREGATE: FiBarChart2,
  LIMIT:     FiList,
  SQL:       FiDatabase,
  TOOL:      FiGitMerge,
  ANSWER:    FiCheckCircle,
  MERGED:    FiGitMerge,
};

const OP_COLOR: Record<OperationType, string> = {
  SELECT:    'var(--accent-blue-light)',
  FILTER:    'var(--accent-orange)',
  GROUP_BY:  'var(--accent-purple)',
  JOIN:      'var(--accent-blue)',
  SORT:      'var(--accent-cyan)',
  AGGREGATE: 'var(--accent-cyan)',
  LIMIT:     'var(--text-secondary)',
  SQL:       'var(--accent-blue-light)',
  TOOL:      'var(--accent-purple)',
  ANSWER:    'var(--accent-green)',
  MERGED:    'var(--accent-purple)',
};

const OP_LABEL: Record<OperationType, string> = {
  SELECT:    'SELECT',
  FILTER:    'FILTER',
  GROUP_BY:  'GROUP BY',
  JOIN:      'JOIN',
  SORT:      'SORT',
  AGGREGATE: 'AGGREGATE',
  LIMIT:     'LIMIT',
  SQL:       'SQL',
  TOOL:      'TOOL',
  ANSWER:    'ANSWER',
  MERGED:    'MERGED',
};
