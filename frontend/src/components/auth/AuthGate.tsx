import { useEffect, useState } from 'react';
import { FiDatabase, FiGithub, FiLoader, FiLogOut } from 'react-icons/fi';
import { getCurrentUser, githubLoginUrl, logout, type CurrentUser } from '../../services/api/authApi';
import './AuthGate.css';

interface AuthGateProps {
  children: React.ReactNode;
}

type AuthState =
  | { status: 'loading'; user: null; error: null }
  | { status: 'authenticated'; user: CurrentUser; error: null }
  | { status: 'unauthenticated'; user: null; error: string | null };

export function AuthGate({ children }: AuthGateProps) {
  const [state, setState] = useState<AuthState>({ status: 'loading', user: null, error: null });

  const refreshUser = async () => {
    setState({ status: 'loading', user: null, error: null });
    try {
      const user = await getCurrentUser();
      setState({ status: 'authenticated', user, error: null });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Authentication required';
      setState({ status: 'unauthenticated', user: null, error: message });
    }
  };

  useEffect(() => {
    void refreshUser();
  }, []);

  if (state.status === 'loading') {
    return (
      <div className="auth-screen">
        <div className="auth-card auth-card--compact">
          <FiLoader className="auth-loader" size={18} />
          <span>Checking session</span>
        </div>
      </div>
    );
  }

  if (state.status === 'unauthenticated') {
    return (
      <LoginScreen error={state.error} onRetry={() => void refreshUser()} />
    );
  }

  return (
    <div className="auth-app-frame">
      <UserStrip user={state.user} onLogout={() => void handleLogout(refreshUser)} />
      {children}
    </div>
  );
}

function LoginScreen({ error, onRetry }: { error: string | null; onRetry: () => void }) {
  return (
    <div className="auth-screen">
      <section className="auth-card">
        <div className="auth-brand">
          <div className="auth-brand__icon">
            <FiDatabase size={18} />
          </div>
          <div>
            <p className="auth-eyebrow">CP683 Graduate Project</p>
            <h1>DebugSQL</h1>
          </div>
        </div>
        <p className="auth-copy">
          Sign in to inspect, edit, execute, and audit NL2SQL query plans.
        </p>
        {error && <p className="auth-error">{error}</p>}
        <div className="auth-actions">
          <a className="auth-primary" href={githubLoginUrl()}>
            <FiGithub size={14} /> Login with GitHub
          </a>
          <button className="auth-secondary" type="button" onClick={onRetry}>
            Retry dev session
          </button>
        </div>
        <p className="auth-note">
          Local development uses dev auto-login when <code>DEBUGSQL_AUTO_LOGIN=1</code>.
        </p>
      </section>
    </div>
  );
}

function UserStrip({ user, onLogout }: { user: CurrentUser; onLogout: () => void }) {
  const initials = (user.displayName || user.email || 'U').slice(0, 1).toUpperCase();
  return (
    <div className="user-strip">
      <div className="user-strip__identity">
        {user.avatarUrl ? (
          <img className="user-strip__avatar" src={user.avatarUrl} alt="" />
        ) : (
          <span className="user-strip__avatar user-strip__avatar--fallback">{initials}</span>
        )}
        <span className="user-strip__name">{user.displayName || user.email}</span>
        <span className="user-strip__mode">{user.authMode}</span>
      </div>
      <button className="user-strip__logout" type="button" onClick={onLogout}>
        <FiLogOut size={12} /> Logout
      </button>
    </div>
  );
}

async function handleLogout(refreshUser: () => Promise<void>) {
  try {
    await logout();
  } finally {
    await refreshUser();
  }
}
