import { useEffect, useState } from "react";
import "./App.css";

type ApiState = {
  loading: boolean;
  health?: unknown;
  dbHealth?: unknown;
  error?: string;
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api";

async function fetchJson(path: string) {
  const response = await fetch(`${API_BASE_URL}${path}`);
  if (!response.ok) {
    throw new Error(`${path} returned ${response.status}`);
  }
  return response.json();
}

export default function App() {
  const [state, setState] = useState<ApiState>({ loading: true });

  useEffect(() => {
    let cancelled = false;

    async function loadStatus() {
      try {
        const [health, dbHealth] = await Promise.all([
          fetchJson("/health"),
          fetchJson("/db-health"),
        ]);

        if (!cancelled) {
          setState({ loading: false, health, dbHealth });
        }
      } catch (error) {
        if (!cancelled) {
          setState({
            loading: false,
            error: error instanceof Error ? error.message : "Unknown error",
          });
        }
      }
    }

    loadStatus();

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="app-shell">
      <section className="hero">
        <p className="eyebrow">CP683 Graduate Project</p>
        <h1>DebugSQL</h1>
        <p className="subtitle">
          Minimal Linux deployment check for the frontend, backend, and PostgreSQL chain.
        </p>
      </section>

      <section className="status-grid" aria-label="Service status">
        <StatusCard
          title="Frontend"
          status="ok"
          detail="React/Vite app is running."
        />
        <StatusCard
          title="Backend"
          status={state.loading ? "loading" : state.error ? "error" : "ok"}
          detail={state.error ?? JSON.stringify(state.health, null, 2)}
        />
        <StatusCard
          title="Database"
          status={state.loading ? "loading" : state.error ? "unknown" : "ok"}
          detail={state.error ? "Waiting for backend response." : JSON.stringify(state.dbHealth, null, 2)}
        />
      </section>
    </main>
  );
}

function StatusCard({
  title,
  status,
  detail,
}: {
  title: string;
  status: string;
  detail: string;
}) {
  return (
    <article className="status-card">
      <div className="status-card__header">
        <h2>{title}</h2>
        <span className={`status-pill status-pill--${status}`}>{status}</span>
      </div>
      <pre>{detail}</pre>
    </article>
  );
}
