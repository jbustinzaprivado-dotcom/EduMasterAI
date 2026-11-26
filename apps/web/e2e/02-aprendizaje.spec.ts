import { expect, test } from "@playwright/test";
import { login } from "./helpers";

test.describe.configure({ mode: "serial" });

test.describe("Aprendizaje del estudiante (§4.3, §4.5)", () => {
  test("marcar una actividad sube el progreso", async ({ page }) => {
    // ML-301 está a mitad de ciclo: nadie lo completó, siempre hay actividades pendientes.
    await login(page, "ANDINO", "estudiante3@andino.demo");
    await page.goto("/cursos");
    await page.getByRole("link", { name: /Introducción al Machine Learning/ }).click();
    const progress = page.locator("section").filter({ hasText: "Mi avance" }).locator("p.text-3xl");
    const before = Number((await progress.textContent())!.replace(/\D/g, ""));
    await page.getByRole("button", { name: "Marcar como completada" }).first().click();
    await expect(async () => {
      const after = Number((await progress.textContent())!.replace(/\D/g, ""));
      expect(after).toBeGreaterThan(before);
    }).toPass({ timeout: 10_000 });
  });

  test("IA Tutor responde con sugerencias explicadas y se pueden aceptar", async ({ page }) => {
    await login(page, "ANDINO", "estudiante@andino.demo");
    await page.goto("/tutor");
    await page.getByRole("button", { name: "¿Qué hago ahora?" }).click();
    await expect(page.getByText("Te sugiero esto")).toBeVisible();
    const title = (await page.locator("article h3").first().textContent())!;
    const card = page.locator("article").filter({ has: page.getByRole("heading", { name: title }) });
    await expect(card.getByText("Por qué:")).toBeVisible();
    // D55: un solo botón de acción; ir a hacerlo cuenta como aceptar.
    await expect(card.getByText(/^Prioridad: /)).toBeVisible();
    await card.getByRole("link").first().click();
    await page.goto("/recomendaciones");
    await expect(page.locator("article").filter({ has: page.getByRole("heading", { name: title }) }).getByText("aceptada")).toBeVisible();
  });

  test("mis recomendaciones: historial con el motivo de cierre y cómo me han servido (D55)", async ({ page }) => {
    await login(page, "ANDINO", "estudiante@andino.demo");
    await page.goto("/recomendaciones");
    await expect(page.getByRole("tab", { name: /Vigentes/ })).toHaveAttribute("aria-selected", "true");
    await page.getByRole("tab", { name: "Cómo me han servido" }).click();
    await expect(page.getByText("Recibidas", { exact: true })).toBeVisible();
    await page.getByRole("tab", { name: "Historial" }).click();
    await expect(page.getByRole("tabpanel")).toBeVisible();
  });

  test("la ruta de aprendizaje muestra las etapas bloqueadas", async ({ page }) => {
    await login(page, "ANDINO", "estudiante@andino.demo");
    await page.goto("/rutas");
    await expect(page.getByRole("heading", { name: "Analista de datos junior" })).toBeVisible();
    await expect(page.getByText("Bloqueado").first()).toBeVisible();
  });
});
