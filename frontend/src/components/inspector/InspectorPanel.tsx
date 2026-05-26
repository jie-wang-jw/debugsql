// ================================================
// DebugSQL – Inspector Panel  (Phase 4)
//
// Displays editable fields for the currently selected React Flow node.
// Driven by QueryPlanContext — no direct props needed.
// ================================================

import { useState, useEffect, useMemo, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  FiSliders,
  FiPlay,
  FiEdit3,
  FiMousePointer,
  FiCheckCircle,
  FiZap,
  FiDatabase,
  FiGitMerge,
  FiRefreshCw,
} from 'react-icons/fi';
import type { InspectorField } from '../../types';
import type { FlowNodeData, QueryPlanEditResult } from '../query-plan/queryPlan.types';
import { useQueryPlanContext } from '../../store/QueryPlanContext';
import { useExecutionContext } from '../../store/ExecutionContext';
import { useReexecutePlan } from '../../hooks/useReexecutePlan';
import {
  deriveNodeSections,
  applyEditsToNodeData,
  type InspectorSection,
} from './inspectorFields.utils';
import { StatusBadge } from '../ui/StatusBadge';
import './InspectorPanel.css';

// ---- Node display helpers ----

function getNodeKindLabel(data: FlowNodeData): string {
  switch (data.kind) {
    case 'intent':    return 'Query Intent';
    case 'operation': return data.operationType;
    case 'data':      return data.nodeRole === 'result' ? 'Result Set' : 'Table Source';
  }
}

function getNodeDisplayName(data: FlowNodeData): string {
  switch (data.kind) {
    case 'intent':    return data.intentLabel;
    case 'operation': return data.label;
    case 'data':      return data.tableName;
  }
}

type AccentVariant = 'blue' | 'purple' | 'green' | 'cyan' | 'orange' | 'gray';

function getNodeAccent(data: FlowNodeData): AccentVariant {
  switch (data.kind) {
    case 'intent':    return 'blue';
    case 'operation': return 'purple';
    case 'data':      return data.nodeRole === 'result' ? 'purple' : 'green';
  }
}

function getNodeIcon(data: FlowNodeData) {
  switch (data.kind) {
    case 'intent':    return <FiZap      size={13} />;
    case 'operation': return <FiGitMerge size={13} />;
    case 'data':      return <FiDatabase size={13} />;
  }
}

function resolveApplyHint(
  isDirty: boolean,
  isApplied: boolean,
  editResult?: QueryPlanEditResult,
): string {
  if (isDirty) {
    return 'Unsaved changes - click Apply to update the graph';
  }
  if (isApplied && editResult?.needsReplan) {
    return `Needs full replan - ${editResult.message}`;
  }
  if (isApplied && editResult?.status === 'regenerated') {
    return `Downstream replanned - ${editResult.message}`;
  }
  if (isApplied) {
    return editResult?.message || 'Applied';
  }
  return 'Edit fields above to modify the query plan node';
}

// ---- Main component ----

export function InspectorPanel() {
  const { graph, selectedNode, selectedNodeId, onNodeDataUpdate } = useQueryPlanContext();
  const { resetExecution } = useExecutionContext();
  const {
    canReexecute,
    blockedReason,
    isReexecuting,
    reexecutePlan,
  } = useReexecutePlan();

  // Flat list of all editable/read-only fields — reset on each new selection
  const [editedFields, setEditedFields] = useState<InspectorField[]>([]);
  const [isDirty,    setIsDirty]    = useState(false);
  const [isApplied,  setIsApplied]  = useState(false);
  const [isRerunning, setIsRerunning] = useState(false);

  // Reset local field state whenever the selected node changes
  useEffect(() => {
    if (selectedNode) {
      const allFields = deriveNodeSections(selectedNode.data).flatMap((s) => s.fields);
      setEditedFields(allFields);
    } else {
      setEditedFields([]);
    }
    setIsDirty(false);
    setIsApplied(false);
  }, [selectedNode]);

  /**
   * Merge current edited values into the derived sections for display.
   * The sections provide structure (title, accent, which keys belong);
   * editedFields provides the live values.
   */
  const displaySections = useMemo((): InspectorSection[] => {
    if (!selectedNode) return [];
    const editedMap = Object.fromEntries(editedFields.map((f) => [f.key, f.value]));
    return deriveNodeSections(selectedNode.data).map((section) => ({
      ...section,
      fields: section.fields.map((field) => ({
        ...field,
        value: editedMap[field.key] ?? field.value,
      })),
    }));
  }, [selectedNode, editedFields]);

  const handleChange = useCallback((key: string, newValue: string) => {
    setEditedFields((prev) =>
      prev.map((f) => (f.key === key ? { ...f, value: newValue } : f))
    );
    setIsDirty(true);
    setIsApplied(false);
  }, []);

  const handleApply = useCallback(async (): Promise<boolean> => {
    if (!selectedNode || !selectedNodeId) return false;

    const updatedData = applyEditsToNodeData(selectedNode.data, editedFields);
    try {
      await onNodeDataUpdate(selectedNodeId, updatedData);

      setIsDirty(false);
      setIsApplied(true);
      resetExecution();
      return true;
    } catch (error) {
      console.error('Failed to apply node changes', error);
      return false;
    }
  }, [selectedNode, selectedNodeId, editedFields, onNodeDataUpdate, resetExecution]);

  const handleRerun = useCallback(async () => {
    if (!canReexecute || isReexecuting || isRerunning) return;

    setIsRerunning(true);
    try {
      if (isDirty) {
        const applied = await handleApply();
        if (!applied) return;
      }
      await reexecutePlan();
    } finally {
      setIsRerunning(false);
    }
  }, [canReexecute, handleApply, isDirty, isReexecuting, isRerunning, reexecutePlan]);

  const rerunDisabled = !canReexecute || isReexecuting || isRerunning;
  const rerunHint = blockedReason
    ?? (isDirty
      ? 'Pending edits will be applied before re-running'
      : 'Re-run the full query using the updated plan');

  const accent: AccentVariant = selectedNode
    ? getNodeAccent(selectedNode.data)
    : 'gray';

  return (
    <div className="inspector">
      <InspectorHeader isDirty={isDirty} isApplied={isApplied} />

      <AnimatePresence mode="wait">
        {/* ---- Empty state ---- */}
        {!selectedNode && (
          <motion.div
            key="empty"
            className="inspector__body"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
          >
            <InspectorEmptyState />
          </motion.div>
        )}

        {/* ---- Populated state ---- */}
        {selectedNode && (
          <motion.div
            key={selectedNodeId}
            className="inspector__body"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.26, ease: [0.22, 1, 0.36, 1] }}
          >
            {/* Node identity banner */}
            <InspectorNodeBanner
              icon={getNodeIcon(selectedNode.data)}
              kindLabel={getNodeKindLabel(selectedNode.data)}
              displayName={getNodeDisplayName(selectedNode.data)}
              nodeId={selectedNodeId!}
              accent={accent}
            />

            {/* Grouped field sections */}
            {displaySections.map((section) => (
              <InspectorSectionGroup
                key={section.title}
                section={section}
                onChange={handleChange}
              />
            ))}

            {/* Apply / re-run actions */}
            <div className="inspector__actions">
              <div className="inspector__action-row">
                <motion.button
                  type="button"
                  className={[
                    'inspector__apply-btn',
                    isDirty   ? 'inspector__apply-btn--active'  : '',
                    isApplied ? 'inspector__apply-btn--applied' : '',
                  ].join(' ')}
                  onClick={() => void handleApply()}
                  disabled={!isDirty}
                  whileTap={isDirty ? { scale: 0.97 } : {}}
                  transition={{ duration: 0.1 }}
                >
                  {isApplied ? (
                    <><FiCheckCircle size={11} /> Applied</>
                  ) : (
                    <><FiPlay size={11} /> Apply Changes</>
                  )}
                </motion.button>
                <motion.button
                  type="button"
                  className={[
                    'inspector__rerun-btn',
                    !rerunDisabled ? 'inspector__rerun-btn--active' : '',
                  ].join(' ')}
                  onClick={() => void handleRerun()}
                  disabled={rerunDisabled}
                  whileTap={!rerunDisabled ? { scale: 0.97 } : {}}
                  transition={{ duration: 0.1 }}
                  title={rerunHint}
                >
                  <FiRefreshCw
                    size={11}
                    className={isReexecuting || isRerunning ? 'inspector__rerun-icon--spin' : ''}
                  />
                  {isReexecuting || isRerunning ? 'Re-ejecutando…' : 'Re-ejecutar plan'}
                </motion.button>
              </div>
              <p className="inspector__apply-hint">
                {rerunDisabled && blockedReason
                  ? blockedReason
                  : resolveApplyHint(isDirty, isApplied, graph.lastEditResult)}
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ================================================================
// Sub-components
// ================================================================

/* ---- Header ---- */

interface InspectorHeaderProps {
  isDirty:   boolean;
  isApplied: boolean;
}

function InspectorHeader({ isDirty, isApplied }: InspectorHeaderProps) {
  return (
    <div className="inspector__header">
      <div className="inspector__header-left">
        <div className="inspector__header-icon">
          <FiSliders size={12} />
        </div>
        <span className="inspector__title">Node Inspector</span>
      </div>
      <div className="inspector__header-right">
        <AnimatePresence mode="wait">
          {isDirty && (
            <motion.span
              key="modified"
              initial={{ opacity: 0, scale: 0.85 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.85 }}
              transition={{ duration: 0.15 }}
            >
              <StatusBadge label="modified" variant="orange" dot />
            </motion.span>
          )}
          {isApplied && !isDirty && (
            <motion.span
              key="applied"
              initial={{ opacity: 0, scale: 0.85 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.85 }}
              transition={{ duration: 0.15 }}
            >
              <StatusBadge label="applied" variant="green" dot />
            </motion.span>
          )}
          {!isDirty && !isApplied && (
            <motion.span
              key="editable"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
            >
              <StatusBadge label="editable" variant="blue" />
            </motion.span>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

/* ---- Empty state ---- */

function InspectorEmptyState() {
  return (
    <div className="inspector__empty">
      <motion.div
        className="inspector__empty-icon"
        initial={{ scale: 0.8, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ delay: 0.1, duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
      >
        <FiMousePointer size={20} />
      </motion.div>
      <motion.p
        className="inspector__empty-title"
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.18, duration: 0.3 }}
      >
        No node selected
      </motion.p>
      <motion.p
        className="inspector__empty-hint"
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.24, duration: 0.3 }}
      >
        Click any node in the query plan graph to inspect and edit its properties.
      </motion.p>
    </div>
  );
}

/* ---- Node identity banner ---- */

interface NodeBannerProps {
  icon:        React.ReactNode;
  kindLabel:   string;
  displayName: string;
  nodeId:      string;
  accent:      AccentVariant;
}

function InspectorNodeBanner({
  icon,
  kindLabel,
  displayName,
  nodeId,
  accent,
}: NodeBannerProps) {
  return (
    <div className={`inspector__node-banner inspector__node-banner--${accent}`}>
      <div className="inspector__node-banner-icon">{icon}</div>
      <div className="inspector__node-banner-body">
        <span className="inspector__node-kind">{kindLabel}</span>
        <strong className="inspector__node-name">{displayName}</strong>
      </div>
      <span className="inspector__node-id">#{nodeId}</span>
    </div>
  );
}

/* ---- Section group ---- */

interface SectionGroupProps {
  section:  InspectorSection;
  onChange: (key: string, value: string) => void;
}

function InspectorSectionGroup({ section, onChange }: SectionGroupProps) {
  return (
    <div className="inspector__section">
      <div
        className="inspector__section-header"
        style={{ '--section-accent': section.accent } as React.CSSProperties}
      >
        <span className="inspector__section-dot" />
        <span className="inspector__section-title">{section.title}</span>
      </div>
      <div className="inspector__fields">
        {section.fields.map((field) => (
          <FieldRow key={field.key} field={field} onChange={onChange} />
        ))}
      </div>
    </div>
  );
}

/* ---- Field row ---- */

interface FieldRowProps {
  field:    InspectorField;
  onChange: (key: string, value: string) => void;
}

function FieldRow({ field, onChange }: FieldRowProps) {
  return (
    <motion.div
      className={`field-row ${field.editable ? 'field-row--editable' : ''}`}
      whileHover={field.editable ? { backgroundColor: 'rgba(255,255,255,0.028)' } : {}}
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
        <span
          className={`field-row__value ${field.type === 'code' ? 'field-row__value--mono' : ''}`}
        >
          {String(field.value)}
        </span>
      )}
    </motion.div>
  );
}
