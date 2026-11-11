import { useEffect, useState } from 'react';
import NewItemDialog from './components/NewItemDialog.jsx';

const API_STATES = {
  checking: { label: 'Connecting to API', tone: 'pending' },
  online: { label: 'API connected', tone: 'ok' },
  offline: { label: 'API unavailable', tone: 'error' },
};

const COLUMNS = ['Item', 'SKU', 'Category', 'On hand', 'Status'];

function statusTone(status) {
  if (status === 'In stock') return 'ok';
  if (status === 'Low stock') return 'warn';
  return 'muted';
}

export default function App() {
  const [apiState, setApiState] = useState('checking');
  const [items, setItems] = useState([]);
  const [dialogOpen, setDialogOpen] = useState(false);

  async function loadInventory() {
    const response = await fetch('/api/inventory');
    if (!response.ok) {
      throw new Error('API request failed');
    }
    const payload = await response.json();
    setItems(Array.isArray(payload.items) ? payload.items : []);
  }

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [health] = await Promise.all([fetch('/api/health'), loadInventory()]);

        if (!health.ok) {
          throw new Error('API request failed');
        }

        if (!cancelled) {
          setApiState('online');
        }
      } catch {
        if (!cancelled) {
          setApiState('offline');
        }
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleCreated() {
    setDialogOpen(false);
    try {
      await loadInventory();
      setApiState('online');
    } catch {
      setApiState('offline');
    }
  }

  const status = API_STATES[apiState];

  return (
    <div className="app">
      <header className="topbar">
        <a className="brand" href="/">
          <span className="brand__mark" aria-hidden="true">
            VT
          </span>
          <span className="brand__text">
            <strong>VERLTRIX TIRES</strong>
            <span>Inventory management</span>
          </span>
        </a>

        <span className={`status status--${status.tone}`}>
          <span className="status__dot" aria-hidden="true" />
          {status.label}
        </span>
      </header>

      <main className="content">
        <div className="page-head">
          <p className="eyebrow">Operations</p>
          <h1>Inventory</h1>
          <p className="lede">
            Track tire stock, locations, and movements. The app shell and API are
            running &mdash; inventory features build on top of this.
          </p>
        </div>

        <section className="panel" aria-labelledby="items-heading">
          <div className="panel__head">
            <div>
              <h2 id="items-heading">Inventory items</h2>
              <p className="panel__sub">
                Stock records from the inventory API appear here.
              </p>
            </div>
            <div className="panel__actions">
              <span className="count">
                {items.length} {items.length === 1 ? 'item' : 'items'}
              </span>
              <button
                type="button"
                className="btn btn--primary"
                onClick={() => setDialogOpen(true)}
              >
                Add item
              </button>
            </div>
          </div>

          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  {COLUMNS.map((column) => (
                    <th key={column} scope="col">
                      {column}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {items.length === 0 ? (
                  <tr>
                    <td colSpan={COLUMNS.length}>
                      <div className="empty">
                        <span className="empty__icon" aria-hidden="true">
                          <svg viewBox="0 0 24 24" width="26" height="26" fill="none">
                            <path
                              d="M3 7h18M3 12h18M3 17h18"
                              stroke="currentColor"
                              strokeWidth="1.6"
                              strokeLinecap="round"
                            />
                          </svg>
                        </span>
                        <p className="empty__title">No inventory items yet</p>
                        <p className="empty__text">
                          Once the inventory data layer is connected, stock levels
                          and movements will be listed here.
                        </p>
                      </div>
                    </td>
                  </tr>
                ) : (
                  items.map((item) => (
                    <tr key={item.id ?? item.sku}>
                      <td>{item.name}</td>
                      <td className="mono">{item.sku}</td>
                      <td>{item.category}</td>
                      <td>{item.quantity}</td>
                      <td>
                        <span className={`pill pill--${statusTone(item.status)}`}>
                          {item.status}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>

        <section className="grid" aria-label="Starter notes">
          <article className="note">
            <h3>React client</h3>
            <p>
              Pages and components live in <code>client/src</code>. Vite hot-reloads
              every change.
            </p>
          </article>
          <article className="note">
            <h3>Node API</h3>
            <p>
              Routes live in <code>server/src/routes</code>. Requests to
              <code>/api</code> are proxied to the Express server.
            </p>
          </article>
          <article className="note">
            <h3>Next step</h3>
            <p>
              Add a database, then build create, edit, and stock-movement flows for
              inventory items.
            </p>
          </article>
        </section>
      </main>

      <NewItemDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        onCreated={handleCreated}
      />

      <footer className="footer">
        <span>VERLTRIX TIRES &middot; inventory starter</span>
        <span className="mono">React + Express</span>
      </footer>
    </div>
  );
}
