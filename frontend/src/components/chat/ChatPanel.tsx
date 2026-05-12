import { useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { FiDatabase, FiSend, FiZap, FiUser } from 'react-icons/fi';
import type { ChatMessage } from '../../types';
import { formatTime } from '../../utils';
import { StatusBadge } from '../ui/StatusBadge';
import './ChatPanel.css';

// TODO: Replace with live conversation state from AI backend (POST /api/query)
const MOCK_MESSAGES: ChatMessage[] = [
  {
    id: '1',
    role: 'assistant',
    content:
      "Hello! I'm your SQL debugging assistant. Submit a natural language query and I'll generate the SQL, build an editable query plan, and help you optimize it.",
    timestamp: new Date(Date.now() - 120_000),
  },
  {
    id: '2',
    role: 'user',
    content: 'Find all users who placed more than 5 orders in the last 30 days, sorted by order count.',
    timestamp: new Date(Date.now() - 60_000),
  },
  {
    id: '3',
    role: 'assistant',
    content:
      'Generated SQL:\n\nSELECT u.id, u.name,\n  COUNT(o.id) AS order_count\nFROM users u\nJOIN orders o ON o.user_id = u.id\nWHERE o.created_at >= NOW() - INTERVAL \'30 days\'\nGROUP BY u.id\nHAVING COUNT(o.id) > 5\nORDER BY order_count DESC;\n\nQuery plan ready — select a node in the plan to inspect and edit it.',
    timestamp: new Date(),
  },
];

export function ChatPanel() {
  const bottomRef = useRef<HTMLDivElement>(null);

  // TODO: Auto-scroll when new assistant messages are appended
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  return (
    <div className="chat-panel">
      <ChatHeader />
      <div className="chat-panel__messages">
        <AnimatePresence initial>
          {MOCK_MESSAGES.map((msg, i) => (
            <MessageBubble key={msg.id} message={msg} index={i} />
          ))}
        </AnimatePresence>
        <div ref={bottomRef} />
      </div>
      <ChatInputArea />
    </div>
  );
}

/* ---- Header ---- */
function ChatHeader() {
  return (
    <div className="chat-header">
      <div className="chat-header__brand">
        <div className="chat-header__icon-wrap">
          <FiDatabase size={15} />
        </div>
        <div className="chat-header__titles">
          <span className="chat-header__name">DebugSQL</span>
          <span className="chat-header__sub">Editable Query Plans for NL2SQL</span>
        </div>
      </div>
      <StatusBadge label="AI Ready" variant="green" dot />
    </div>
  );
}

/* ---- Message bubble ---- */
interface MessageBubbleProps {
  message: ChatMessage;
  index: number;
}

function MessageBubble({ message, index }: MessageBubbleProps) {
  const isUser = message.role === 'user';
  const isCode = message.content.includes('\n') && !isUser;

  return (
    <motion.div
      className={`chat-msg chat-msg--${message.role}`}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28, delay: index * 0.06, ease: [0.22, 1, 0.36, 1] }}
    >
      <div className="chat-msg__avatar">
        {isUser ? <FiUser size={11} /> : <FiZap size={11} />}
      </div>
      <div className="chat-msg__body">
        <div className="chat-msg__meta">
          <span className="chat-msg__role">{isUser ? 'You' : 'DebugSQL AI'}</span>
          <span className="chat-msg__time">{formatTime(message.timestamp)}</span>
        </div>
        {isCode ? (
          <pre className="chat-msg__code">{message.content}</pre>
        ) : (
          <p className="chat-msg__text">{message.content}</p>
        )}
      </div>
    </motion.div>
  );
}

/* ---- Input area ---- */
function ChatInputArea() {
  // TODO: Connect to AI service — send NL query, receive SQL + query plan
  return (
    <div className="chat-input-area">
      <div className="chat-input__wrap">
        <textarea
          className="chat-input__field"
          placeholder="Describe your data question in plain English…"
          rows={2}
          readOnly
        />
        <button className="chat-input__send" aria-label="Send query" disabled>
          <FiSend size={14} />
        </button>
      </div>
      <p className="chat-input__hint">
        Press <kbd>⌘ Enter</kbd> to submit · <kbd>Shift Enter</kbd> for new line
      </p>
    </div>
  );
}
