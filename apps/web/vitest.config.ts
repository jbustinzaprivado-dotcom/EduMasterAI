import { defineConfig } from "vitest/config";

// Vitest solo corre pruebas unitarias de src/. Las de e2e/ son de Playwright (npm run e2e).
export default defineConfig({
  test: { include: ["src/**/*.test.ts"], environment: "node" },
});
