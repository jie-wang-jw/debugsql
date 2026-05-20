import { memo } from 'react';
import { Handle, Position, type NodeProps } from 'reactflow';
import { motion } from 'framer-motion';
import { FiZap, FiFilter, FiLayers, FiTarget } from 'react-icons/fi';
import type { IntentNodeData } from '../queryPlan.types';

/**
 * IntentNode – Represents the semantic intent derived from the NL query.
 * This is the "AI reasoning" entry point of the execution pipeline.
 *
 * TODO: Populate intent fields from NL parsing backend response
 */
export const IntentNode = memo(function IntentNode({
  data,
  selected,
}: NodeProps<IntentNodeData>) {
  return (
    <motion.div
      className={`flow-node flow-node--intent ${selected ? 'flow-node--selected' : ''}`}
      initial={{ opacity: 0, scale: 0.92, y: -8 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
      whileHover={{ scale: 1.015, y: -2 }}
    >
      {/* Source handle at bottom — connects to first operation */}
      <Handle type="source" position={Position.Bottom} id="bottom" className="flow-handle" />

      {/* Header */}
      <div className="flow-node__header">
        <div className="flow-node__icon flow-node__icon--intent">
          <FiZap size={13} />
        </div>
        <div className="flow-node__titles">
          <span className="flow-node__kind">Query Intent</span>
          <span className="flow-node__label">{data.intentLabel}</span>
        </div>
      </div>

      {/* Fields */}
      <div className="flow-node__fields">
        {data.aggregation && (
          <IntentField icon={<FiLayers size={9} />} label="Aggregate" value={data.aggregation} />
        )}
        {data.filters?.map((f, i) => (
          <IntentField key={i} icon={<FiFilter size={9} />} label="Filter" value={f} />
        ))}
        {data.groupBy && data.groupBy.length > 0 && (
          <IntentField
            icon={<FiLayers size={9} />}
            label="Group by"
            value={data.groupBy.join(', ')}
          />
        )}
        {data.targetColumns && data.targetColumns.length > 0 && (
          <IntentField
            icon={<FiTarget size={9} />}
            label="Columns"
            value={data.targetColumns.join(', ')}
          />
        )}
      </div>
    </motion.div>
  );
});

interface IntentFieldProps {
  icon: React.ReactNode;
  label: string;
  value: string;
}

function IntentField({ icon, label, value }: IntentFieldProps) {
  return (
    <div className="intent-field">
      <span className="intent-field__icon">{icon}</span>
      <span className="intent-field__label">{label}</span>
      <span className="intent-field__value">{value}</span>
    </div>
  );
}
