import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { FiSliders, FiTerminal } from 'react-icons/fi';
import { FadeIn }             from '../animations/FadeIn';
import { ChatPanel }          from '../chat/ChatPanel';
import { QueryPlanPanel }     from '../query-plan/QueryPlanPanel';
import { InspectorPanel }     from '../inspector/InspectorPanel';
import { ExecutionPanel }     from '../results/ExecutionPanel';
import { QueryPlanProvider, useQueryPlanContext } from '../../store/QueryPlanContext';
import { ExecutionProvider, useExecutionContext } from '../../store/ExecutionContext';
import { ExecutionStatus }    from '../results/ExecutionStatus';
import '../results/ExecutionPanel.css';
import './AppShell.css';

/**
 * Root layout shell: three-panel dashboard.
 *
 * ┌───────────────────┬──────────────────────────────┐
 * │                   │  Query Plan Area  (top 57%)  │
 * │   Chat Panel      ├──────────────────────────────┤
 * │   (left 30%)      │  [Inspector] [Execution] tab │
 * │                   │  Active panel (bottom 43%)   │
 * └───────────────────┴──────────────────────────────┘
 *
 * ExecutionProvider wraps everything so both ChatPanel and
 * InspectorPanel can call triggerExecution.
 *
 * QueryPlanProvider wraps the right side for node-selection sharing.
 */
export function AppShell() {
  return (
    <ExecutionProvider>
      <QueryPlanProvider>
        <AppShellInner />
      </QueryPlanProvider>
    </ExecutionProvider>
  );
}

/** Inner layout — must live inside ExecutionProvider to consume context. */
function AppShellInner() {
  const { status } = useExecutionContext();
  const { selectedNodeId } = useQueryPlanContext();
  const [activeTab, setActiveTab] = useState<'inspector' | 'execution'>('inspector');

  // Focus Inspector when the user selects a plan node (unless a run is in progress)
  useEffect(() => {
    if (selectedNodeId && status !== 'running') {
      setActiveTab('inspector');
    }
  }, [selectedNodeId, status]);

  // Auto-switch to the Execution tab whenever execution starts or finishes
  useEffect(() => {
    if (status === 'running' || status === 'success' || status === 'failed') {
      setActiveTab('execution');
    }
  }, [status]);

  return (
    <div className="app-shell">
      {/* Ambient background gradients */}
      <div className="app-shell__bg" aria-hidden="true" />

      {/* Left: Chat panel */}
      <FadeIn direction="left" delay={0.05} className="app-shell__left">
        <ChatPanel />
      </FadeIn>

      {/* Right: Query plan + tabbed bottom panel */}
      <>
        <div className="app-shell__right">
          <FadeIn direction="up" delay={0.12} className="app-shell__top-right">
            <QueryPlanPanel />
          </FadeIn>

          <FadeIn direction="up" delay={0.2} className="app-shell__bottom-right">
            <div className="bottom-tabs">
              {/* Tab bar */}
              <div className="bottom-tabs__bar" role="tablist">
                <TabButton
                  id="inspector"
                  label="Inspector"
                  icon={<FiSliders size={11} />}
                  active={activeTab === 'inspector'}
                  onClick={() => setActiveTab('inspector')}
                />
                <TabButton
                  id="execution"
                  label="Execution"
                  icon={<FiTerminal size={11} />}
                  active={activeTab === 'execution'}
                  onClick={() => setActiveTab('execution')}
                  statusDot={<ExecutionStatus status={status} compact />}
                />
              </div>

              {/* Panel content — AnimatePresence for smooth tab switching */}
              <div className="bottom-tabs__content" role="tabpanel">
                <AnimatePresence mode="wait" initial={false}>
                  {activeTab === 'inspector' ? (
                    <motion.div
                      key="inspector"
                      className="bottom-tabs__panel"
                      initial={{ opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -4 }}
                      transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }}
                    >
                      <InspectorPanel />
                    </motion.div>
                  ) : (
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
                  )}
                </AnimatePresence>
              </div>
            </div>
          </FadeIn>
        </div>
      </>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tab button
// ---------------------------------------------------------------------------

interface TabButtonProps {
  id:        string;
  label:     string;
  icon:      React.ReactNode;
  active:    boolean;
  onClick:   () => void;
  statusDot?: React.ReactNode;
}

function TabButton({ id, label, icon, active, onClick, statusDot }: TabButtonProps) {
  return (
    <motion.button
      role="tab"
      aria-selected={active}
      aria-controls={`tabpanel-${id}`}
      className={`bottom-tabs__tab ${active ? 'bottom-tabs__tab--active' : ''}`}
      onClick={onClick}
      whileTap={{ scale: 0.96 }}
      transition={{ duration: 0.1 }}
    >
      <span className="bottom-tabs__tab-icon">{icon}</span>
      <span className="bottom-tabs__tab-label">{label}</span>
      {statusDot}
      {active && (
        <motion.span
          className="bottom-tabs__tab-indicator"
          layoutId="tab-indicator"
          transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
        />
      )}
    </motion.button>
  );
}
