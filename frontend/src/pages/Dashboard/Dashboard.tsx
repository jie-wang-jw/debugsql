import { AppShell } from '../../components/layout/AppShell';

/**
 * Dashboard page — the primary workspace for DebugSQL.
 * Renders the full three-panel AppShell.
 *
 * TODO: Fetch initial session/query state on mount
 * TODO: Pass query plan data and selected node state down through context
 */
export default function Dashboard() {
  return <AppShell />;
}
