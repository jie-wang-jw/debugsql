// ================================================
// DebugSQL – Execution pipeline type definitions
// ================================================

/** Lifecycle states of a single query execution run. */
export type ExecutionStatus = 'idle' | 'running' | 'success' | 'failed';

/** A single column descriptor for the results table. */
export interface ExecutionColumn {
  key:   string;
  label: string;
}

/** A single result row — values may be strings, numbers, or null. */
export type ExecutionRow = Record<string, string | number | null>;

/** Timing and size metrics returned alongside the results. */
export interface ExecutionMetrics {
  planningTimeMs:   number;
  executionTimeMs:  number;
  rowCount:         number;
  /** Estimated rows from the query planner. */
  estimatedRows:    number;
}

/** Full result payload produced by a successful execution run. */
export interface ExecutionResult {
  /** The SQL that was executed (or would be sent to the DB). */
  sql:     string;
  columns: ExecutionColumn[];
  rows:    ExecutionRow[];
  metrics: ExecutionMetrics;
}
