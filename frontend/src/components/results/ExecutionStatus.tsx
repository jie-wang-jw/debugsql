// ================================================
// DebugSQL – ExecutionStatus  (Phase 5)
//
// Compact status indicator: pulsing dot + label + optional timing.
// Used in the ExecutionPanel header and the AppShell tab bar.
// ================================================

import { motion, AnimatePresence } from 'framer-motion';
import { FiCheckCircle, FiXCircle, FiClock, FiLoader } from 'react-icons/fi';
import type { ExecutionStatus } from '../../types/execution.types';

interface ExecutionStatusProps {
  status:         ExecutionStatus;
  executionTimeMs?: number;
  /** If true, renders a minimal dot-only badge (for the tab bar). */
  compact?: boolean;
}

/** Maps status to design-system color tokens. */
function statusColor(s: ExecutionStatus): string {
  switch (s) {
    case 'running': return 'var(--accent-blue)';
    case 'success': return 'var(--accent-green)';
    case 'failed':  return 'var(--accent-red)';
    default:        return 'var(--text-muted)';
  }
}

function statusLabel(s: ExecutionStatus): string {
  switch (s) {
    case 'running': return 'Running';
    case 'success': return 'Success';
    case 'failed':  return 'Failed';
    default:        return 'Idle';
  }
}

function StatusIcon({ status }: { status: ExecutionStatus }) {
  const size = 12;
  switch (status) {
    case 'running': return (
      <motion.span
        animate={{ rotate: 360 }}
        transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
        style={{ display: 'inline-flex' }}
      >
        <FiLoader size={size} />
      </motion.span>
    );
    case 'success': return <FiCheckCircle size={size} />;
    case 'failed':  return <FiXCircle size={size} />;
    default:        return <FiClock size={size} />;
  }
}

/** Full-width status bar shown inside the execution panel. */
export function ExecutionStatus({ status, executionTimeMs, compact = false }: ExecutionStatusProps) {
  if (compact) {
    return (
      <AnimatePresence>
        {status !== 'idle' && (
          <motion.span
            className="exec-status-dot"
            style={{ background: statusColor(status) }}
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
          />
        )}
      </AnimatePresence>
    );
  }

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={status}
        className={`exec-status exec-status--${status}`}
        initial={{ opacity: 0, y: -4 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: 4 }}
        transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
        style={{ '--status-color': statusColor(status) } as React.CSSProperties}
      >
        <span className="exec-status__icon" style={{ color: statusColor(status) }}>
          <StatusIcon status={status} />
        </span>
        <span className="exec-status__label" style={{ color: statusColor(status) }}>
          {statusLabel(status)}
        </span>

        {status === 'running' && (
          <motion.span
            className="exec-status__pulse"
            animate={{ opacity: [0.6, 0.15, 0.6] }}
            transition={{ duration: 1.4, repeat: Infinity, ease: 'easeInOut' }}
          />
        )}

        {status === 'success' && executionTimeMs != null && (
          <span className="exec-status__timing">
            {executionTimeMs < 1000
              ? `${executionTimeMs} ms`
              : `${(executionTimeMs / 1000).toFixed(2)} s`}
          </span>
        )}
      </motion.div>
    </AnimatePresence>
  );
}
