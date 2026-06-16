import { useCallback, useEffect, useState } from 'react';
import { FiDatabase, FiRefreshCw, FiZap } from 'react-icons/fi';
import {
  getCapabilities,
  type CapabilitiesResponse,
  type CapabilityExample,
} from '../../services/api/capabilitiesApi';
import {
  getBenchmarkDatabases,
  getBenchmarks,
  type BenchmarkDatabaseInfo,
  type BenchmarkInfo,
} from '../../services/api/benchmarkApi';
import { useDatasetContext } from '../../store/DatasetContext';
import './CapabilitiesPanel.css';

interface CapabilitiesPanelProps {
  onExampleSelect?: (example: CapabilityExample) => void;
}

export function CapabilitiesPanel({ onExampleSelect }: CapabilitiesPanelProps) {
  const { selection, setDbType, setBenchmark, setDbId } = useDatasetContext();
  const [benchmarks, setBenchmarks] = useState<BenchmarkInfo[]>([]);
  const [databases, setDatabases] = useState<BenchmarkDatabaseInfo[]>([]);
  const [capabilities, setCapabilities] = useState<CapabilitiesResponse | null>(null);
  const [status, setStatus] = useState<'idle' | 'loading' | 'error'>('idle');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getBenchmarks()
      .then(setBenchmarks)
      .catch(() => setBenchmarks([]));
  }, []);

  useEffect(() => {
    if (selection.dbType !== 'sqlite_benchmark') return;
    getBenchmarkDatabases(selection.benchmark)
      .then((items) => {
        setDatabases(items);
        if (!selection.dbId && items.length > 0) {
          setDbId(items.find((item) => item.hasSQLite)?.dbId || items[0].dbId);
        }
      })
      .catch(() => setDatabases([]));
  }, [selection.benchmark, selection.dbId, selection.dbType, setDbId]);

  const loadCapabilities = useCallback(async () => {
    if (selection.dbType === 'sqlite_benchmark' && !selection.dbId) {
      setCapabilities(null);
      return;
    }
    setStatus('loading');
    setError(null);
    try {
      const payload = await getCapabilities({
        dbType: selection.dbType,
        benchmark: selection.dbType === 'sqlite_benchmark' ? selection.benchmark : undefined,
        dbId: selection.dbType === 'sqlite_benchmark' ? selection.dbId : undefined,
      });
      setCapabilities(payload);
      setStatus('idle');
    } catch (err) {
      setStatus('error');
      setError(err instanceof Error ? err.message : 'Failed to load capabilities');
    }
  }, [selection.benchmark, selection.dbId, selection.dbType]);

  useEffect(() => {
    void loadCapabilities();
  }, [loadCapabilities]);

  const tables = (capabilities?.schemaPreview?.tables as Array<{ name: string; columns?: Array<{ name: string }> }>) ?? [];
  const relationships = (capabilities?.schemaPreview?.relationships as Array<Record<string, string>>) ?? [];

  return (
    <div className="capabilities-panel">
      <header className="capabilities-panel__header">
        <div className="capabilities-panel__title">
          <FiDatabase size={14} />
          <span>Capabilities Explorer</span>
        </div>
        <button type="button" className="capabilities-panel__refresh" onClick={() => void loadCapabilities()}>
          <FiRefreshCw size={12} />
          Refresh
        </button>
      </header>

      <section className="capabilities-panel__context">
        <label>
          <span>Database type</span>
          <select
            value={selection.dbType}
            onChange={(event) => setDbType(event.target.value as 'sqlite_benchmark' | 'postgres')}
          >
            <option value="sqlite_benchmark">Benchmark SQLite</option>
            <option value="postgres">PostgreSQL</option>
          </select>
        </label>

        {selection.dbType === 'sqlite_benchmark' && (
          <>
            <label>
              <span>Benchmark</span>
              <select value={selection.benchmark} onChange={(event) => setBenchmark(event.target.value)}>
                {(benchmarks.length > 0 ? benchmarks : [{ id: selection.benchmark, label: selection.benchmark }]).map(
                  (item) => (
                    <option key={item.id} value={item.id}>
                      {item.label}
                    </option>
                  ),
                )}
              </select>
            </label>
            <label>
              <span>Database</span>
              <select value={selection.dbId} onChange={(event) => setDbId(event.target.value)}>
                {databases.map((database) => (
                  <option key={database.dbId} value={database.dbId}>
                    {database.dbId}
                  </option>
                ))}
              </select>
            </label>
          </>
        )}
      </section>

      {status === 'loading' && <p className="capabilities-panel__status">Loading capabilities...</p>}
      {status === 'error' && <p className="capabilities-panel__status capabilities-panel__status--error">{error}</p>}

      {capabilities && (
        <div className="capabilities-panel__body">
          <section className="capabilities-section">
            <h3>What you can see</h3>
            <p className="capabilities-section__meta">
              {capabilities.connector.label} · {tables.length} tables · read-only
            </p>
            <div className="capabilities-tables">
              {tables.map((table) => (
                <article key={table.name} className="capabilities-table-card">
                  <strong>{table.name}</strong>
                  <span>{table.columns?.length ?? 0} columns</span>
                  <ul>
                    {(table.columns ?? []).slice(0, 6).map((column) => (
                      <li key={column.name}>{column.name}</li>
                    ))}
                  </ul>
                </article>
              ))}
            </div>
            {relationships.length > 0 && (
              <div className="capabilities-relationships">
                <h4>Relationships</h4>
                <ul>
                  {relationships.slice(0, 8).map((rel, index) => (
                    <li key={`${rel.fromTable}-${index}`}>
                      {rel.fromTable}.{rel.fromColumn} → {rel.toTable}.{rel.toColumn}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </section>

          <section className="capabilities-section">
            <h3>What you can execute</h3>
            <ul className="capabilities-policies">
              <li>Read-only SELECT/WITH queries only</li>
              <li>Max rows: {capabilities.policies.maxRows as number}</li>
              <li>Sample rows: {capabilities.policies.maxSampleRows as number}</li>
            </ul>
            <div className="capabilities-tools">
              {capabilities.tools.map((tool) => (
                <span key={tool.name} className="capabilities-tool-chip">
                  {tool.label}
                  {tool.requiresApproval ? ' (approval)' : ''}
                </span>
              ))}
            </div>
          </section>

          <section className="capabilities-section">
            <h3>Examples</h3>
            <div className="capabilities-examples">
              {capabilities.examples.map((example) => (
                <button
                  key={example.id}
                  type="button"
                  className="capabilities-example"
                  onClick={() => onExampleSelect?.(example)}
                >
                  <span className="capabilities-example__label">
                    <FiZap size={11} />
                    {example.label}
                  </span>
                  <span className="capabilities-example__content">{example.content}</span>
                </button>
              ))}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
