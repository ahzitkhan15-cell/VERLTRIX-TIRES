import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Sandbox previews are served through a proxy on a sandbox-specific hostname.
// Only in preview mode do we widen the dev-server host allowlist and point the
// HMR socket at the proxy's HTTPS entry point; normal development is unchanged.
const previewMode = process.env.BASE44_PREVIEW_MODE === '1';
const sandboxHostDomain = process.env.BASE44_SANDBOX_HOST_DOMAIN;

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    allowedHosts:
      previewMode && sandboxHostDomain ? [`.${sandboxHostDomain}`] : undefined,
    hmr: previewMode ? { clientPort: 443 } : undefined,
    proxy: {
      '/api': {
        target: process.env.API_PROXY_TARGET || 'http://127.0.0.1:3001',
        changeOrigin: true,
      },
    },
  },
});
