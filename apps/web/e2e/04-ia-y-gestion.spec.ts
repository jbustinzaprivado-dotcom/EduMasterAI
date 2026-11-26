import { expect, test } from "@playwright/test";
import { login, logout } from "./helpers";

test.describe.configure({ mode: "serial" });

test("aprobación humana del modelo y alerta de riesgo para el docente (§9.6-§9.8)", async ({ page }) => {
  await login(page, "ANDINO", "admin@andino.demo");
  await page.goto("/modelos");
  await expect(page.getByText("Candidato · requiere aprobación")).toBeVisible();
  await page.getByRole("button", { name: "Aprobar publicación" }).click();
  await page.getByRole("button", { name: "Sí, aprobar" }).click();
  await expect(page.getByText("Publicado en tu institución")).toBeVisible();
  await logout(page);

  await login(page, "ANDINO", "docente@andino.demo");
  await page.goto("/cursos");
  await page.getByRole("link", { name: /Fundamentos de Python/ }).click();
  await page.getByRole("tab", { name: "Estudiantes y riesgo" }).click();
  await page.getByRole("button", { name: "Actualizar riesgo con IA" }).click();
  // Los estudiantes DEMO "en riesgo" llevan semanas sin entrar: el modelo debe marcar al menos uno en alto.
  const alert = page.locator("tr").filter({ has: page.getByRole("button", { name: /Riesgo alto/ }) }).first();
  await expect(alert).toBeVisible({ timeout: 15_000 });
  await alert.getByRole("button", { name: /Riesgo alto/ }).click();
  await expect(page.getByText(/Es un apoyo, no un diagnóstico/)).toBeVisible();
  await page.getByRole("button", { name: "Marcar atendida" }).click();
  await expect(page.getByText("atendida").first()).toBeVisible();
});

test("certificado: verificación pública sin sesión (§4.7)", async ({ page, browser }) => {
  await login(page, "ANDINO", "admin@andino.demo");
  await page.goto("/certificados");
  const code = (await page.locator("article dd.font-mono").nth(1).textContent())!.trim();
  expect(code).toMatch(/^[A-Z0-9]{10}$/);

  const anon = await browser.newContext();
  const pub = await anon.newPage();
  await pub.goto(`/verificar/${code}`);
  await expect(pub.getByText("Certificado válido")).toBeVisible();
  await expect(pub.getByText("Solo se muestran datos mínimos")).toBeVisible();
  await pub.goto("/verificar/NOEXISTE00");
  await expect(pub.getByText("No existe un certificado con ese código.")).toBeVisible();
  await anon.close();
});

test("analítica: filtrar y exportar a CSV queda auditado (§4.4)", async ({ page }) => {
  await login(page, "ANDINO", "admin@andino.demo");
  await page.goto("/analitica");
  await expect(page.getByText("Participación").first()).toBeVisible();
  await page.getByLabel("Oferta").selectOption({ label: "DS-201 · Grupo A · 2026-II" });
  await page.getByRole("tab", { name: /Por oferta/ }).click();
  await expect(page.locator("table").first().getByText("DS-201 · Grupo A")).toBeVisible();
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.locator("section").filter({ hasText: "Por oferta" }).getByRole("button", { name: "CSV" }).click(),
  ]);
  expect(download.suggestedFilename()).toMatch(/\.csv$/);
  await page.goto("/actividad");
  await page.getByLabel("Filtrar por acción").selectOption({ label: "Todas las acciones" });
  await expect(page.getByText("Exportó un reporte de analítica").first()).toBeVisible();
});

test("dominio de habilidades: el docente valida el nivel oficial (§4.9)", async ({ page }) => {
  await login(page, "ANDINO", "docente@andino.demo");
  await page.goto("/habilidades");
  await expect(page.getByText("Sintaxis de Python").first()).toBeVisible();
  await page.getByLabel("Oferta").selectOption({ label: "PY-101 · Grupo A" });
  await page.getByRole("tab", { name: "Por estudiante y validación" }).click();
  await page.getByLabel("Estudiante", { exact: true }).selectOption({ label: "Valeria Mendoza" });
  const card = page.locator("div.rounded-xl").filter({ hasText: "Sintaxis de Python" }).first();
  await card.getByLabel("Nivel validado").selectOption({ label: "avanzado" });
  await card.getByLabel("Nota de validación").fill("Explicó bien variables y tipos en clase.");
  await card.getByRole("button", { name: "Validar" }).click();
  await expect(card.getByText("Explicó bien variables y tipos en clase.")).toBeVisible();
});
