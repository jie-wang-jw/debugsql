// ================================================
// DebugSQL – ResultsTable  (Phase 5)
//
// Dark, modern data table for query result rows.
// Renders within any scrollable container.
//
// TODO: Add pagination for large result sets (backend cursor)
// TODO: Add column sorting by clicking headers
// TODO: Add CSV / JSON export via backend API
// TODO: Support infinite-scroll streaming rows from backend
// ================================================

import { motion } from 'framer-motion';
import type { ExecutionColumn, ExecutionRow } from '../../types/execution.types';

interface ResultsTableProps {
  columns: ExecutionColumn[];
  rows:    ExecutionRow[];
}

/** Detects whether a column is numeric to right-align its cells. */
function isNumericColumn(rows: ExecutionRow[], key: string): boolean {
  return rows.some((r) => typeof r[key] === 'number');
}

/** Formats a single cell value for display. */
function formatCellValue(value: string | number | null): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'number') {
    // Use locale formatting for large numbers / decimals
    return value % 1 !== 0
      ? value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
      : value.toLocaleString('en-US');
  }
  return String(value);
}

const ROW_VARIANTS = {
  hidden:  { opacity: 0, y: 4 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.03, duration: 0.2, ease: 'easeOut' as const },
  }),
};

export function ResultsTable({ columns, rows }: ResultsTableProps) {
  return (
    <motion.div
      className="results-table-wrap"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
    >
      <div className="results-table-scroll">
        <table className="results-table" aria-label="Query results">
          <thead>
            <tr>
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={`results-table__th ${isNumericColumn(rows, col.key) ? 'results-table__th--num' : ''}`}
                >
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, rowIdx) => (
              <motion.tr
                key={rowIdx}
                className="results-table__row"
                custom={rowIdx}
                variants={ROW_VARIANTS}
                initial="hidden"
                animate="visible"
              >
                {columns.map((col) => {
                  const value = row[col.key] ?? null;
                  const isNum = typeof value === 'number';
                  return (
                    <td
                      key={col.key}
                      className={[
                        'results-table__td',
                        isNum ? 'results-table__td--num' : '',
                        value === null ? 'results-table__td--null' : '',
                      ].join(' ')}
                    >
                      {formatCellValue(value)}
                    </td>
                  );
                })}
              </motion.tr>
            ))}
          </tbody>
        </table>
      </div>
    </motion.div>
  );
}
