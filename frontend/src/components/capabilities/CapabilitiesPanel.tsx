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

const SQLITE_BENCHMARK_IDS = new Set(['spider', 'bird']);
const FALLBACK_SQLITE_BENCHMARKS: BenchmarkInfo[] = [
  { id: 'spider', label: 'Spider', status: 'ready', databaseCount: 0 },
  { id: 'bird', label: 'BIRD', status: 'ready', databaseCount: 0 },
];

function isSqliteBenchmarkOption(item: BenchmarkInfo): boolean {
  return SQLITE_BENCHMARK_IDS.has(item.id.toLowerCase());
}

export function CapabilitiesPanel({ onExampleSelect }: CapabilitiesPanelProps) {
  const { selection, setDbType, setBenchmark, setDbId } = useDatasetContext();
  const [benchmarks, setBenchmarks] = useState<BenchmarkInfo[]>([]);
  const [databases, setDatabases] = useState<BenchmarkDatabaseInfo[]>([]);
  const [capabilities, setCapabilities] = useState<CapabilitiesResponse | null>(null);
  const [status, setStatus] = useState<'idle' | 'loading' | 'error'>('idle');
  const [error, setError] = useState<string | null>(null);
  const isMultimodal = selection.dbType === 'multimodal_demo' || selection.benchmark === 'multimodal_demo';
  const isCraigslist = selection.dbType === 'craigslist' || selection.benchmark === 'craigslist';
  const isFixedDataset = isMultimodal || isCraigslist;
  const effectiveDbType = isMultimodal ? 'multimodal_demo' : isCraigslist ? 'craigslist' : selection.dbType;
  const effectiveBenchmark = isFixedDataset ? selection.benchmark : selection.benchmark;
  const effectiveDbId = isFixedDataset ? selection.benchmark : selection.dbId;

  useEffect(() => {
    getBenchmarks()
      .then(setBenchmarks)
      .catch(() => setBenchmarks([]));
  }, []);

  useEffect(() => {
    const benchmarkToLoad = isFixedDataset
      ? selection.benchmark
      : selection.dbType === 'sqlite_benchmark'
        ? selection.benchmark
        : null;
    if (!benchmarkToLoad) {
      setDatabases([]);
      return;
    }
    let cancelled = false;
    getBenchmarkDatabases(benchmarkToLoad)
      .then((items) => {
        if (cancelled) return;
        setDatabases(items);
        if (isFixedDataset) {
          setDbId(items[0]?.dbId || selection.benchmark);
        } else if (!selection.dbId && items.length > 0) {
          setDbId(items.find((item) => item.hasSQLite)?.dbId || items[0].dbId);
        }
      })
      .catch(() => {
        if (!cancelled) setDatabases([]);
      });
    return () => {
      cancelled = true;
    };
  }, [isFixedDataset, selection.benchmark, selection.dbId, selection.dbType, setDbId]);

  const loadCapabilities = useCallback(async () => {
    if (!isFixedDataset && selection.dbType === 'sqlite_benchmark' && !selection.dbId) {
      setCapabilities(null);
      return;
    }
    setStatus('loading');
    setError(null);
    try {
      const payload = await getCapabilities({
        dbType: effectiveDbType,
        benchmark: isFixedDataset ? selection.benchmark : selection.dbType === 'sqlite_benchmark' ? selection.benchmark : undefined,
        dbId: isFixedDataset ? selection.benchmark : selection.dbType === 'sqlite_benchmark' ? selection.dbId : undefined,
      });
      setCapabilities(payload);
      setStatus('idle');
    } catch (err) {
      setStatus('error');
      setError(err instanceof Error ? err.message : 'Failed to load capabilities');
    }
  }, [effectiveDbType, isFixedDataset, selection.benchmark, selection.dbId, selection.dbType]);

  useEffect(() => {
    void loadCapabilities();
  }, [loadCapabilities]);

  const tables = (capabilities?.schemaPreview?.tables as Array<{ name: string; columns?: Array<{ name: string }> }>) ?? [];
  const relationships = (capabilities?.schemaPreview?.relationships as Array<Record<string, string>>) ?? [];
  const mediaTypes = (capabilities?.schemaPreview?.mediaTypes as Array<{ type: string; count: number }>) ?? [];
  const sqliteBenchmarks = benchmarks.filter(isSqliteBenchmarkOption);

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
            value={effectiveDbType}
            onChange={(event) => {
              const nextDbType = event.target.value as 'sqlite_benchmark' | 'postgres' | 'multimodal_demo' | 'craigslist';
              setDbType(nextDbType);
              if (nextDbType === 'multimodal_demo') {
                setBenchmark('multimodal_demo');
                setDbId('multimodal_demo');
              } else if (nextDbType === 'craigslist') {
                setBenchmark('craigslist');
                setDbId('craigslist');
              } else if (nextDbType === 'sqlite_benchmark' && ['multimodal_demo', 'craigslist'].includes(selection.benchmark)) {
                setBenchmark('spider');
                setDbId('');
              }
            }}
          >
            <option value="sqlite_benchmark">Benchmark SQLite</option>
            <option value="multimodal_demo">Multimodal Demo</option>
            <option value="craigslist">Craigslist Furniture</option>
            <option value="postgres">PostgreSQL</option>
          </select>
        </label>

        {effectiveDbType === 'sqlite_benchmark' && (
          <>
            <label>
              <span>Benchmark</span>
              <select
                value={effectiveBenchmark}
                onChange={(event) => {
                  const nextBenchmark = event.target.value;
                  setDbType('sqlite_benchmark');
                  setBenchmark(nextBenchmark);
                }}
              >
                {(sqliteBenchmarks.length > 0 ? sqliteBenchmarks : FALLBACK_SQLITE_BENCHMARKS).map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.label}
                    </option>
                  ))}
              </select>
            </label>
            <label>
              <span>Database</span>
              <select
                value={effectiveDbId}
                onChange={(event) => setDbId(event.target.value)}
                disabled={isMultimodal}
              >
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
          <section className="capabilities-section capabilities-section--guide">
            <h3>How to use this</h3>
            <ol className="capabilities-guide">
              <li>Review the tables and media types available in this dataset.</li>
              <li>Click an example below or ask a question in the chat panel.</li>
              <li>Validate the proposed SQL, then approve execution to see real results.</li>
            </ol>
          </section>

          {(capabilities.capabilityLabels?.length ?? 0) > 0 && (
            <section className="capabilities-section">
              <h3>This benchmark supports</h3>
              <ul className="capabilities-support-list">
                {capabilities.capabilityLabels!.map((label) => (
                  <li key={label}>{label}</li>
                ))}
              </ul>
            </section>
          )}
          <section className="capabilities-section">
            <h3>What you can see</h3>
            <p className="capabilities-section__meta">
              {capabilities.connector.label} · {tables.length} tables · read-only
            </p>
            {mediaTypes.length > 0 && (
              <div className="capabilities-media">
                {mediaTypes.map((item) => (
                  <span key={item.type} className="capabilities-media__chip">
                    {item.type}: {item.count}
                  </span>
                ))}
              </div>
            )}
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
