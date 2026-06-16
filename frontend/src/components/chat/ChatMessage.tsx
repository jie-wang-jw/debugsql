import { motion } from 'framer-motion';
import { FiZap, FiUser, FiCopy, FiCheck } from 'react-icons/fi';
import { useState } from 'react';
import type { ChatMessage, ContentSegment } from './chat.types';
import { formatTime } from '../../utils';

interface ChatMessageProps {
  message: ChatMessage;
  isLatest: boolean;
}

/** Parses message content into text and fenced code block segments. */
function parseContent(raw: string): ContentSegment[] {
  const segments: ContentSegment[] = [];
  const fenceRegex = /```(\w*)\n?([\s\S]*?)```/g;
  let cursor = 0;
  let match: RegExpExecArray | null;

  while ((match = fenceRegex.exec(raw)) !== null) {
    if (match.index > cursor) {
      const text = raw.slice(cursor, match.index).trim();
      if (text) segments.push({ type: 'text', content: text });
    }
    segments.push({ type: 'code', content: match[2].trim(), language: match[1] || 'sql' });
    cursor = match.index + match[0].length;
  }

  if (cursor < raw.length) {
    const remaining = raw.slice(cursor).trim();
    if (remaining) segments.push({ type: 'text', content: remaining });
  }

  return segments.length > 0 ? segments : [{ type: 'text', content: raw }];
}

/** Renders a single chat message bubble (user or assistant). */
export function ChatMessage({ message, isLatest }: ChatMessageProps) {
  const isUser = message.role === 'user';
  const segments = parseContent(message.content);

  return (
    <motion.div
      className={`chat-msg chat-msg--${message.role}`}
      initial={{ opacity: 0, y: 12, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
      layout={isLatest}
    >
      {/* Avatar — only shown for assistant */}
      {!isUser && (
        <div className="chat-msg__avatar chat-msg__avatar--ai">
          <FiZap size={11} />
        </div>
      )}

      <div className="chat-msg__content">
        {/* Sender + timestamp */}
        <div className="chat-msg__meta">
          <span className="chat-msg__sender">{isUser ? 'You' : 'DebugSQL AI'}</span>
          <span className="chat-msg__time">{formatTime(message.timestamp)}</span>
        </div>

        {/* Message bubble */}
        <div className="chat-msg__bubble">
          {segments.map((seg, i) =>
            seg.type === 'code' ? (
              <CodeBlock key={i} code={seg.content} language={seg.language} />
            ) : (
              <p key={i} className="chat-msg__text">{seg.content}</p>
            )
          )}
          {!isUser && <MessageMetadata message={message} />}
        </div>
      </div>

      {/* Avatar — only shown for user */}
      {isUser && (
        <div className="chat-msg__avatar chat-msg__avatar--user">
          <FiUser size={11} />
        </div>
      )}
    </motion.div>
  );
}

function MessageMetadata({ message }: { message: ChatMessage }) {
  const assumptions = message.assumptions?.filter(Boolean) ?? [];
  const tables = message.tablesUsed?.filter(Boolean) ?? [];
  const hasConfidence = typeof message.confidence === 'number';
  if (!assumptions.length && !tables.length && !hasConfidence) return null;

  return (
    <div className="chat-msg__metadata" aria-label="AI response metadata">
      {hasConfidence && (
        <span className="chat-msg__metadata-pill">
          confidence {Math.round((message.confidence ?? 0) * 100)}%
        </span>
      )}
      {tables.length > 0 && (
        <span className="chat-msg__metadata-pill">
          tables {tables.join(', ')}
        </span>
      )}
      {assumptions.length > 0 && (
        <div className="chat-msg__metadata-block">
          <span>Assumptions</span>
          <ul>
            {assumptions.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

/* ---- Code block with copy button ---- */
interface CodeBlockProps {
  code: string;
  language?: string;
}

function CodeBlock({ code, language = 'sql' }: CodeBlockProps) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="code-block">
      <div className="code-block__header">
        <span className="code-block__lang">{language.toUpperCase()}</span>
        <button
          className="code-block__copy"
          onClick={handleCopy}
          aria-label="Copy code"
          title="Copy to clipboard"
        >
          {copied ? <FiCheck size={11} /> : <FiCopy size={11} />}
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      <pre className="code-block__pre"><code>{code}</code></pre>
    </div>
  );
}
