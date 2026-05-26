import { useCallback, useMemo } from 'react';
import { useQueryPlanContext } from '../store/QueryPlanContext';
import { useExecutionContext } from '../store/ExecutionContext';

export interface UseReexecutePlanResult {
  /** Whether a plan re-run can be triggered right now. */
  canReexecute: boolean;
  /** Plan edits require a full replan before execution. */
  needsReplan: boolean;
  /** Human-readable reason when re-execution is blocked. */
  blockedReason: string | null;
  /** Whether a re-run request is in flight. */
  isReexecuting: boolean;
  /** Re-execute the active plan using the latest stored SQL. */
  reexecutePlan: () => Promise<boolean>;
}

/**
 * Shared logic for re-running the active query plan after node edits.
 * Used by InspectorPanel and ExecutionPanel.
 */
export function useReexecutePlan(): UseReexecutePlanResult {
  const { activePlanId, graph, refreshActivePlan } = useQueryPlanContext();
  const { triggerExecution, lastExecutionSql, result, status } = useExecutionContext();

  const needsReplan = Boolean(graph.needsReplan || graph.lastEditResult?.needsReplan);

  const blockedReason = useMemo(() => {
    if (!activePlanId) {
      return 'No active query plan. Generate a plan from the chat first.';
    }
    if (needsReplan) {
      return graph.lastEditResult?.message ?? 'Plan edits require a full replan before execution.';
    }
    return null;
  }, [activePlanId, needsReplan, graph.lastEditResult?.message]);

  const canReexecute = Boolean(activePlanId) && !needsReplan;
  const isReexecuting = status === 'running';

  const reexecutePlan = useCallback(async (): Promise<boolean> => {
    if (!canReexecute || !activePlanId || isReexecuting) {
      return false;
    }

    const sql =
      result?.sql?.trim() ||
      lastExecutionSql?.trim() ||
      graph.queryLabel?.trim() ||
      '';

    await triggerExecution(sql, activePlanId);
    await refreshActivePlan();
    return true;
  }, [
    activePlanId,
    canReexecute,
    graph.queryLabel,
    isReexecuting,
    lastExecutionSql,
    refreshActivePlan,
    result?.sql,
    triggerExecution,
  ]);

  return {
    canReexecute,
    needsReplan,
    blockedReason,
    isReexecuting,
    reexecutePlan,
  };
}
