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

// TODO: Initialize messages from server session (GET /api/sessions/:id/messages)
const INITIAL_MESSAGES: ChatMessage[] = [];

/**
 * Left-panel AI chat orchestrator.
 * Manages conversation state, mock AI response lifecycle, and scroll behaviour.
 *
 * TODO: Connect chat messages to backend conversation API
 * TODO: Trigger query plan generation after AI response arrives
 * TODO: Sync query plan visualization with assistant responses
 */
export function ChatPanel() {
  const [messages, setMessages] = useState<ChatMessage[]>(INITIAL_MESSAGES);
  const [status, setStatus] = useState<ChatStatus>('idle');
  const bottomRef = useRef<HTMLDivElement>(null);
  const { triggerExecution } = useExecutionContext();
  const { loadPlan } = useQueryPlanContext();

  // Auto-scroll to latest message whenever messages or typing state changes
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, status]);

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || status === 'thinking') return;

      // Append user message immediately
      const userMsg: ChatMessage = {
        id: generateId(),
        role: 'user',
        content: trimmed,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, userMsg]);
      setStatus('thinking');

      // TODO: POST /api/query — replace sendChatMessage mock with real backend call
      // TODO: Pass real sessionId once authentication/session handling is integrated
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

        // Kick off the mock execution pipeline with the user's original query.
        // TODO: Replace with real backend execution — pass planId from AI response
        // TODO: Wait for query plan to be fully rendered before executing
        triggerExecution(trimmed);
      } catch {
        // TODO: Surface real API errors to the user (toast/inline error)
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
    [status]
  );

  const isEmpty = messages.length === 0 && status === 'idle';

  return (
    <div className="chat-panel">
      <ChatHeader status={status} />

      {/* Conversation area */}
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

        {/* Typing indicator rendered outside AnimatePresence list for clean entry/exit */}
        <AnimatePresence>
          {status === 'thinking' && <TypingIndicator key="typing" />}
        </AnimatePresence>

        {/* Scroll anchor */}
        <div ref={bottomRef} />
      </div>

      <ChatInput onSend={sendMessage} isDisabled={status === 'thinking'} />
    </div>
  );
}
