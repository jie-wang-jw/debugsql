import { FadeIn } from '../animations/FadeIn';
import { ChatPanel } from '../chat/ChatPanel';
import { QueryPlanPanel } from '../query-plan/QueryPlanPanel';
import { InspectorPanel } from '../inspector/InspectorPanel';
import './AppShell.css';

/**
 * Root layout shell: three-panel dashboard.
 *
 * ┌───────────────────┬─────────────────────────────┐
 * │                   │   Query Plan Area  (top)     │
 * │   Chat Panel      ├─────────────────────────────┤
 * │   (left 30%)      │   Inspector Panel  (bottom)  │
 * └───────────────────┴─────────────────────────────┘
 */
export function AppShell() {
  return (
    <div className="app-shell">
      {/* Ambient background gradients */}
      <div className="app-shell__bg" aria-hidden="true" />

      {/* Left: Chat panel */}
      <FadeIn direction="left" delay={0.05} className="app-shell__left">
        <ChatPanel />
      </FadeIn>

      {/* Right: Query plan + Inspector stacked */}
      <div className="app-shell__right">
        <FadeIn direction="up" delay={0.12} className="app-shell__top-right">
          <QueryPlanPanel />
        </FadeIn>

        <FadeIn direction="up" delay={0.2} className="app-shell__bottom-right">
          <InspectorPanel />
        </FadeIn>
      </div>
    </div>
  );
}
