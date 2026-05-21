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
function formatCellValue(value: unknown): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'number') {
    return value % 1 !== 0
      ? value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
      : value.toLocaleString('en-US');
  }
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  return String(value);
}

/** Build column headers when API omits them but rows contain keys. */
function resolveColumns(columns: ExecutionColumn[], rows: ExecutionRow[]): ExecutionColumn[] {
  if (columns.length > 0) return columns;
  const first = rows[0];
  if (!first) return [];
  return Object.keys(first).map((key) => ({ key, label: key }));
}

export function ResultsTable({ columns, rows }: ResultsTableProps) {
  const resolvedColumns = resolveColumns(columns, rows);

  if (resolvedColumns.length === 0) {
    return (
      <div className="results-table-wrap results-table-wrap--empty">
        <p className="results-table__empty">No rows returned.</p>
      </div>
    );
  }

  return (
    <div className="results-table-wrap">
      <div className="results-table-scroll">
        <table className="results-table" aria-label="Query results">
          <thead>
            <tr>
              {resolvedColumns.map((col) => (
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
              <tr key={rowIdx} className="results-table__row">
                {resolvedColumns.map((col) => {
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
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
