import { useState, useRef, useEffect, useCallback } from 'react';
import { AnimatePresence } from 'framer-motion';
import type { ChatMessage, ChatStatus } from './chat.types';
import { ChatHeader } from './ChatHeader';
import { ChatMessage as ChatMessageItem } from './ChatMessage';
import { ChatInput } from './ChatInput';
import { TypingIndicator } from './TypingIndicator';
import { SuggestedPrompts } from './SuggestedPrompts';
import { sendChatMessage } from '../../services/adapters/chatAdapter';
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
  const bottomRef = useRef<HTMLDivElement>(null);
  const { triggerExecution } = useExecutionContext();
  const { loadPlan } = useQueryPlanContext();

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, status]);

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
    [loadPlan, status, triggerExecution],
  );

  const isEmpty = messages.length === 0 && status === 'idle';

  return (
    <div className="chat-panel">
      <ChatHeader status={status} />

      <div
        className="chat-panel__messages"
        role="log"
        aria-label="Conversation"
        aria-live="polite"
      >
        <AnimatePresence mode="wait">
          {isEmpty ? (
            <SuggestedPrompts key="suggestions" onSelect={sendMessage} />
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
