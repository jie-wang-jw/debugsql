import { useEffect, useState, type Dispatch, type ReactNode, type SetStateAction } from 'react';
import { FiDatabase, FiLoader, FiLogOut, FiMail } from 'react-icons/fi';
import {
  getCurrentUser,
  logout,
  requestEmailCode,
  verifyEmailCode,
  type CurrentUser,
} from '../../services/api/authApi';
import './AuthGate.css';

interface AuthGateProps {
  children: ReactNode;
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
      const rawMessage = error instanceof Error ? error.message : 'Authentication required';
      const message = rawMessage === 'No authenticated user' ? null : rawMessage;
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
      <LoginScreen
        error={state.error}
        onRetry={() => void refreshUser()}
        onAuthenticated={(user) => setState({ status: 'authenticated', user, error: null })}
      />
    );
  }

  return (
    <div className="auth-app-frame">
      <UserStrip user={state.user} onLogout={() => void handleLogout(setState)} />
      {children}
    </div>
  );
}

function LoginScreen({
  error,
  onRetry,
  onAuthenticated,
}: {
  error: string | null;
  onRetry: () => void;
  onAuthenticated: (user: CurrentUser) => void;
}) {
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [status, setStatus] = useState<'idle' | 'sending' | 'sent' | 'verifying'>('idle');
  const [formError, setFormError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [resendAfter, setResendAfter] = useState(0);
  const showDevRetry = import.meta.env.DEV && Boolean(error);

  useEffect(() => {
    if (resendAfter <= 0) {
      return;
    }
    const timer = window.setInterval(() => {
      setResendAfter((value) => Math.max(0, value - 1));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [resendAfter]);

  const handleRequestCode = async () => {
    setFormError(null);
    setNotice(null);
    setStatus('sending');
    try {
      const result = await requestEmailCode(email);
      setStatus('sent');
      setResendAfter(result.resendAfterSeconds);
      setNotice(result.delivery === 'dev_log'
        ? 'Code generated. Check the backend logs for the verification code.'
        : `Code sent to ${result.email}.`);
    } catch (requestError) {
      setStatus('idle');
      setFormError(requestError instanceof Error ? requestError.message : 'Unable to send verification code');
    }
  };

  const handleVerifyCode = async () => {
    setFormError(null);
    setStatus('verifying');
    try {
      const user = await verifyEmailCode(email, code);
      onAuthenticated(user);
    } catch (verifyError) {
      setStatus('sent');
      setFormError(verifyError instanceof Error ? verifyError.message : 'Unable to verify code');
    }
  };

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
          Sign in with your email to inspect, edit, execute, and audit NL2SQL query plans.
        </p>
        {(formError || error) && <p className="auth-error">{formError || error}</p>}
        {notice && <p className="auth-success">{notice}</p>}
        <form className="auth-form" onSubmit={(event) => event.preventDefault()}>
          <label className="auth-field">
            <span>Email</span>
            <input
              type="email"
              value={email}
              autoComplete="email"
              placeholder="you@example.com"
              disabled={status === 'sending' || status === 'verifying'}
              onChange={(event) => setEmail(event.target.value)}
            />
          </label>
          <button
            className="auth-primary"
            type="button"
            disabled={!email || status === 'sending' || status === 'verifying' || resendAfter > 0}
            onClick={() => void handleRequestCode()}
          >
            <FiMail size={14} />
            {status === 'sending' ? 'Sending code' : resendAfter > 0 ? `Resend in ${resendAfter}s` : 'Send code'}
          </button>
          <label className="auth-field">
            <span>Verification code</span>
            <input
              type="text"
              inputMode="numeric"
              maxLength={6}
              value={code}
              autoComplete="one-time-code"
              placeholder="123456"
              disabled={status === 'sending' || status === 'verifying'}
              onChange={(event) => setCode(event.target.value.replace(/\D/g, '').slice(0, 6))}
            />
          </label>
          <button
            className="auth-primary"
            type="button"
            disabled={!email || code.length !== 6 || status === 'sending' || status === 'verifying'}
            onClick={() => void handleVerifyCode()}
          >
            {status === 'verifying' ? 'Verifying' : 'Sign in'}
          </button>
        </form>
        {showDevRetry && (
          <div className="auth-actions">
            <button className="auth-secondary" type="button" onClick={onRetry}>
              Retry dev session
            </button>
          </div>
        )}
        <p className="auth-note">
          Local development can still use dev auto-login when <code>DEBUGSQL_AUTO_LOGIN=1</code>.
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

async function handleLogout(setState: Dispatch<SetStateAction<AuthState>>) {
  try {
    await logout();
  } finally {
    setState({ status: 'unauthenticated', user: null, error: null });
  }
}
