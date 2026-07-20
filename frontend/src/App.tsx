import { useEffect, useState } from "react";
import "./App.css";

type HealthStatus = {
  status: string;
  detail?: string | null;
};

type HealthResponse = {
  application: HealthStatus;
  database: HealthStatus;
  execution: HealthStatus;
};

const pages = ["Dashboard", "Scanner", "Signals", "Active Trades", "Journal", "Risk", "Settings"];

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

function App() {
  const [activePage, setActivePage] = useState(pages[0]);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    async function loadHealth() {
      try {
        const response = await fetch(`${apiBaseUrl}/health`, { signal: controller.signal });
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        setHealth((await response.json()) as HealthResponse);
        setHealthError(null);
      } catch (error) {
        if (!controller.signal.aborted) {
          setHealth(null);
          setHealthError(error instanceof Error ? error.message : "Unavailable");
        }
      }
    }

    void loadHealth();

    return () => controller.abort();
  }, []);

  const apiStatus = health?.application.status ?? (healthError ? "error" : "checking");
  const databaseStatus = health?.database.status ?? "unknown";
  const executionStatus = health?.execution.status ?? "disabled";

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <strong>Binance Scalping Bot</strong>
          <span>Demo Trading</span>
        </div>
        <nav className="nav" aria-label="Main navigation">
          {pages.map((page) => (
            <button
              className={page === activePage ? "active" : undefined}
              key={page}
              onClick={() => setActivePage(page)}
              type="button"
            >
              {page}
            </button>
          ))}
        </nav>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div className="status-group">
            <span className="status-pill">
              <span className={`status-dot ${apiStatus === "ok" ? "ok" : ""}`} />
              API {apiStatus}
            </span>
            <span className="status-pill">
              <span className={`status-dot ${databaseStatus === "ok" ? "ok" : ""}`} />
              Database {databaseStatus}
            </span>
          </div>
          <div className="status-group">
            <span className="status-pill">
              <span className="status-dot warn" />
              Demo Trading
            </span>
            <span className="status-pill">
              <span className="status-dot warn" />
              Execution {executionStatus === "disabled" ? "Disabled" : "Enabled"}
            </span>
          </div>
        </header>

        <section className="content">
          <div className="page-header">
            <h1 className="page-title">{activePage}</h1>
            <div className="page-subtitle">Batch 1 foundation shell. No live trading logic is active.</div>
          </div>

          <div className="terminal-grid">
            <section className="panel">
              <h2>Application</h2>
              <div className="metric">
                <span className="status-label">Backend health</span>
                <span className="metric-value">{apiStatus}</span>
              </div>
            </section>
            <section className="panel">
              <h2>Database</h2>
              <div className="metric">
                <span className="status-label">PostgreSQL connectivity</span>
                <span className="metric-value">{databaseStatus}</span>
              </div>
            </section>
            <section className="panel">
              <h2>Execution</h2>
              <div className="metric">
                <span className="status-label">Live orders</span>
                <span className="metric-value">Disabled</span>
              </div>
            </section>
          </div>

          <section className="panel" style={{ marginTop: 14 }}>
            <h2>{activePage} Workspace</h2>
            <p className="placeholder">
              This page is intentionally limited to navigation and backend health visibility for Batch
              1. Trading data, balances, signals, positions, and performance metrics are not
              implemented.
            </p>
          </section>
        </section>
      </main>
    </div>
  );
}

export default App;
