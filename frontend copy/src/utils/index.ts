// ================================================
// DebugSQL – Utility Functions
// ================================================

import type { NodeType } from '../types';

/** Generates a simple random ID.
 * TODO: Replace with server-generated IDs once backend is connected. */
export function generateId(): string {
  return Math.random().toString(36).slice(2, 11);
}

/** Formats a Date object to a short HH:MM time string. */
export function formatTime(date: Date): string {
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

/** Formats a query planner cost value to two decimals. */
export function formatCost(cost: number): string {
  return cost.toFixed(2);
}

/** Maps a query plan node type to its accent color variable. */
export function getNodeTypeColor(type: NodeType | string): string {
  const map: Record<string, string> = {
    SeqScan:    'var(--accent-orange)',
    IndexScan:  'var(--accent-green)',
    HashJoin:   'var(--accent-blue)',
    MergeJoin:  'var(--accent-blue)',
    NestedLoop: 'var(--accent-purple)',
    Sort:       'var(--accent-cyan)',
    Aggregate:  'var(--accent-cyan)',
    Limit:      'var(--text-muted)',
    Hash:       'var(--accent-blue-light)',
    Filter:     'var(--accent-red)',
  };
  return map[type] ?? 'var(--text-secondary)';
}

/** Maps a node type to a short category label for display. */
export function getNodeCategory(type: NodeType | string): string {
  if (['SeqScan', 'IndexScan'].includes(type)) return 'Scan';
  if (['HashJoin', 'MergeJoin', 'NestedLoop'].includes(type)) return 'Join';
  if (type === 'Sort') return 'Sort';
  if (type === 'Aggregate') return 'Agg';
  return 'Op';
}
