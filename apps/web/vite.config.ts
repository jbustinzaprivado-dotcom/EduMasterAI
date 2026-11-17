import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// En desarrollo la web (5173) reenvía /api a FastAPI (8000): mismo origen, sin CORS.
// En la demo, FastAPI sirve la carpeta dist directamente (decisión D03).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
});
