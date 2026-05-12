import { motion } from 'framer-motion';
import { FiBarChart2, FiFilter, FiGitMerge, FiList, FiZap } from 'react-icons/fi';
import type { SuggestedPrompt } from './chat.types';

interface SuggestedPromptsProps {
  onSelect: (prompt: string) => void;
}

const PROMPTS: SuggestedPrompt[] = [
  {
    id: 'p1',
    label: 'Total sales by region',
    description: 'Show total sales grouped by region',
    icon: 'chart',
  },
  {
    id: 'p2',
    label: 'Top 10 selling stores',
    description: 'Rank stores by revenue in the last 30 days',
    icon: 'sort',
  },
  {
    id: 'p3',
    label: 'Customers with recent orders',
    description: 'Find users who placed more than 5 orders',
    icon: 'join',
  },
  {
    id: 'p4',
    label: 'Products low in stock',
    description: 'Filter active products where quantity < 10',
    icon: 'filter',
  },
];

const PROMPT_ICONS: Record<SuggestedPrompt['icon'], React.ComponentType<{ size?: number }>> = {
  chart:  FiBarChart2,
  filter: FiFilter,
  join:   FiGitMerge,
  sort:   FiList,
};

/**
 * Empty-state component displayed when there are no messages.
 * Shows a welcome screen and clickable prompt suggestions.
 */
export function SuggestedPrompts({ onSelect }: SuggestedPromptsProps) {
  return (
    <motion.div
      className="suggested-prompts"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0, transition: { duration: 0.15 } }}
      transition={{ duration: 0.35 }}
    >
      {/* Hero area */}
      <div className="sp-hero">
        <motion.div
          className="sp-hero__icon"
          animate={{ boxShadow: ['0 0 12px rgba(59,130,246,0.15)', '0 0 28px rgba(59,130,246,0.3)', '0 0 12px rgba(59,130,246,0.15)'] }}
          transition={{ duration: 2.5, repeat: Infinity, ease: 'easeInOut' }}
        >
          <FiZap size={22} />
        </motion.div>
        <h2 className="sp-hero__title">Start a SQL Conversation</h2>
        <p className="sp-hero__desc">
          Describe your data question in plain English.<br />
          I'll generate the SQL and build an editable query plan.
        </p>
      </div>

      {/* Suggestion cards */}
      <div className="sp-cards">
        <p className="sp-cards__label">Try a suggestion</p>
        <div className="sp-cards__grid">
          {PROMPTS.map((prompt, i) => {
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
              </motion.button>
            );
          })}
        </div>
      </div>
    </motion.div>
  );
}
