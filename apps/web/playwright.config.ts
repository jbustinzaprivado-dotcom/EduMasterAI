import { defineConfig, devices } from "@playwright/test";
import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));

/**
 * Pruebas E2E (§13): recorren la web real contra una API aislada con datos DEMO.
 * - Local (Windows): usa el Edge instalado (PW_CHANNEL=msedge por defecto), sin descargar navegadores.
 * - CI: Chromium de Playwright (PW_CHANNEL vacío).
 * Requiere la web compilada (npm run build): la API la sirve en el mismo origen.
 */
const venvPython = resolve(here, "../api/.venv/Scripts/python.exe");
const python = process.env.E2E_PYTHON ?? (existsSync(venvPython) ? venvPython : "python");
const port = Number(process.env.E2E_PORT ?? 8010);
const channel = process.env.PW_CHANNEL ?? (process.platform === "win32" ? "msedge" : undefined);

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1, // comparten una base: el orden importa (p. ej. aprobar el modelo antes de predecir)
  retries: process.env.CI ? 1 : 0,
  timeout: 45_000,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    locale: "es-PE",
    timezoneId: "America/Lima",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "escritorio", use: { ...devices["Desktop Chrome"], ...(channel ? { channel } : {}) } }],
  webServer: {
    command: `"${python}" scripts/e2e_server.py`,
    cwd: resolve(here, "../api"),
    url: `http://127.0.0.1:${port}/api/v1/health/ready`,
    timeout: 120_000,
    reuseExistingServer: false,
    env: { E2E_PORT: String(port) },
  },
});
