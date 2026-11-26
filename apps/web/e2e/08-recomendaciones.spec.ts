import { expect, test } from "@playwright/test";
import { login } from "./helpers";

test("docente: acciones sugeridas para sus grupos y sugerencias de cada estudiante (D55)", async ({ page }) => {
  await login(page, "ANDINO", "docente@andino.demo");
  await page.getByRole("link", { name: "Recomendaciones" }).click();
  await expect(page.getByRole("tab", { name: "Acciones sugeridas" })).toHaveAttribute("aria-selected", "true");
  // Cada acción dice qué hacer, en qué grupo y por qué, con un botón que lleva a hacerlo.
  const first = page.locator("li.panel").first();
  await expect(first).toBeVisible();
  await expect(first.getByRole("link")).toHaveAttribute("href", /^\//);
  await page.getByRole("tab", { name: "Sugerencias de mis grupos" }).click();
  const offering = page.getByLabel("Oferta", { exact: true });
  const py101 = await offering.locator("option", { hasText: "PY-101" }).first().getAttribute("value");
  await offering.selectOption(py101!);
  await expect(page.getByText("Valeria Mendoza").first()).toBeVisible();
});

test("gestión: métricas por tipo, evolución semanal, por curso y motivos de descarte (D55)", async ({ page }) => {
  await login(page, "ANDINO", "admin@andino.demo");
  await page.goto("/recomendaciones?seccion=metricas");
  await expect(page.getByText("Aceptación y utilidad por tipo")).toBeVisible();
  await expect(page.getByText("Evolución semanal")).toBeVisible();
  await expect(page.getByText("Motivos de descarte más frecuentes")).toBeVisible();
});
