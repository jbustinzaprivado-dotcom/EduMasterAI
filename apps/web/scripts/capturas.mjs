// Capturas de pantalla del sistema para la documentación (docs/capturas).
// Recorre la plataforma como lo haría cada rol, sobre una API con datos DEMO limpios (scripts/e2e_server.py).
//
// Uso (con la API aislada en marcha en el puerto 8010):
//   node scripts/capturas.mjs [URL] [CONTRASEÑA]
// Por defecto: http://127.0.0.1:8010 y la contraseña de las pruebas E2E.
import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const BASE = process.argv[2] ?? "http://127.0.0.1:8010";
const PASSWORD = process.argv[3] ?? "ClaveE2E-2026";
const OUT = resolve(dirname(fileURLToPath(import.meta.url)), "../../../docs/capturas");
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch({ channel: process.platform === "win32" ? "msedge" : undefined });
const done = [];
const failed = [];

async function newPage(viewport = { width: 1440, height: 900 }) {
  const ctx = await browser.newContext({ baseURL: BASE, viewport, colorScheme: "dark", locale: "es-PE",
    timezoneId: "America/Lima" });
  return ctx.newPage();
}

async function login(page, org, email) {
  await page.goto("/login");
  await page.getByLabel("Código de institución").fill(org);
  await page.getByLabel("Correo").fill(email);
  await page.getByLabel("Contraseña").fill(PASSWORD);
  await page.getByRole("button", { name: "Entrar" }).click();
  await page.waitForURL((u) => !u.pathname.startsWith("/login")); // en móvil el menú está oculto
}

async function settle(page) {
  // No se espera "networkidle": el canal en vivo (SSE) mantiene una conexión abierta siempre.
  await page.waitForLoadState("load");
  await page.locator(".animate-pulse").first().waitFor({ state: "detached", timeout: 8000 }).catch(() => {});
  await page.waitForTimeout(900); // gráficos y contadores terminan de pintarse
}

async function shot(page, name, { full = false } = {}) {
  await settle(page);
  const size = page.viewportSize();
  if (full) {
    // En vez de fullPage (pinta la barra lateral y la superior a mitad de página), se agranda la ventana.
    const height = await page.evaluate(() => document.documentElement.scrollHeight);
    await page.setViewportSize({ width: size.width, height: Math.min(Math.max(height, size.height), 4200) });
    await page.waitForTimeout(500);
  }
  await page.screenshot({ path: `${OUT}/${name}.jpg`, type: "jpeg", quality: 82 });
  if (full) await page.setViewportSize(size);
  done.push(name);
}

async function step(name, fn) {
  try {
    await fn();
  } catch (err) {
    failed.push(`${name}: ${String(err).split("\n")[0]}`);
  }
}

// ---------- Público ----------
const pub = await newPage();
await step("login", async () => { await pub.goto("/login"); await shot(pub, "01-login"); });

// ---------- Administración ----------
const admin = await newPage();
await step("admin", async () => {
  await login(admin, "ANDINO", "admin@andino.demo");
  await shot(admin, "02-dashboard-admin", { full: true });
  await admin.goto("/modelos");
  await shot(admin, "03-modelo-candidato");
  await admin.getByRole("button", { name: "Aprobar publicación" }).click();
  await shot(admin, "04-modelo-confirmar-aprobacion");
  await admin.getByRole("button", { name: "Sí, aprobar" }).click();
  await admin.getByText("Publicado en tu institución").first().waitFor();
  await shot(admin, "05-modelo-publicado", { full: true });
  await admin.goto("/red-neuronal");
  await settle(admin);
  await admin.getByRole("button", { name: /Capa Bloque temporal/ }).click().catch(() => {});
  await shot(admin, "06-red-neuronal");
});

// ---------- Docente ----------
const doc = await newPage();
await step("docente", async () => {
  await login(doc, "ANDINO", "docente@andino.demo");
  await doc.goto("/cursos");
  await shot(doc, "07-cursos-docente");
  await doc.getByRole("link", { name: /Fundamentos de Python/ }).click();
  await doc.getByRole("tab", { name: "Estudiantes y riesgo" }).click(); // D54: la lista está en su pestaña
  await doc.getByRole("button", { name: "Actualizar riesgo con IA" }).click();
  await doc.getByRole("button", { name: /Riesgo alto/ }).first().waitFor();
  await shot(doc, "08-oferta-riesgo-ia", { full: true });
  await doc.getByRole("button", { name: /Riesgo alto/ }).first().click();
  await doc.getByText(/Es un apoyo, no un diagnóstico/).waitFor();
  await shot(doc, "09-alerta-factores");
  await doc.keyboard.press("Escape").catch(() => {});
  await doc.goto("/cursos");
  await doc.getByRole("link", { name: /Fundamentos de Python/ }).click();
  await settle(doc);
  await doc.locator('a[href*="/actividad/"]').first().click();
  await shot(doc, "10-leccion");
  await doc.goto("/evaluaciones");
  await shot(doc, "11-evaluaciones-docente");
  await doc.goto("/habilidades");
  await settle(doc);
  await doc.getByLabel("Oferta").selectOption({ label: "PY-101 · Grupo A" }).catch(() => {});
  await shot(doc, "12-habilidades-heatmap", { full: true });
  await doc.goto("/comunidad");
  await shot(doc, "13-comunidad");
});

// Recorrido real de una predicción (D51-D53): el docente traza a Valeria (perfil en riesgo).
await step("recorrido", async () => {
  await doc.goto("/red-neuronal");
  await settle(doc);
  const offering = doc.getByLabel("Oferta", { exact: true });
  const py101 = await offering.locator("option", { hasText: "PY-101" }).first().getAttribute("value");
  await offering.selectOption(py101);
  await doc.getByLabel("Estudiante", { exact: true }).selectOption({ label: "Valeria Mendoza" });
  // Se espera a que la señal llegue a la salida y muestre la probabilidad.
  await doc.getByTestId("trace-svg").getByText(/C · Riesgo de abandono · \d+ %/).waitFor({ timeout: 12000 });
  await shot(doc, "26-red-recorrido", { full: true });
});

// Recomendaciones v2 (D55): acciones sugeridas del docente.
await step("acciones-docente", async () => {
  await doc.goto("/recomendaciones");
  await doc.locator("li.panel").first().waitFor();
  await shot(doc, "28-acciones-docente", { full: true });
});

// ---------- Coordinación ----------
const coord = await newPage();
await step("coordinacion", async () => {
  await login(coord, "ANDINO", "coordinacion@andino.demo");
  await coord.goto("/rutas");
  await settle(coord);
  await coord.getByText(/Analista de datos junior/).first().click().catch(() => {});
  await shot(coord, "14-rutas-coordinacion", { full: true });
  await coord.goto("/analitica");
  await shot(coord, "15-analitica", { full: true });
});

// ---------- Estudiante ----------
const est = await newPage();
await step("estudiante", async () => {
  await login(est, "ANDINO", "estudiante@andino.demo");
  await shot(est, "16-dashboard-estudiante", { full: true });
  await est.goto("/tutor");
  await settle(est);
  await est.getByRole("button", { name: "¿Qué hago ahora?" }).first().click();
  await shot(est, "17-ia-tutor");
  await est.goto("/recomendaciones");
  await est.getByRole("tab", { name: /Vigentes/ }).waitFor();
  await shot(est, "27-recomendaciones-estudiante", { full: true });
  await est.goto("/rutas");
  await shot(est, "18-ruta-estudiante");
  await est.getByRole("button", { name: /Notificaciones/ }).click();
  await shot(est, "19-notificaciones");
});

// ---------- Certificados y verificación pública ----------
await step("certificados", async () => {
  await admin.goto("/certificados");
  await shot(admin, "20-certificados");
  const href = await admin.locator('a[href*="/verificar/"]').first().getAttribute("href");
  await pub.goto(new URL(href, BASE).pathname);
  await pub.getByText("Certificado válido").waitFor();
  await shot(pub, "21-verificacion-publica");
});

// ---------- Gestión y operación ----------
await step("gestion", async () => {
  await admin.goto("/actividad");
  await shot(admin, "22-auditoria");
  await admin.goto("/administracion/usuarios");
  await shot(admin, "23-usuarios-roles");
  await admin.goto("/operacion");
  await shot(admin, "24-operacion", { full: true });
  await admin.goto("/recomendaciones?seccion=metricas");
  await admin.getByText("Aceptación y utilidad por tipo").waitFor();
  await shot(admin, "29-recomendaciones-metricas", { full: true });
});

// ---------- Móvil ----------
const mobile = await newPage({ width: 390, height: 844 });
await step("movil", async () => {
  await login(mobile, "ANDINO", "estudiante@andino.demo");
  await shot(mobile, "25-movil-estudiante");
});

await browser.close();
console.log(`Capturas: ${done.length} en ${OUT}`);
if (failed.length) console.log("Fallaron:\n  " + failed.join("\n  "));
