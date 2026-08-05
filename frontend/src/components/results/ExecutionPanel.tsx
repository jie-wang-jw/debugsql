// ================================================
// DebugSQL – ExecutionPanel  (Phase 5)
//
// Orchestrates the full execution result view:
//   header + status  →  SQL preview  →  metrics  →  results table
//
// Driven by ExecutionContext — no direct props required.
//
// TODO: Add "Re-run" button that re-triggers the last query
// TODO: Show execution step timeline (planning → scan → sort → return)
// TODO: Add query history sidebar
// TODO: Stream result rows progressively from backend
// ================================================

import { motion, AnimatePresence } from 'framer-motion';
import {
  FiTerminal,
  FiAlertCircle,
  FiDatabase,
  FiClock,
  FiRefreshCw,
} from 'react-icons/fi';
import { useExecutionContext }  from '../../store/ExecutionContext';
import { ExecutionStatus }      from './ExecutionStatus';
import { SQLPreview }           from './SQLPreview';
import { ResultsTable }         from './ResultsTable';
import type { MediaPreview } from '../../types/execution.types';

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function PanelHeader() {
  const { status, result, lastExecutionSql, triggerExecution } = useExecutionContext();
  const isRunning = status === 'running';
  const showRerun = (status === 'success' || status === 'failed') && Boolean(lastExecutionSql?.trim());

  return (
    <div className="exec-panel__header">
      <div className="exec-panel__header-left">
        <div className="exec-panel__header-icon">
          <FiTerminal size={12} />
        </div>
        <span className="exec-panel__title">Execution</span>
      </div>
      <div className="exec-panel__header-right">
        {showRerun && (
          <button
            type="button"
            className="exec-panel__rerun-btn"
            disabled={isRunning}
            title="Re-run the last executed SQL"
            onClick={() => void triggerExecution(lastExecutionSql ?? '')}
          >
            <FiRefreshCw
              size={11}
              className={isRunning ? 'exec-panel__rerun-icon--spin' : ''}
            />
            Re-run
          </button>
        )}
        <ExecutionStatus
          status={status}
          executionTimeMs={result?.metrics.executionTimeMs}
        />
      </div>
    </div>
  );
}

function MetricsBar() {
  const { result } = useExecutionContext();
  if (!result) return null;
  const { metrics } = result;

  return (
    <motion.div
      className="exec-metrics"
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.24, delay: 0.05 }}
    >
      <MetricChip icon={<FiDatabase size={10} />} label="rows returned" value={metrics.rowCount.toLocaleString()} accent="green" />
      <MetricChip icon={<FiClock size={10} />}    label="execution"     value={
        metrics.executionTimeMs < 1000
          ? `${metrics.executionTimeMs} ms`
          : `${(metrics.executionTimeMs / 1000).toFixed(2)} s`
      } accent="cyan" />
      <MetricChip icon={<FiDatabase size={10} />} label="estimated"     value={`~${metrics.estimatedRows.toLocaleString()} rows`} accent="purple" />
    </motion.div>
  );
}

type MetricAccent = 'blue' | 'green' | 'cyan' | 'purple' | 'orange';

interface MetricChipProps {
  icon:   React.ReactNode;
  label:  string;
  value:  string;
  accent: MetricAccent;
}

function MetricChip({ icon, label, value, accent }: MetricChipProps) {
  return (
    <div className={`exec-metric exec-metric--${accent}`}>
      <span className="exec-metric__icon">{icon}</span>
      <span className="exec-metric__value">{value}</span>
      <span className="exec-metric__label">{label}</span>
    </div>
  );
}

function IdleState() {
  return (
    <motion.div
      className="exec-panel__idle"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
    >
      <div className="exec-panel__idle-icon">
        <FiTerminal size={22} />
      </div>
      <p className="exec-panel__idle-title">No execution yet</p>
      <p className="exec-panel__idle-hint">
        Ask a question in the chat. When SQL is proposed, validate it and approve execution here.
      </p>
    </motion.div>
  );
}

function RunningState() {
  return (
    <motion.div
      className="exec-panel__running"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.22 }}
    >
      {/* Pulsing glow bar */}
      <motion.div
        className="exec-panel__run-glow"
        animate={{ opacity: [0.4, 1, 0.4], scaleX: [0.96, 1, 0.96] }}
        transition={{ duration: 1.6, repeat: Infinity, ease: 'easeInOut' }}
      />
      <p className="exec-panel__run-label">Executing query pipeline…</p>
      <div className="exec-panel__run-steps">
        {['Planning', 'Scanning tables', 'Applying filters', 'Aggregating', 'Sorting results'].map((step, i) => (
          <motion.span
            key={step}
            className="exec-panel__run-step"
            initial={{ opacity: 0, x: -6 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.22, duration: 0.28 }}
          >
            {step}
          </motion.span>
        ))}
      </div>
    </motion.div>
  );
}

function FailedState() {
  const { error } = useExecutionContext();
  return (
    <motion.div
      className="exec-panel__failed"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.26 }}
    >
      <FiAlertCircle size={18} className="exec-panel__failed-icon" />
      <p className="exec-panel__failed-title">Execution failed</p>
      <p className="exec-panel__failed-msg">{error ?? 'An unknown error occurred.'}</p>
    </motion.div>
  );
}

function formatPreviewPrice(price: MediaPreview['price']): string | null {
  if (price === null || price === undefined || price === '') return null;
  const numericPrice = typeof price === 'number' ? price : Number(price);
  if (!Number.isFinite(numericPrice)) return String(price);
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 2,
  }).format(numericPrice);
}

function MediaPreviewGrid({ items }: { items: MediaPreview[] }) {
  if (!items.length) return null;
  return (
    <section className="media-preview-grid" aria-label="Media previews">
      <div className="media-preview-grid__header">
        <span>Media previews</span>
        <small>{items.length} matched assets</small>
      </div>
      <div className="media-preview-grid__items">
        {items.map((item) => {
          const formattedPrice = formatPreviewPrice(item.price);
          return (
            <article key={item.asset_id} className="media-preview-card">
              {item.media_type === 'image' || item.media_type === 'video' ? (
                <img
                  src={item.preview_url ?? ''}
                  alt={item.caption ?? item.asset_id}
                  className="media-preview-card__visual"
                />
              ) : (
                <div className="media-preview-card__audio">
                  <span>Audio transcript</span>
                </div>
              )}
              <div className="media-preview-card__body">
                <strong>{item.asset_id}</strong>
                <span>{item.media_type} / score {item.score.toFixed(2)}</span>
                {formattedPrice && (
                  <span className="media-preview-card__price">{formattedPrice}</span>
                )}
                <p>{item.caption || item.transcript || 'No preview text available.'}</p>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Main panel
// ---------------------------------------------------------------------------

export function ExecutionPanel() {
  const { status, result } = useExecutionContext();

  return (
    <div className="exec-panel">
      <PanelHeader />

      <div className="exec-panel__body">
        <AnimatePresence mode="wait">

          {status === 'idle' && (
            <motion.div key="idle" className="exec-panel__state-wrap">
              <IdleState />
            </motion.div>
          )}

          {status === 'running' && (
            <motion.div
              key="running"
              className="exec-panel__state-wrap"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              <RunningState />
            </motion.div>
          )}

          {status === 'failed' && (
            <motion.div
              key="failed"
              className="exec-panel__state-wrap"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              <FailedState />
            </motion.div>
          )}

          {status === 'success' && result && (
            <div key="success" className="exec-panel__results">
              <MetricsBar />
              <SQLPreview sql={result.sql} />
              <MediaPreviewGrid items={result.mediaPreviews ?? []} />
              <ResultsTable columns={result.columns} rows={result.rows} />
            </div>
          )}

        </AnimatePresence>
      </div>
    </div>
  );
}
