import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';

// Lazy-loaded pages for code splitting
const Dashboard = lazy(() => import('../pages/Dashboard/Dashboard'));

// TODO: Add these pages in future phases
// const Login    = lazy(() => import('../pages/Login/Login'));
// const History  = lazy(() => import('../pages/History/History'));
// const Settings = lazy(() => import('../pages/Settings/Settings'));

function PageLoader() {
  return (
    <div
      style={{
        height: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'var(--bg-base)',
        color: 'var(--text-muted)',
        fontFamily: 'var(--font-mono)',
        fontSize: '12px',
        letterSpacing: '0.05em',
      }}
    >
      loading…
    </div>
  );
}

export function AppRouter() {
  return (
    <BrowserRouter>
      <Suspense fallback={<PageLoader />}>
        <Routes>
          {/* Main dashboard workspace */}
          <Route path="/" element={<Dashboard />} />
          <Route path="/dashboard" element={<Dashboard />} />

          {/* Prepared routes for future phases */}
          {/* <Route path="/login"    element={<Login />}    /> */}
          {/* <Route path="/history"  element={<History />}  /> */}
          {/* <Route path="/settings" element={<Settings />} /> */}

          {/* Catch-all: redirect unknown paths to dashboard */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}
