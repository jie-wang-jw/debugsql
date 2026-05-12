import { useState } from 'react';
import { motion } from 'framer-motion';
import { FiSliders, FiPlay, FiInfo, FiEdit3 } from 'react-icons/fi';
import type { InspectorField } from '../../types';
import { FadeIn } from '../animations/FadeIn';
import { StatusBadge } from '../ui/StatusBadge';
import './InspectorPanel.css';

// TODO: Connect inspector state to the selected query plan node
// The selectedNodeId from QueryPlanArea should drive this panel's content
const MOCK_NODE_LABEL = 'Hash Join';

const MOCK_FIELDS: InspectorField[] = [
  { key: 'nodeType',     label: 'Node Type',      value: 'HashJoin',            editable: false, type: 'string' },
  { key: 'joinType',     label: 'Join Type',       value: 'Inner',               editable: true,  type: 'string' },
  { key: 'hashCond',     label: 'Hash Condition',  value: '(o.user_id = u.id)',  editable: true,  type: 'code'   },
  { key: 'startupCost',  label: 'Startup Cost',    value: 12.50,                 editable: false, type: 'number' },
  { key: 'totalCost',    label: 'Total Cost',      value: 45.23,                 editable: false, type: 'number' },
  { key: 'estimatedRows',label: 'Estimated Rows',  value: 1183,                  editable: true,  type: 'number' },
  { key: 'actualRows',   label: 'Actual Rows',     value: 1140,                  editable: false, type: 'number' },
];

export function InspectorPanel() {
  const [fields, setFields] = useState<InspectorField[]>(MOCK_FIELDS);
  const [isDirty, setIsDirty] = useState(false);

  // TODO: POST updated node fields to backend (PATCH /api/query-plan/:id/nodes/:nodeId)
  function handleApply() {
    setIsDirty(false);
  }

  function handleChange(key: string, newValue: string) {
    setFields((prev) =>
      prev.map((f) => (f.key === key ? { ...f, value: newValue } : f))
    );
    setIsDirty(true);
  }

  return (
    <div className="inspector">
      <InspectorHeader isDirty={isDirty} />
      <FadeIn direction="up" delay={0.15} className="inspector__body">
        <div className="inspector__selected-info">
          <FiInfo size={11} />
          <span>Selected node:</span>
          <strong>{MOCK_NODE_LABEL}</strong>
        </div>

        <div className="inspector__fields">
          {fields.map((field) => (
            <FieldRow
              key={field.key}
              field={field}
              onChange={handleChange}
            />
          ))}
        </div>

        <div className="inspector__actions">
          <button
            className={`inspector__apply-btn ${isDirty ? 'inspector__apply-btn--active' : ''}`}
            onClick={handleApply}
            disabled={!isDirty}
          >
            <FiPlay size={11} />
            Apply Changes
          </button>
          <p className="inspector__apply-hint">
            {isDirty
              ? 'Unsaved changes — click Apply to re-execute the plan'
              : 'Edit fields above to modify the query plan node'}
          </p>
        </div>
      </FadeIn>
    </div>
  );
}

/* ---- Header ---- */
function InspectorHeader({ isDirty }: { isDirty: boolean }) {
  return (
    <div className="inspector__header">
      <div className="inspector__header-left">
        <div className="inspector__header-icon">
          <FiSliders size={12} />
        </div>
        <span className="inspector__title">Node Inspector</span>
      </div>
      <div className="inspector__header-right">
        {isDirty && <StatusBadge label="modified" variant="orange" dot />}
        <StatusBadge label="editable" variant="blue" />
      </div>
    </div>
  );
}

/* ---- Field row ---- */
interface FieldRowProps {
  field: InspectorField;
  onChange: (key: string, value: string) => void;
}

function FieldRow({ field, onChange }: FieldRowProps) {
  return (
    <motion.div
      className={`field-row ${field.editable ? 'field-row--editable' : ''}`}
      whileHover={field.editable ? { backgroundColor: 'var(--bg-hover)' } : {}}
      transition={{ duration: 0.12 }}
    >
      <div className="field-row__label-wrap">
        <span className="field-row__label">{field.label}</span>
        {field.editable && (
          <FiEdit3 size={9} className="field-row__edit-icon" />
        )}
      </div>
      {field.editable ? (
        <input
          className={`field-row__input ${field.type === 'code' ? 'field-row__input--mono' : ''}`}
          value={String(field.value)}
          onChange={(e) => onChange(field.key, e.target.value)}
          aria-label={field.label}
        />
      ) : (
        <span className={`field-row__value ${field.type === 'code' ? 'field-row__value--mono' : ''}`}>
          {String(field.value)}
        </span>
      )}
    </motion.div>
  );
}
