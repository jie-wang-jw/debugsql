// ================================================
// DebugSQL – Inspector field derivation utilities
//
// Maps FlowNodeData (per kind) → typed InspectorSection arrays
// for rendering in the Inspector panel, and applies edits back.
// ================================================

import type { InspectorField } from '../../types';
import type {
  FlowNodeData,
  IntentNodeData,
  OperationNodeData,
  DataNodeData,
} from '../query-plan/queryPlan.types';

// ---- Section descriptor ----

export interface InspectorSection {
  /** Displayed as the section header label. */
  title: string;
  /** CSS color value used for the section left-border accent. */
  accent: string;
  fields: InspectorField[];
}

// ---- Private helpers ----

function f(
  key: string,
  label: string,
  value: InspectorField['value'],
  editable: boolean,
  type: InspectorField['type'] = 'string',
): InspectorField {
  return { key, label, value, editable, type };
}

const csv = (arr: string[] | undefined): string => arr?.join(', ') ?? '';

const splitCSV = (v: string | number | boolean | null): string[] =>
  String(v ?? '')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);

// ---- Derivation: IntentNode ----

function deriveIntentSections(data: IntentNodeData): InspectorSection[] {
  return [
    {
      title: 'Intent',
      accent: 'var(--accent-blue-light)',
      fields: [
        f('intentLabel', 'Intent Label', data.intentLabel,           true,  'string'),
        f('aggregation', 'Aggregation',  data.aggregation ?? '',     true,  'code'),
      ],
    },
    {
      title: 'Scope',
      accent: 'var(--accent-cyan)',
      fields: [
        f('filters',       'Filters',         csv(data.filters),       true, 'code'),
        f('groupBy',       'Group By',        csv(data.groupBy),       true, 'string'),
        f('targetColumns', 'Target Columns',  csv(data.targetColumns), true, 'string'),
      ],
    },
  ];
}

// ---- Derivation: OperationNode ----

function deriveOperationSections(data: OperationNodeData): InspectorSection[] {
  return [
    {
      title: 'Operation',
      accent: 'var(--accent-purple)',
      fields: [
        f('operationType',  'Type',         data.operationType,                 false, 'string'),
        f('label',          'Label',        data.label,                         true,  'string'),
        f('detail',         'Detail / Expr', data.detail ?? '',                 true,  'code'),
        f('executionState', 'Exec. State',  data.executionState ?? 'pending',   false, 'string'),
      ],
    },
    {
      title: 'Cost Estimates',
      accent: 'var(--accent-orange)',
      fields: [
        f('estimatedRows', 'Est. Rows', data.estimatedRows ?? 0, true,  'number'),
        f('cost',          'Est. Cost', data.cost          ?? 0, false, 'number'),
      ],
    },
  ];
}

// ---- Derivation: DataNode ----

function deriveDataSections(data: DataNodeData): InspectorSection[] {
  return [
    {
      title: 'Data Source',
      accent: 'var(--accent-green)',
      fields: [
        f('nodeRole',  'Role',          data.nodeRole,  false, 'string'),
        f('tableName', 'Table / Label', data.tableName, true,  'string'),
      ],
    },
    {
      title: 'Statistics',
      accent: 'var(--accent-orange)',
      fields: [
        f('rowCount',      'Row Count', data.rowCount      ?? 0, true,  'number'),
        f('estimatedCost', 'Est. Cost', data.estimatedCost ?? 0, false, 'number'),
        f('columns',       'Columns',   csv(data.columns),       true,  'string'),
      ],
    },
  ];
}

// ---- Public: derive sections from any node kind ----

export function deriveNodeSections(data: FlowNodeData): InspectorSection[] {
  switch (data.kind) {
    case 'intent':    return deriveIntentSections(data);
    case 'operation': return deriveOperationSections(data);
    case 'data':      return deriveDataSections(data);
  }
}

// ---- Apply edited InspectorField values back to node data ----

function getStr(fields: InspectorField[], key: string): string {
  return String(fields.find((f) => f.key === key)?.value ?? '');
}

function getNum(fields: InspectorField[], key: string, fallback: number | undefined): number | undefined {
  const raw = Number(getStr(fields, key));
  return Number.isFinite(raw) && raw >= 0 ? raw : fallback;
}

/**
 * Produces a new FlowNodeData object by applying the user's
 * edited InspectorField values onto the original data.
 *
 * Only editable fields are mutated; read-only fields (e.g. operationType)
 * retain their original values.
 */
export function applyEditsToNodeData(
  original: FlowNodeData,
  editedFields: InspectorField[],
): FlowNodeData {
  switch (original.kind) {
    case 'intent':
      return {
        ...original,
        intentLabel:   getStr(editedFields, 'intentLabel'),
        aggregation:   getStr(editedFields, 'aggregation') || undefined,
        filters:       splitCSV(getStr(editedFields, 'filters')),
        groupBy:       splitCSV(getStr(editedFields, 'groupBy')),
        targetColumns: splitCSV(getStr(editedFields, 'targetColumns')),
      };

    case 'operation':
      return {
        ...original,
        label:         getStr(editedFields, 'label'),
        detail:        getStr(editedFields, 'detail') || undefined,
        estimatedRows: getNum(editedFields, 'estimatedRows', original.estimatedRows),
      };

    case 'data':
      return {
        ...original,
        tableName: getStr(editedFields, 'tableName'),
        rowCount:  getNum(editedFields, 'rowCount', original.rowCount),
        columns:   splitCSV(getStr(editedFields, 'columns')),
      };
  }
}
