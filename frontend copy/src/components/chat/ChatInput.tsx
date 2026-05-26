import { useState, useRef, useCallback, type KeyboardEvent } from 'react';
import { motion } from 'framer-motion';
import { FiSend, FiCommand } from 'react-icons/fi';

interface ChatInputProps {
  onSend: (message: string) => void;
  isDisabled?: boolean;
}

/** Multiline textarea input with keyboard submit and auto-height. */
export function ChatInput({ onSend, isDisabled = false }: ChatInputProps) {
  const [value, setValue] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const canSend = value.trim().length > 0 && !isDisabled;

  /** Resize textarea to fit content (up to a max). */
  function autoResize() {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 140)}px`;
  }

  const handleSend = useCallback(() => {
    if (!canSend) return;
    onSend(value.trim());
    setValue('');
    // Reset height after clearing
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  }, [canSend, onSend, value]);

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    // Enter (without Shift) sends the message
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <div className="chat-input-area">
      <div className={`chat-input__wrap ${isDisabled ? 'chat-input__wrap--disabled' : ''}`}>
        <textarea
          ref={textareaRef}
          className="chat-input__field"
          value={value}
          onChange={(e) => { setValue(e.target.value); autoResize(); }}
          onKeyDown={handleKeyDown}
          placeholder={isDisabled ? 'DebugSQL AI is thinking…' : 'Describe your data question in plain English…'}
          rows={1}
          disabled={isDisabled}
          aria-label="Query input"
        />

        <motion.button
          className="chat-input__send"
          onClick={handleSend}
          disabled={!canSend}
          aria-label="Send message"
          whileHover={canSend ? { scale: 1.08 } : {}}
          whileTap={canSend ? { scale: 0.94 } : {}}
          transition={{ duration: 0.12 }}
        >
          <FiSend size={13} />
        </motion.button>
      </div>

      <p className="chat-input__hint">
        <FiCommand size={9} />
        <kbd>Enter</kbd> to send &nbsp;·&nbsp; <kbd>Shift + Enter</kbd> for newline
      </p>
    </div>
  );
}
