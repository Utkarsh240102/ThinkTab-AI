import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],

  server: {
    port: 5173,
    /* Proxy /api/* requests to the FastAPI backend.
       This avoids CORS issues during development — the browser
       thinks everything is on the same origin (localhost:5173).
       In production (Chrome Extension), we call the backend directly. */
    proxy: {
      '/api': {
        target:    'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite:   (path) => path,   // Keep /api/chat as-is
      },
    },
  },

  /* ── Chrome Extension Build Setup ── */
  // Forces Vite to use relative paths (e.g. ./assets/styles.css) 
  // instead of absolute paths (/assets/styles.css) which completely breaks Chrome Extensions.
  base: './',
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  }
})
