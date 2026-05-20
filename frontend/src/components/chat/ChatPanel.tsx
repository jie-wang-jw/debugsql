import { useState, useRef, useEffect, useCallback } from 'react';
import { AnimatePresence } from 'framer-motion';
import type { ChatMessage, ChatStatus, SuggestedPrompt } from './chat.types';
import { ChatHeader } from './ChatHeader';
import { ChatMessage as ChatMessageItem } from './ChatMessage';
import { ChatInput } from './ChatInput';
import { TypingIndicator } from './TypingIndicator';
import { SuggestedPrompts } from './SuggestedPrompts';
import { sendChatMessage } from '../../services/adapters/chatAdapter';
import {
  getBenchmarkDatabases,
  type BenchmarkDatabaseInfo,
} from '../../services/api/benchmarkApi';
import { useExecutionContext } from '../../store/ExecutionContext';
import { useQueryPlanContext } from '../../store/QueryPlanContext';
import { generateId } from '../../utils';
import './ChatPanel.css';

// TODO: Initialize messages from server session history.
const INITIAL_MESSAGES: ChatMessage[] = [];

/**
 * Left-panel AI chat orchestrator.
 * Manages conversation state, backend AI/demo response lifecycle, and scrolling.
 *
 * TODO: Persist messages to backend conversation history.
 * TODO: Restore previous session messages on page load.
 */
export function ChatPanel() {
  const [messages, setMessages] = useState<ChatMessage[]>(INITIAL_MESSAGES);
  const [status, setStatus] = useState<ChatStatus>('idle');
  const [databases, setDatabases] = useState<BenchmarkDatabaseInfo[]>([]);
  const [selectedBenchmark] = useState('spider');
  const [selectedDbId, setSelectedDbId] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);
  const { triggerExecution } = useExecutionContext();
  const { loadPlan } = useQueryPlanContext();

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, status]);

  useEffect(() => {
    let isMounted = true;

    getBenchmarkDatabases(selectedBenchmark)
      .then((items) => {
        if (!isMounted) return;
        setDatabases(items);
        setSelectedDbId((prev) => prev || items.find((item) => item.hasSQLite)?.dbId || items[0]?.dbId || '');
      })
      .catch(() => {
        if (isMounted) {
          setDatabases([]);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [selectedBenchmark]);

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
        const { content: aiContent, planId } = await sendChatMessage({
          message: trimmed,
          sessionId: 'dev-session',
          datasetContext: selectedDbId
            ? { benchmark: selectedBenchmark, dbId: selectedDbId }
            : undefined,
        });

        const aiMsg: ChatMessage = {
          id: generateId(),
          role: 'assistant',
          content: aiContent,
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, aiMsg]);

        await loadPlan(planId);

        // Execute against the backend using the planId returned by /query.
        triggerExecution(trimmed, planId);
      } catch {
        const errorMsg: ChatMessage = {
          id: generateId(),
          role: 'assistant',
          content: 'Something went wrong generating the query plan. Please try again.',
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, errorMsg]);
        setStatus('error');
        return;
      }

      setStatus('idle');
    },
    [loadPlan, selectedBenchmark, selectedDbId, status, triggerExecution],
  );

  const isEmpty = messages.length === 0 && status === 'idle';
  const selectedDatabase = databases.find((item) => item.dbId === selectedDbId);
  const databasePrompts: SuggestedPrompt[] = (selectedDatabase?.sampleQuestions ?? []).map((item, index) => ({
    id: `${selectedDbId}-${index}`,
    label: `Question ${index + 1}`,
    description: item.question,
    icon: 'question',
  }));

  return (
    <div className="chat-panel">
      <ChatHeader status={status} />
      <DatasetSelector
        benchmark={selectedBenchmark}
        databases={databases}
        selectedDbId={selectedDbId}
        onDbChange={setSelectedDbId}
      />

      <div
        className="chat-panel__messages"
        role="log"
        aria-label="Conversation"
        aria-live="polite"
      >
        <AnimatePresence mode="wait">
          {isEmpty ? (
            <SuggestedPrompts
              key={`suggestions-${selectedDbId}`}
              prompts={databasePrompts}
              databaseLabel={selectedDbId}
              onSelect={sendMessage}
            />
          ) : (
            <div key="messages" className="chat-panel__message-list">
              {messages.map((msg, i) => (
                <ChatMessageItem
                  key={msg.id}
                  message={msg}
                  isLatest={i === messages.length - 1 && status === 'idle'}
                />
              ))}
            </div>
          )}
        </AnimatePresence>

        <AnimatePresence>
          {status === 'thinking' && <TypingIndicator key="typing" />}
        </AnimatePresence>

        <div ref={bottomRef} />
      </div>

      <ChatInput onSend={sendMessage} isDisabled={status === 'thinking'} />
    </div>
  );
}

interface DatasetSelectorProps {
  benchmark: string;
  databases: BenchmarkDatabaseInfo[];
  selectedDbId: string;
  onDbChange: (dbId: string) => void;
}

function DatasetSelector({
  benchmark,
  databases,
  selectedDbId,
  onDbChange,
}: DatasetSelectorProps) {
  const selected = databases.find((item) => item.dbId === selectedDbId);

  return (
    <div className="dataset-selector">
      <div className="dataset-selector__field">
        <span className="dataset-selector__label">Benchmark</span>
        <span className="dataset-selector__pill">{benchmark.toUpperCase()}</span>
      </div>
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
            </option>
          ))}
        </select>
      </label>
      <span className="dataset-selector__meta">
        {selected ? `${selected.tableCount} tables` : 'loading'}
      </span>
    </div>
  );
}
