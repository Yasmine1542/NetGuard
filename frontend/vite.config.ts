import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev proxy mirrors the production nginx edge routing: each /api and /ws prefix
// goes to the service that owns it. Specific prefixes are listed before /api so
// they win (Vite matches proxy keys in order).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      "/api/aiops": "http://localhost:8004", // aiops-engine
      "/api/incidents": "http://localhost:8004", // aiops-engine
      "/api/inject": "http://localhost:8002", // collector
      "/api": "http://localhost:8003", // backend-api (status, metrics, live-stats, cluster, prometheus, loki)
      "/ws/aiops": { target: "ws://localhost:8004", ws: true }, // aiops-engine
      "/ws": { target: "ws://localhost:8003", ws: true }, // backend-api live predictions
    },
  },
});
