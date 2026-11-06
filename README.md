# VERLTRIX TIRES — Inventory

Inventory management for VERLTRIX TIRES: a React client and a Node.js (Express)
API in one npm-workspace repository.

## Structure

```
.
├── client/                 React app (Vite)
│   ├── index.html
│   ├── vite.config.js      Dev server + `/api` proxy to the Express server
│   └── src/
│       ├── main.jsx
│       ├── App.jsx         Inventory shell (list + API status)
│       └── styles.css
├── server/                 Node.js API (Express)
│   └── src/
│       ├── index.js        Server entry point
│       └── routes/
│           └── inventory.js  Inventory endpoints
├── Dockerfile              `development` and `production` targets
├── package.json            Workspaces and root scripts
└── package-lock.json
```

## Local development

Requires Node.js 20+.

```bash
npm install
npm run dev
```

- Client: http://localhost:5173
- API: http://localhost:3001 (the client proxies `/api` here)

Other scripts:

| Command | What it does |
| --- | --- |
| `npm run dev:web` | Vite client only |
| `npm run dev:api` | Express API only (watches for changes) |
| `npm run build` | Build the client into `client/dist` |
| `npm start` | Run the API; it also serves `client/dist` when present |

## Docker

The Dockerfile has two targets.

```bash
# Development container with both dev servers (ports 5173 and 3001)
docker build --target development -t verltrix-inventory:dev .
docker run --rm -p 3000:5173 -p 3001:3001 -v "$PWD:/app" verltrix-inventory:dev

# Production image: Express serves the API and the built client on port 3000
docker build --target production -t verltrix-inventory .
docker run --rm -p 3000:3000 verltrix-inventory
```

When using the development target with a bind mount, keep the container's
`node_modules` from the image by not mounting over `/app/node_modules`
(the sandbox configuration handles this with a named volume).

## API

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/health` | Service health and uptime |
| `GET` | `/api/inventory` | List inventory items |
| `POST` | `/api/inventory` | Create an item (`name`, `sku`, `category`, `quantity`) |

Items are kept in memory for now, so they reset when the API restarts.

## Environment

The app runs with no external credentials. Optional variables:

- `PORT` — API port (default `3001`)
- `API_PROXY_TARGET` — API URL used by the Vite dev proxy (default `http://127.0.0.1:3001`)
