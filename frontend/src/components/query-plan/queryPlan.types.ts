// ================================================
// DebugSQL – Query Plan Graph Types
// ================================================
import type { Node, Edge } from 'reactflow';

// ---- Node data shapes ----

export interface IntentNodeData {
  kind: 'intent';
  intentLabel: string;
  aggregation?: string;
  filters?: string[];
  groupBy?: string[];
  targetColumns?: string[];
}

export type OperationType =
  | 'SCAN'
  | 'SELECT'
  | 'FILTER'
  | 'GROUP_BY'
  | 'JOIN'
  | 'SORT'
  | 'AGGREGATE'
  | 'LIMIT'
  | 'SQL'
  | 'TOOL'
  | 'ANSWER'
  | 'MERGED';

export type ExecutionState = 'pending' | 'running' | 'success' | 'error' | 'skipped' | 'done';

export interface QueryPlanRunStatus {
  runId: string;
  status: 'idle' | 'running' | 'success' | 'error';
  currentNodeId?: string | null;
  nextNodeId?: string | null;
  stepsCompleted: number;
  totalSteps: number;
}

export interface QueryPlanEditResult {
  status: 'regenerated' | 'graph_updated' | 'needs_replan' | 'missing_plan' | 'missing_node' | string;
  message: string;
  executableAvailable?: boolean;
  needsReplan?: boolean;
  downstreamNodeIds?: string[];
  editedNodeId?: string;
  executableSqlChanged?: boolean;
  requiresProvider?: boolean;
  operationType?: string;
  mergedNodeIds?: string[];
}

export interface OperationNodeData {
  kind: 'operation';
  operationType: OperationType;
  label: string;
  detail?: string;
  estimatedRows?: number;
  cost?: number;
  executionState?: ExecutionState;
  previewStatus?: string;
  previewMessage?: string;
  fragmentSql?: string | null;
  previewRowCount?: number;
  previewColumns?: Array<{ key?: string; label?: string }>;
  previewRows?: Array<Record<string, unknown>>;
}

export type DataNodeRole = 'source' | 'result';

export interface DataNodeData {
  kind: 'data';
  tableName: string;
  nodeRole: DataNodeRole;
  rowCount?: number;
  estimatedCost?: number;
  columns?: string[];
  executionState?: ExecutionState;
  materialized?: boolean;
  previewStatus?: string;
  previewMessage?: string;
  fragmentSql?: string | null;
  previewRowCount?: number;
  previewColumns?: Array<{ key?: string; label?: string }>;
  previewRows?: Array<Record<string, unknown>>;
}

// Union discriminated by `kind`
export type FlowNodeData = IntentNodeData | OperationNodeData | DataNodeData;

// Typed React Flow node / edge aliases
export type FlowNode = Node<FlowNodeData>;
export type FlowEdge = Edge;

// ---- Graph container ----

export interface QueryPlanGraph {
  nodes: FlowNode[];
  edges: FlowEdge[];
  queryLabel: string;
  totalCost: number;
  runStatus?: QueryPlanRunStatus;
  editStatus?: QueryPlanEditResult;
  lastEditResult?: QueryPlanEditResult;
  needsReplan?: boolean;
}
