import { memo } from 'react';
import { Handle, Position, type NodeProps } from 'reactflow';
import { motion } from 'framer-motion';
import { FiDatabase, FiTable, FiColumns } from 'react-icons/fi';
import type { DataNodeData } from '../queryPlan.types';

/**
 * DataNode – Represents a data source (table scan) or the final result set.
 *
 * Source nodes:  green accent — connects to the JOIN via side handles
 * Result nodes:  blue/purple accent — terminal node, no outbound edges
 *
 * TODO: Clicking a result node should display row previews in the Inspector
 */
export const DataNode = memo(function DataNode({
  data,
  selected,
}: NodeProps<DataNodeData>) {
  const isResult = data.nodeRole === 'result';
  const Icon = isResult ? FiTable : FiDatabase;

  return (
    <motion.div
      className={`flow-node flow-node--data flow-node--data-${data.nodeRole} ${selected ? 'flow-node--selected' : ''}`}
      initial={{ opacity: 0, scale: 0.92 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
      whileHover={{ scale: 1.02, y: -2 }}
    >
      {/* Source node: right and left side handles + bottom */}
      {!isResult && (
        <>
          <Handle type="source" position={Position.Right}  id="right"  className="flow-handle flow-handle--side flow-handle--data" />
          <Handle type="source" position={Position.Left}   id="left"   className="flow-handle flow-handle--side flow-handle--data" />
          <Handle type="source" position={Position.Bottom} id="bottom" className="flow-handle flow-handle--data" />
        </>
      )}

      {/* Result node: only receives from above */}
      {isResult && (
        <Handle type="target" position={Position.Top} id="top" className="flow-handle flow-handle--data" />
      )}

      {/* Header */}
      <div className="flow-node__header">
        <div className={`flow-node__icon flow-node__icon--data-${data.nodeRole}`}>
          <Icon size={12} />
        </div>
        <div className="flow-node__titles">
          <span className="flow-node__kind">{isResult ? 'Result Set' : 'Table Scan'}</span>
          <span className="flow-node__label flow-node__label--mono">{data.tableName}</span>
        </div>
      </div>

      {/* Stats */}
      <div className="flow-node__stats">
        {data.rowCount !== undefined && (
          <span className="flow-node__stat">
            <span className="flow-node__stat-key">{isResult ? 'output' : 'rows'}</span>
            <span className="flow-node__stat-val">{data.rowCount.toLocaleString()}</span>
          </span>
        )}
        {data.estimatedCost !== undefined && (
          <span className="flow-node__stat">
            <span className="flow-node__stat-key">cost</span>
            <span className="flow-node__stat-val">{data.estimatedCost.toFixed(2)}</span>
          </span>
        )}
      </div>

      {/* Column list */}
      {data.columns && data.columns.length > 0 && (
        <div className="data-node__columns">
          <FiColumns size={8} className="data-node__col-icon" />
          <span className="data-node__col-list">
            {data.columns.slice(0, 4).join(', ')}
            {data.columns.length > 4 && <em> +{data.columns.length - 4} more</em>}
          </span>
        </div>
      )}
    </motion.div>
  );
});
