import { useCallback, useState } from 'react';
import { FiCheck, FiPlay } from 'react-icons/fi';
import type { ProposedToolAction } from '../../services/api/chatApi';
import { executeTool } from '../../services/api/capabilitiesApi';
import type { DatasetContext } from '../../services/api/chatApi';
import './ProposedActions.css';

interface ProposedActionsProps {
  actions: ProposedToolAction[];
  datasetContext?: DatasetContext;
  onResult: (actionId: string, summary: string) => void;
  onExecutionResult?: (sql: string, data: Record<string, unknown>) => void;
}

export function ProposedActions({
  actions,
  datasetContext,
  onResult,
  onExecutionResult,
}: ProposedActionsProps) {
  const [runningId, setRunningId] = useState<string | null>(null);
  const [completed, setCompleted] = useState<Record<string, boolean>>({});

  const runAction = useCallback(
    async (action: ProposedToolAction, approved = false) => {
      if (!datasetContext) {
        onResult(action.id, 'Select a database context before running tools.');
        return;
      }
      setRunningId(action.id);
      try {
        const result = await executeTool({
          tool: action.tool,
          toolCallId: action.id,
          arguments: action.arguments,
          context: {
            ...datasetContext,
            dbType: datasetContext.dbType ?? 'sqlite_benchmark',
          },
          approved,
        });
        if (!result.success) {
          onResult(action.id, result.error ?? 'Tool execution failed.');
          return;
        }
        setCompleted((prev) => ({ ...prev, [action.id]: true }));
        if (action.tool === 'run_sql') {
          const sql = String(action.arguments.sql ?? '');
          onExecutionResult?.(sql, result.data);
          onResult(action.id, `Executed SQL and returned ${String((result.data.metrics as { rowCount?: number })?.rowCount ?? 'some')} rows.`);
        } else if (action.tool === 'run_sql_preview') {
          onResult(action.id, String(result.data.message ?? 'SQL validation completed.'));
        } else if (action.tool === 'introspect_schema') {
          const tables = (result.data.tables as unknown[]) ?? [];
          onResult(action.id, `Loaded schema with ${tables.length} tables.`);
        } else {
          onResult(action.id, `${action.label} completed.`);
        }
      } catch (err) {
        onResult(action.id, err instanceof Error ? err.message : 'Tool execution failed.');
      } finally {
        setRunningId(null);
      }
    },
    [datasetContext, onExecutionResult, onResult],
  );

  if (actions.length === 0) return null;

  return (
    <div className="proposed-actions">
      <p className="proposed-actions__title">Proposed actions</p>
      {actions.map((action) => (
        <article key={action.id} className="proposed-action-card">
          <div>
            <strong>{action.label}</strong>
            {action.description && <p>{action.description}</p>}
          </div>
          <button
            type="button"
            disabled={runningId === action.id || completed[action.id]}
            onClick={() => void runAction(action, action.requiresApproval)}
          >
            {completed[action.id] ? (
              <>
                <FiCheck size={12} /> Done
              </>
            ) : action.requiresApproval ? (
              <>
                <FiPlay size={12} /> Approve & run
              </>
            ) : (
              <>
                <FiPlay size={12} /> Run
              </>
            )}
          </button>
        </article>
      ))}
    </div>
  );
}
