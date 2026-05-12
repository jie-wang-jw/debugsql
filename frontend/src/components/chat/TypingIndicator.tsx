import { motion } from 'framer-motion';
import { FiZap } from 'react-icons/fi';

/** Animated three-dot typing indicator shown while the AI is generating a response. */
export function TypingIndicator() {
  return (
    <motion.div
      className="typing-indicator"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 4, transition: { duration: 0.15 } }}
      transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
    >
      {/* AI avatar */}
      <div className="chat-msg__avatar chat-msg__avatar--ai">
        <FiZap size={11} />
      </div>

      <div className="typing-indicator__body">
        <div className="typing-indicator__meta">
          <span className="chat-msg__sender">DebugSQL AI</span>
          <span className="chat-msg__time">generating…</span>
        </div>
        <div className="typing-indicator__bubble">
          {[0, 1, 2].map((i) => (
            <motion.span
              key={i}
              className="typing-dot"
              animate={{ y: [0, -5, 0], opacity: [0.4, 1, 0.4] }}
              transition={{
                duration: 0.7,
                repeat: Infinity,
                delay: i * 0.14,
                ease: 'easeInOut',
              }}
            />
          ))}
        </div>
      </div>
    </motion.div>
  );
}
