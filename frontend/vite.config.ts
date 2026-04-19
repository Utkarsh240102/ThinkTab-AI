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
        target:    'http://localhost:8000',
        changeOrigin: true,
        rewrite:   (path) => path,   // Keep /api/chat as-is
      },
    },
  },
})
