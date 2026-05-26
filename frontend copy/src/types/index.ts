// ================================================
// DebugSQL – Shared Type Definitions
// ================================================

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  isLoading?: boolean;
}

export type NodeType =
  | 'SeqScan'
  | 'IndexScan'
  | 'HashJoin'
  | 'MergeJoin'
  | 'NestedLoop'
  | 'Sort'
  | 'Aggregate'
  | 'Limit'
  | 'Hash'
  | 'Filter';

export interface QueryNode {
  id: string;
  type: NodeType;
  relation?: string;
  estimatedRows?: number;
  actualRows?: number;
  totalCost?: number;
  startupCost?: number;
  filter?: string;
  indexName?: string;
  joinType?: string;
  hashCond?: string;
  children?: string[];
}

export interface InspectorField {
  key: string;
  label: string;
  value: string | number | boolean | null;
  editable: boolean;
  type: 'string' | 'number' | 'boolean' | 'code';
}

// TODO: Extend with full query plan tree shape once backend is integrated
export interface QueryPlanState {
  nodes: QueryNode[];
  selectedNodeId: string | null;
  rawSql: string;
  isLoading: boolean;
}

export interface NavigationItem {
  path: string;
  label: string;
  iconName: string;
  disabled?: boolean;
}
