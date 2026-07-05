import { useState, useRef, useEffect, useCallback } from 'react';
import { AnimatePresence } from 'framer-motion';
import type { ChatMessage, ChatStatus, SuggestedPrompt } from './chat.types';
import { ChatHeader } from './ChatHeader';
import { ChatMessage as ChatMessageItem } from './ChatMessage';
import { ChatInput } from './ChatInput';
import { TypingIndicator } from './TypingIndicator';
import { SuggestedPrompts } from './SuggestedPrompts';
import { ProposedActions } from './ProposedActions';
import { sendChatMessage } from '../../services/adapters/chatAdapter';
import {
  getBenchmarkDatabases,
  getBenchmarks,
  type BenchmarkDatabaseInfo,
  type BenchmarkInfo,
} from '../../services/api/benchmarkApi';
import {
  getHistoryConversation,
  getHistorySummary,
  type HistoryConversationSummary,
} from '../../services/api/historyApi';
import { useExecutionContext } from '../../store/ExecutionContext';
import { useDatasetContext } from '../../store/DatasetContext';
import { generateId } from '../../utils';
import type { ExecutionResult, ExecutionResultPreview } from '../../types/execution.types';
import './ChatPanel.css';

const INITIAL_MESSAGES: ChatMessage[] = [];
const HISTORY_SUMMARY_LIMIT = 20;
const SQLITE_BENCHMARK_IDS = new Set(['spider', 'bird']);
const FALLBACK_SQLITE_BENCHMARKS: BenchmarkInfo[] = [
  { id: 'spider', label: 'Spider', status: 'ready', databaseCount: 0 },
  { id: 'bird', label: 'BIRD', status: 'ready', databaseCount: 0 },
];

function isSqliteBenchmarkOption(item: BenchmarkInfo): boolean {
  return SQLITE_BENCHMARK_IDS.has(item.id.toLowerCase());
}

interface ChatPanelProps {
  onPromptFromExplorer?: (content: string) => void;
  externalPrompt?: string | null;
  onExternalPromptConsumed?: () => void;
}

/**
 * Left-panel AI chat orchestrator with tool-assisted actions.
 */
export function ChatPanel({
  onPromptFromExplorer,
  externalPrompt,
  onExternalPromptConsumed,
}: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>(INITIAL_MESSAGES);
  const [status, setStatus] = useState<ChatStatus>('idle');
  const [sessionId, setSessionId] = useState(() => `session-${Date.now()}`);
  const [historyItems, setHistoryItems] = useState<HistoryConversationSummary[]>([]);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyStatus, setHistoryStatus] = useState<'idle' | 'loading' | 'error'>('idle');
  const [historyHasMore, setHistoryHasMore] = useState(false);
  const [benchmarks, setBenchmarks] = useState<BenchmarkInfo[]>([]);
  const [databases, setDatabases] = useState<BenchmarkDatabaseInfo[]>([]);
  const { selection, setDbType, setBenchmark, setDbId } = useDatasetContext();
  const bottomRef = useRef<HTMLDivElement>(null);
  const { restoreExecution } = useExecutionContext();

  const datasetContext =
    selection.dbType === 'postgres'
      ? { dbType: 'postgres' as const }
      : selection.dbType === 'multimodal_demo'
        ? { dbType: 'multimodal_demo' as const, dbId: 'multimodal_demo' }
      : selection.dbId
        ? { dbType: 'sqlite_benchmark' as const, benchmark: selection.benchmark, dbId: selection.dbId }
        : undefined;

  const refreshHistory = useCallback(async () => {
    setHistoryStatus('loading');
    try {
      const summary = await getHistorySummary({ limit: HISTORY_SUMMARY_LIMIT, offset: 0 });
      setHistoryItems(summary.conversations);
      setHistoryHasMore(Boolean(summary.pagination?.hasMoreConversations));
      setHistoryStatus('idle');
    } catch {
      setHistoryStatus('error');
    }
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, status]);

  useEffect(() => {
    void refreshHistory();
  }, [refreshHistory]);

  useEffect(() => {
    let isMounted = true;
    getBenchmarks()
      .then((items) => {
        if (!isMounted) return;
        setBenchmarks(items);
        const sqliteItems = items.filter(isSqliteBenchmarkOption);
        const preferred =
          sqliteItems.find((item) => item.status === 'ready' && item.id === 'spider') ??
          sqliteItems.find((item) => item.status === 'ready') ??
          sqliteItems[0];
        if (preferred && !selection.benchmark) {
          setBenchmark(preferred.id);
        }
      })
      .catch(() => {
        if (isMounted) setBenchmarks([]);
      });
    return () => {
      isMounted = false;
    };
  }, [selection.benchmark, setBenchmark]);

  useEffect(() => {
    if (selection.dbType === 'sqlite_benchmark' && selection.benchmark === 'multimodal_demo') {
      setDbType('multimodal_demo');
      setDbId('multimodal_demo');
      return;
    }
    const benchmarkToLoad =
      selection.dbType === 'multimodal_demo'
        ? 'multimodal_demo'
        : selection.dbType === 'sqlite_benchmark'
          ? selection.benchmark
          : null;
    if (!benchmarkToLoad) {
      setDatabases([]);
      return;
    }
    let isMounted = true;
    getBenchmarkDatabases(benchmarkToLoad)
      .then((items) => {
        if (!isMounted) return;
        setDatabases(items);
        if (selection.dbType === 'multimodal_demo') {
          setDbId(items[0]?.dbId || 'multimodal_demo');
        } else if (!selection.dbId) {
          setDbId(items.find((item) => item.hasSQLite)?.dbId || items[0]?.dbId || '');
        }
      })
      .catch(() => {
        if (isMounted) setDatabases([]);
      });
    return () => {
      isMounted = false;
    };
  }, [selection.benchmark, selection.dbId, selection.dbType, setDbId, setDbType]);

  const applyExecutionResult = useCallback((sql: string, data: Record<string, unknown>) => {
    const columns = (data.columns as ExecutionResult['columns']) ?? [];
    const rows = (data.rows as ExecutionResult['rows']) ?? [];
    const metrics = (data.metrics as ExecutionResult['metrics']) ?? {
      planningTimeMs: 0,
      executionTimeMs: 0,
      rowCount: rows.length,
      estimatedRows: rows.length,
    };
    restoreExecution(
      {
        sql,
        columns,
        rows,
        metrics,
        rowCount: metrics.rowCount,
        mediaPreviews: (data.mediaPreviews as ExecutionResult['mediaPreviews']) ?? [],
      },
      'success',
    );
  }, [restoreExecution]);

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || status === 'thinking') return;

      const userMsg: ChatMessage = {
        id: generateId(),
        role: 'user',
        content: trimmed,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, userMsg]);
      setStatus('thinking');

      try {
        const response = await sendChatMessage({
          message: trimmed,
          sessionId,
          datasetContext,
        });

        const aiMsg: ChatMessage = {
          id: generateId(),
          role: 'assistant',
          content: response.content,
          timestamp: new Date(),
          proposedActions: response.proposedActions ?? [],
          confidence: response.confidence,
          assumptions: response.assumptions ?? [],
          tablesUsed: response.tablesUsed ?? [],
          usedContext: response.usedContext,
          conversationMode: response.conversationMode,
          workingStateRevision: response.workingStateRevision,
          mediaMatches: response.mediaMatches ?? [],
          mediaPredicate: response.mediaPredicate,
          mediaType: response.mediaType,
          mediaLimit: response.mediaLimit,
        };
        setMessages((prev) => [...prev, aiMsg]);
        void refreshHistory();
      } catch (error) {
        console.error('Chat request failed', error);
        const detail = error instanceof Error ? error.message : 'Unknown client error';
        const errorMsg: ChatMessage = {
          id: generateId(),
          role: 'assistant',
          content: `Something went wrong while processing your request.\n\n${detail}`,
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, errorMsg]);
        setStatus('error');
        return;
      }

      setStatus('idle');
    },
    [datasetContext, refreshHistory, sessionId, status],
  );

  useEffect(() => {
    if (!externalPrompt?.trim()) return;
    void sendMessage(externalPrompt);
    onExternalPromptConsumed?.();
  }, [externalPrompt, onExternalPromptConsumed, sendMessage]);

  const handleActionResult = useCallback((messageId: string, actionId: string, summary: string) => {
    setMessages((prev) =>
      prev.map((message) =>
        message.id === messageId
          ? {
              ...message,
              actionResults: { ...(message.actionResults ?? {}), [actionId]: summary },
            }
          : message,
      ),
    );
  }, []);

  const appendAssistantResult = useCallback((content: string) => {
    const trimmed = content.trim();
    if (!trimmed) return;
    setMessages((prev) => [
      ...prev,
      {
        id: generateId(),
        role: 'assistant',
        content: trimmed,
        timestamp: new Date(),
      },
    ]);
  }, []);

  const startNewConversation = useCallback(() => {
    setSessionId(`session-${Date.now()}`);
    setMessages([]);
    setStatus('idle');
  }, []);

  const loadHistoryConversation = useCallback(
    async (conversationId: string) => {
      setHistoryStatus('loading');
      try {
        const detail = await getHistoryConversation(conversationId);
        setSessionId(detail.sessionId);
        const latestSummary = detail.latestExecutionResultPreview
          ? summarizeRestoredExecution(detail.latestExecutionResultPreview)
          : null;
        setMessages(
          detail.messages.map((message) => ({
            id: message.id,
            role: message.role,
            content: message.content,
            timestamp: new Date(message.timestamp),
            proposedActions: message.proposedActions ?? [],
            confidence: message.confidence,
            assumptions: message.assumptions ?? [],
            tablesUsed: message.tablesUsed ?? [],
            usedContext: message.usedContext,
            conversationMode: message.conversationMode,
            workingStateRevision: message.workingStateRevision,
            mediaMatches: message.mediaMatches ?? [],
            mediaPredicate: message.mediaPredicate,
            mediaType: message.mediaType,
            mediaLimit: message.mediaLimit,
            actionResults: buildRestoredActionResults(message.proposedActions, latestSummary),
          })),
        );
        if (detail.datasetContext?.benchmark) {
          setBenchmark(detail.datasetContext.benchmark);
        }
        if (detail.datasetContext?.dbId) {
          setDbId(detail.datasetContext.dbId);
        }
        restoreExecution(detail.latestExecutionResultPreview, detail.latestExecutionStatus);
        setHistoryStatus('idle');
      } catch {
        setHistoryStatus('error');
      }
    },
    [restoreExecution, setBenchmark, setDbId],
  );

  const isEmpty = messages.length === 0 && status === 'idle';
  const selectedDatabase = databases.find((item) => item.dbId === selection.dbId);
  const databasePrompts: SuggestedPrompt[] = (selectedDatabase?.sampleQuestions ?? []).map((item, index) => ({
    id: `${selection.dbId}-${index}`,
    label: `Question ${index + 1}`,
    description: item.question,
    icon: 'question',
  }));
  const multimodalPrompts: SuggestedPrompt[] = [
    {
      id: 'multimodal-image',
      label: 'Find matching images',
      description: 'Find red cars with sporty-looking images',
      icon: 'question',
    },
    {
      id: 'multimodal-audio',
      label: 'Search audio transcripts',
      description: 'Show audio clips mentioning engine noise',
      icon: 'question',
    },
    {
      id: 'multimodal-video',
      label: 'Search video evidence',
      description: 'Find videos with a red car in the frame',
      icon: 'question',
    },
    {
      id: 'multimodal-join',
      label: 'Combine SQL and media',
      description: 'Find cars under 30000 dollars with red exterior images',
      icon: 'question',
    },
  ];
  const prompts = selection.dbType === 'multimodal_demo' ? multimodalPrompts : databasePrompts;
  const isMultimodal = selection.dbType === 'multimodal_demo';

  return (
    <div className="chat-panel">
      <ChatHeader status={status} />
      {(selection.dbType === 'sqlite_benchmark' || selection.dbType === 'multimodal_demo') && (
        <DatasetSelector
          benchmarks={benchmarks}
          benchmark={selection.dbType === 'multimodal_demo' ? 'multimodal_demo' : selection.benchmark}
          onDbTypeChange={setDbType}
          onBenchmarkChange={setBenchmark}
          databases={databases}
          selectedDbId={selection.dbType === 'multimodal_demo' ? 'multimodal_demo' : selection.dbId}
          onDbChange={setDbId}
          isMultimodal={selection.dbType === 'multimodal_demo'}
        />
      )}

      <div className="chat-panel__messages" role="log" aria-label="Conversation" aria-live="polite">
        <AnimatePresence mode="wait">
          {isEmpty ? (
            <SuggestedPrompts
              key={`suggestions-${selection.dbType}-${selection.dbId}`}
              prompts={prompts}
              databaseLabel={isMultimodal ? 'Multimodal Demo' : selection.dbId || 'database'}
              title={isMultimodal ? 'Ask across tables and media' : 'Ask a data question'}
              description={
                isMultimodal ? (
                  <>
                    Ask for records using normal fields and image, audio, or video meaning.<br />
                    I will prepare a safe query and ask before running it.
                  </>
                ) : undefined
              }
              sectionLabel={isMultimodal ? 'Try a multimodal query' : undefined}
              onSelect={(prompt) => {
                onPromptFromExplorer?.(prompt);
                void sendMessage(prompt);
              }}
            />
          ) : (
            <div key="messages" className="chat-panel__message-list">
              {messages.map((msg, i) => (
                <div key={msg.id}>
                  <ChatMessageItem
                    message={msg}
                    isLatest={i === messages.length - 1 && status === 'idle'}
                  />
                  {msg.proposedActions && msg.proposedActions.length > 0 && (
                    <ProposedActions
                      actions={msg.proposedActions}
                      datasetContext={datasetContext}
                      sessionId={sessionId}
                      onResult={(actionId, summary) => handleActionResult(msg.id, actionId, summary)}
                      onAssistantFollowup={appendAssistantResult}
                      onExecutionResult={applyExecutionResult}
                    />
                  )}
                  {msg.actionResults && (
                    <div className="chat-panel__action-results">
                      {Object.entries(msg.actionResults).map(([actionId, summary]) => (
                        <p key={actionId}>{summary}</p>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </AnimatePresence>

        <AnimatePresence>
          {status === 'thinking' && <TypingIndicator key="typing" />}
        </AnimatePresence>

        <div ref={bottomRef} />
      </div>

      <HistoryPanel
        isOpen={historyOpen}
        items={historyItems}
        status={historyStatus}
        hasMore={historyHasMore}
        limit={HISTORY_SUMMARY_LIMIT}
        onToggle={() => setHistoryOpen((value) => !value)}
        onRefresh={refreshHistory}
        onNew={startNewConversation}
        onSelect={loadHistoryConversation}
      />
      <ChatInput onSend={sendMessage} isDisabled={status === 'thinking'} />
    </div>
  );
}

function summarizeRestoredExecution(preview: ExecutionResultPreview | null | undefined): string | null {
  if (!preview) return null;
  const rows = Array.isArray(preview.rows) ? preview.rows : [];
  const rowCount = preview.metrics?.rowCount ?? preview.rowCount ?? rows.length;
  return `Previous execution result restored. The query returned ${rowCount} rows.`;
}

function buildRestoredActionResults(
  actions: import('../../services/api/chatApi').ProposedToolAction[] | undefined,
  latestSummary: string | null,
): Record<string, string> | undefined {
  if (!latestSummary || !actions?.length) return undefined;
  const runAction = actions.find((action) => action.tool === 'run_sql');
  return runAction ? { [runAction.id]: latestSummary } : undefined;
}

interface HistoryPanelProps {
  isOpen: boolean;
  items: HistoryConversationSummary[];
  status: 'idle' | 'loading' | 'error';
  hasMore: boolean;
  limit: number;
  onToggle: () => void;
  onRefresh: () => void;
  onNew: () => void;
  onSelect: (conversationId: string) => void;
}

function HistoryPanel({
  isOpen,
  items,
  status,
  hasMore,
  limit,
  onToggle,
  onRefresh,
  onNew,
  onSelect,
}: HistoryPanelProps) {
  return (
    <section className="history-panel">
      <div className="history-panel__header">
        <button className="history-panel__toggle" type="button" onClick={onToggle}>
          History {isOpen ? '-' : '+'}
        </button>
        <div className="history-panel__actions">
          <button type="button" onClick={onNew}>New</button>
          <button type="button" onClick={onRefresh}>Refresh</button>
        </div>
      </div>
      {isOpen && (
        <div className="history-panel__list">
          {status === 'loading' && <p className="history-panel__empty">Loading history...</p>}
          {status === 'error' && <p className="history-panel__empty">History unavailable.</p>}
          {status === 'idle' && items.length === 0 && (
            <p className="history-panel__empty">No saved conversations yet.</p>
          )}
          {status !== 'loading' && items.map((item) => (
            <button
              className="history-panel__item"
              type="button"
              key={item.id}
              onClick={() => onSelect(item.id)}
            >
              <span>{item.title || 'Untitled conversation'}</span>
              <small>{new Date(item.updatedAt).toLocaleString()}</small>
            </button>
          ))}
          {status === 'idle' && hasMore && (
            <p className="history-panel__empty">
              Showing latest {limit}. Older conversations stay saved.
            </p>
          )}
        </div>
      )}
    </section>
  );
}

interface DatasetSelectorProps {
  benchmarks: BenchmarkInfo[];
  benchmark: string;
  onDbTypeChange: (dbType: 'sqlite_benchmark' | 'postgres' | 'multimodal_demo') => void;
  onBenchmarkChange: (benchmark: string) => void;
  databases: BenchmarkDatabaseInfo[];
  selectedDbId: string;
  onDbChange: (dbId: string) => void;
  isMultimodal?: boolean;
}

function DatasetSelector({
  benchmarks,
  benchmark,
  onDbTypeChange,
  onBenchmarkChange,
  databases,
  selectedDbId,
  onDbChange,
  isMultimodal = false,
}: DatasetSelectorProps) {
  const selected = databases.find((item) => item.dbId === selectedDbId);
  const localDbCount = databases.filter((item) => item.hasSQLite).length;
  const missingSqlite = Boolean(selected && !selected.hasSQLite);
  const sqliteBenchmarks = benchmarks.filter(isSqliteBenchmarkOption);
  const benchmarkOptions = [
    { id: 'multimodal_demo', label: 'Multimodal Demo' },
    ...(sqliteBenchmarks.length > 0 ? sqliteBenchmarks : FALLBACK_SQLITE_BENCHMARKS),
  ];
  const multimodalBenchmark = benchmarks.find((item) => item.id === 'multimodal_demo');
  const multimodalMediaCounts = multimodalBenchmark?.extra?.mediaCounts as
    | Record<string, number>
    | undefined;
  const multimodalMeta = multimodalMediaCounts
    ? `${selected?.tableCount ?? 2} tables · ${Object.entries(multimodalMediaCounts)
        .map(([type, count]) => `${count} ${type}`)
        .join(' · ')}`
    : `${selected?.tableCount ?? 2} tables · image/audio/video`;

  return (
    <div className="dataset-selector-wrap">
      <div className="dataset-selector">
        <label className="dataset-selector__field">
          <span className="dataset-selector__label">Benchmark</span>
          <select
            className="dataset-selector__select"
            value={benchmark}
            onChange={(event) => {
              const nextBenchmark = event.target.value;
              if (nextBenchmark === 'multimodal_demo') {
                onDbTypeChange('multimodal_demo');
                onBenchmarkChange('multimodal_demo');
                onDbChange('multimodal_demo');
              } else {
                onDbTypeChange('sqlite_benchmark');
                onBenchmarkChange(nextBenchmark);
                onDbChange('');
              }
            }}
          >
            {benchmarkOptions.map((item) => (
              <option key={item.id} value={item.id}>
                {item.label}
                {'status' in item && item.status !== 'ready' ? ` (${item.status})` : ''}
              </option>
            ))}
          </select>
        </label>
        <label className="dataset-selector__field">
          <span className="dataset-selector__label">Database</span>
          {isMultimodal ? (
            <span className="dataset-selector__pill">{selected?.dbId || 'multimodal_demo'}</span>
          ) : (
            <select
              className="dataset-selector__select"
              value={selectedDbId}
              onChange={(event) => onDbChange(event.target.value)}
            >
              {databases.map((database) => (
                <option key={database.dbId} value={database.dbId}>
                  {database.dbId}
                  {database.hasSQLite ? '' : ' (no local DB)'}
                </option>
              ))}
            </select>
          )}
        </label>
        <span className="dataset-selector__meta">
          {isMultimodal
            ? multimodalMeta
            : selected
              ? `${selected.tableCount} tables · ${localDbCount}/${databases.length} local`
              : 'loading'}
        </span>
      </div>
      {missingSqlite && (
        <p className="dataset-selector__warning" role="status">
          No local SQLite for <strong>{selectedDbId}</strong>. Copy BIRD{' '}
          <code>dev_databases/</code> into <code>data/benchmarks/bird/sqlite/</code> (see README).
        </p>
      )}
    </div>
  );
}
