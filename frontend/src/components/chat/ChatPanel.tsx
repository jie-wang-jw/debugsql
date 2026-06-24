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
  const { selection, setBenchmark, setDbId } = useDatasetContext();
  const bottomRef = useRef<HTMLDivElement>(null);
  const { restoreExecution } = useExecutionContext();

  const datasetContext =
    selection.dbType === 'postgres'
      ? { dbType: 'postgres' as const }
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
        const preferred =
          items.find((item) => item.status === 'ready' && item.id === 'spider') ??
          items.find((item) => item.status === 'ready') ??
          items[0];
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
    if (selection.dbType !== 'sqlite_benchmark') return;
    let isMounted = true;
    getBenchmarkDatabases(selection.benchmark)
      .then((items) => {
        if (!isMounted) return;
        setDatabases(items);
        if (!selection.dbId) {
          setDbId(items.find((item) => item.hasSQLite)?.dbId || items[0]?.dbId || '');
        }
      })
      .catch(() => {
        if (isMounted) setDatabases([]);
      });
    return () => {
      isMounted = false;
    };
  }, [selection.benchmark, selection.dbId, selection.dbType, setDbId]);

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
      { sql, columns, rows, metrics, rowCount: metrics.rowCount },
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

  return (
    <div className="chat-panel">
      <ChatHeader status={status} />
      {selection.dbType === 'sqlite_benchmark' && (
        <DatasetSelector
          benchmarks={benchmarks}
          benchmark={selection.benchmark}
          onBenchmarkChange={setBenchmark}
          databases={databases}
          selectedDbId={selection.dbId}
          onDbChange={setDbId}
        />
      )}

      <div className="chat-panel__messages" role="log" aria-label="Conversation" aria-live="polite">
        <AnimatePresence mode="wait">
          {isEmpty ? (
            <SuggestedPrompts
              key={`suggestions-${selection.dbId}`}
              prompts={databasePrompts}
              databaseLabel={selection.dbId || 'database'}
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
  onBenchmarkChange: (benchmark: string) => void;
  databases: BenchmarkDatabaseInfo[];
  selectedDbId: string;
  onDbChange: (dbId: string) => void;
}

function DatasetSelector({
  benchmarks,
  benchmark,
  onBenchmarkChange,
  databases,
  selectedDbId,
  onDbChange,
}: DatasetSelectorProps) {
  const selected = databases.find((item) => item.dbId === selectedDbId);
  const localDbCount = databases.filter((item) => item.hasSQLite).length;
  const missingSqlite = Boolean(selected && !selected.hasSQLite);

  return (
    <div className="dataset-selector-wrap">
      <div className="dataset-selector">
        <label className="dataset-selector__field">
          <span className="dataset-selector__label">Benchmark</span>
          <select
            className="dataset-selector__select"
            value={benchmark}
            onChange={(event) => onBenchmarkChange(event.target.value)}
          >
            {(benchmarks.length > 0 ? benchmarks : [{ id: benchmark, label: benchmark }]).map(
              (item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                  {'status' in item && item.status !== 'ready' ? ` (${item.status})` : ''}
                </option>
              ),
            )}
          </select>
        </label>
        <label className="dataset-selector__field">
          <span className="dataset-selector__label">Database</span>
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
        </label>
        <span className="dataset-selector__meta">
          {selected
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
