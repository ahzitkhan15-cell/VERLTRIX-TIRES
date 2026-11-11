import { createApp } from './app.js';

const PORT = Number(process.env.PORT) || 3001;

createApp().listen(PORT, '0.0.0.0', () => {
  console.log(`Inventory API listening on http://0.0.0.0:${PORT}`);
});
