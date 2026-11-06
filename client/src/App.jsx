import { useEffect, useState } from 'react';

const API_STATES = {
  checking: { label: 'Connecting to API', tone: 'pending' },
  online: { label: 'API connected', tone: 'ok' },
  offline: { label: 'API unavailable', tone: 'error' },
};

const COLUMNS = ['Item', 'SKU', 'Category', 'On hand', 'Status'];

export default function App() {
  const [apiState, setApiState] = useState('checking');
  const [items, setItems] = useState([]);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [health, inventory] = await Promise.all([
          fetch('/api/health'),
          fetch('/api/inventory'),
        ]);

        if (!health.ok || !inventory.ok) {
          throw new Error('API request failed');
        }

        const payload = await inventory.json();
        if (!cancelled) {
          setItems(Array.isArray(payload.items) ? payload.items : []);
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
            <span className="count">{items.length} items</span>
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
                      <td>{item.status}</td>
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

      <footer className="footer">
        <span>VERLTRIX TIRES &middot; inventory starter</span>
        <span className="mono">React + Express</span>
      </footer>
    </div>
  );
}
