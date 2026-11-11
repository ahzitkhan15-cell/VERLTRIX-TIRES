import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import express from 'express';
import createInventoryRouter from './routes/inventory.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Builds the Express app. Each call gets its own inventory store, so tests can
// run against a clean, isolated instance without touching the live server.
export function createApp() {
  const app = express();
  app.use(express.json());

  app.get('/api/health', (_req, res) => {
    res.json({ status: 'ok', service: 'inventory-api', uptime: process.uptime() });
  });

  app.use('/api/inventory', createInventoryRouter());

  // Unknown API paths get a JSON 404 here, before the client fallback below
  // could answer them with index.html and a 200.
  app.use('/api', (_req, res) => {
    res.status(404).json({ error: 'Not found.' });
  });

  // In production the Express server also serves the built React client, so the
  // app runs from a single origin. During development Vite serves the client.
  const clientDist = path.join(__dirname, '../../client/dist');
  if (fs.existsSync(clientDist)) {
    app.use(express.static(clientDist));
    app.get('*', (_req, res) => {
      res.sendFile(path.join(clientDist, 'index.html'));
    });
  }

  return app;
}
