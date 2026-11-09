import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The build lands in frontend/dist, which FastAPI serves. One process, one port, one URL
// — which is what makes the ten-minute setup rule and the hosted deployment the same
// problem solved once.
//
// In development, /api is proxied to the backend so the browser still talks to one
// origin and the session cookie behaves exactly as it will in production.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        // Hard-coded rather than read from the environment: avoiding @types/node for
        // one string keeps the front end's dependency surface smaller, and the dev
        // backend is always on this port.
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
