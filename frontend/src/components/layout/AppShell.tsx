import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { FiDatabase, FiTerminal } from 'react-icons/fi';
import { FadeIn } from '../animations/FadeIn';
import { ChatPanel } from '../chat/ChatPanel';
import { CapabilitiesPanel } from '../capabilities/CapabilitiesPanel';
import { ExecutionPanel } from '../results/ExecutionPanel';
import { DatasetProvider } from '../../store/DatasetContext';
import { ExecutionProvider, useExecutionContext } from '../../store/ExecutionContext';
import { ExecutionStatus } from '../results/ExecutionStatus';
import type { CapabilityExample } from '../../services/api/capabilitiesApi';
import '../results/ExecutionPanel.css';
import './AppShell.css';

/**
 * Root layout shell: chat + capabilities explorer + execution results.
 */
export function AppShell() {
  return (
    <DatasetProvider>
      <ExecutionProvider>
        <AppShellInner />
      </ExecutionProvider>
    </DatasetProvider>
  );
}

function AppShellInner() {
  const { status } = useExecutionContext();
  const [externalPrompt, setExternalPrompt] = useState<string | null>(null);
  const [capabilitiesOpen, setCapabilitiesOpen] = useState(false);

  useEffect(() => {
    if (!capabilitiesOpen) return undefined;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setCapabilitiesOpen(false);
    };
    window.addEventListener('keydown', closeOnEscape);
    return () => window.removeEventListener('keydown', closeOnEscape);
  }, [capabilitiesOpen]);

  const handleExampleSelect = useCallback((example: CapabilityExample) => {
    setExternalPrompt(example.kind === 'prompt' ? example.content : example.content);
  }, []);

  return (
    <div className="app-shell">
      <div className="app-shell__bg" aria-hidden="true" />

      <FadeIn direction="left" delay={0.05} className="app-shell__left">
        <ChatPanel
          externalPrompt={externalPrompt}
          onExternalPromptConsumed={() => setExternalPrompt(null)}
        />
      </FadeIn>

      <div className="app-shell__right">
        <div className="app-shell__execution">
          <div className="bottom-tabs bottom-tabs--single">
            <div className="bottom-tabs__bar" role="tablist">
              <div className="bottom-tabs__tab bottom-tabs__tab--active" role="tab" aria-selected>
                <span className="bottom-tabs__tab-icon"><FiTerminal size={11} /></span>
                <span className="bottom-tabs__tab-label">Execution</span>
                <ExecutionStatus status={status} compact />
              </div>
              <button
                type="button"
                className="app-shell__capabilities-trigger"
                onClick={() => setCapabilitiesOpen(true)}
                aria-haspopup="dialog"
                aria-expanded={capabilitiesOpen}
                title="Open database capabilities"
              >
                <FiDatabase size={13} />
                <span>Capabilities</span>
              </button>
            </div>
            <div className="bottom-tabs__content" role="tabpanel">
              <AnimatePresence mode="wait" initial={false}>
                <motion.div
                  key="execution"
                  className="bottom-tabs__panel"
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -4 }}
                  transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }}
                >
                  <ExecutionPanel />
                </motion.div>
              </AnimatePresence>
            </div>
          </div>
        </div>

        <AnimatePresence>
          {capabilitiesOpen && (
            <>
              <motion.button
                type="button"
                className="app-shell__drawer-backdrop"
                aria-label="Close capabilities explorer"
                onClick={() => setCapabilitiesOpen(false)}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
              />
              <motion.aside
                className="app-shell__capabilities-drawer"
                role="dialog"
                aria-modal="true"
                aria-label="Capabilities Explorer"
                initial={{ x: '100%' }}
                animate={{ x: 0 }}
                exit={{ x: '100%' }}
                transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
              >
                <CapabilitiesPanel
                  onExampleSelect={handleExampleSelect}
                  onClose={() => setCapabilitiesOpen(false)}
                />
              </motion.aside>
            </>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
