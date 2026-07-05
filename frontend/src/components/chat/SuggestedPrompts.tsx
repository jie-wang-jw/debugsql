import { motion } from 'framer-motion';
import {
  FiArrowRight,
  FiBarChart2,
  FiFilter,
  FiGitMerge,
  FiHelpCircle,
  FiList,
  FiZap,
} from 'react-icons/fi';
import type { SuggestedPrompt } from './chat.types';

interface SuggestedPromptsProps {
  prompts?: SuggestedPrompt[];
  databaseLabel?: string;
  title?: string;
  description?: React.ReactNode;
  sectionLabel?: string;
  onSelect: (prompt: string) => void;
}

const DEFAULT_PROMPTS: SuggestedPrompt[] = [
  {
    id: 'p1',
    label: 'Write a benchmark question',
    description: 'Ask a question about the selected database schema',
    icon: 'question',
  },
];

const PROMPT_ICONS: Record<SuggestedPrompt['icon'], React.ComponentType<{ size?: number }>> = {
  chart: FiBarChart2,
  filter: FiFilter,
  join: FiGitMerge,
  sort: FiList,
  question: FiHelpCircle,
};

export function SuggestedPrompts({
  prompts,
  databaseLabel,
  title = 'Start a SQL Conversation',
  description,
  sectionLabel,
  onSelect,
}: SuggestedPromptsProps) {
  const visiblePrompts = prompts?.length ? prompts : DEFAULT_PROMPTS;

  return (
    <motion.div
      className="suggested-prompts"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0, transition: { duration: 0.15 } }}
      transition={{ duration: 0.35 }}
    >
      <div className="sp-hero">
        <motion.div
          className="sp-hero__icon"
          animate={{ boxShadow: ['0 0 12px rgba(59,130,246,0.15)', '0 0 28px rgba(59,130,246,0.3)', '0 0 12px rgba(59,130,246,0.15)'] }}
          transition={{ duration: 2.5, repeat: Infinity, ease: 'easeInOut' }}
        >
          <FiZap size={22} />
        </motion.div>
        <h2 className="sp-hero__title">{title}</h2>
        <p className="sp-hero__desc">
          {description ?? (
            <>
              Ask a question for the selected database.<br />
              I'll prepare safe SQL and ask before running it.
            </>
          )}
        </p>
      </div>

      <div className="sp-cards">
        <p className="sp-cards__label">
          {sectionLabel ?? (databaseLabel ? `Example questions from ${databaseLabel}` : 'Try a suggestion')}
        </p>
        <div className="sp-cards__grid">
          {visiblePrompts.map((prompt, i) => {
            const Icon = PROMPT_ICONS[prompt.icon];
            return (
              <motion.button
                key={prompt.id}
                className="sp-card"
                onClick={() => onSelect(prompt.description)}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 + i * 0.07, duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
                whileHover={{ scale: 1.02, y: -2 }}
                whileTap={{ scale: 0.98 }}
              >
                <div className="sp-card__icon">
                  <Icon size={13} />
                </div>
                <div className="sp-card__text">
                  <span className="sp-card__label">{prompt.label}</span>
                  <span className="sp-card__desc">{prompt.description}</span>
                </div>
                <FiArrowRight size={12} className="sp-card__arrow" />
              </motion.button>
            );
          })}
        </div>
      </div>
    </motion.div>
  );
}
