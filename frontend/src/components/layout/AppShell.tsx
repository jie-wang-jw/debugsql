import { useState, useEffect, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { FiTerminal } from 'react-icons/fi';
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
  const [topRatio, setTopRatio] = useState(57);
  const [externalPrompt, setExternalPrompt] = useState<string | null>(null);
  const rightPanelRef = useRef<HTMLDivElement>(null);
  const isDragging = useRef(false);

  const handleResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    isDragging.current = true;
    document.body.style.cursor = 'row-resize';
    document.body.style.userSelect = 'none';

    const onMove = (ev: MouseEvent) => {
      if (!isDragging.current || !rightPanelRef.current) return;
      const rect = rightPanelRef.current.getBoundingClientRect();
      const offsetY = ev.clientY - rect.top;
      const pct = (offsetY / rect.height) * 100;
      setTopRatio(Math.min(80, Math.max(25, pct)));
    };

    const onUp = () => {
      isDragging.current = false;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };

    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  }, []);

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

      <div className="app-shell__right" ref={rightPanelRef}>
        <div className="app-shell__top-right" style={{ flex: `0 0 ${topRatio}%` }}>
          <CapabilitiesPanel onExampleSelect={handleExampleSelect} />
        </div>

        <div
          className="app-shell__resize-handle"
          onMouseDown={handleResizeStart}
          role="separator"
          aria-orientation="horizontal"
          aria-label="Resize capabilities and execution panels"
        />

        <div className="app-shell__bottom-right" style={{ flex: `0 0 ${100 - topRatio}%` }}>
          <div className="bottom-tabs bottom-tabs--single">
            <div className="bottom-tabs__bar" role="tablist">
              <div className="bottom-tabs__tab bottom-tabs__tab--active" role="tab" aria-selected>
                <span className="bottom-tabs__tab-icon"><FiTerminal size={11} /></span>
                <span className="bottom-tabs__tab-label">Execution</span>
                <ExecutionStatus status={status} compact />
              </div>
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
      </div>
    </div>
  );
}
