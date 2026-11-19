import { expect, test } from "@playwright/test";
import { login } from "./helpers";

test.describe.configure({ mode: "serial" });

test("la nota del docente le llega en vivo a la estudiante (§4.6, §10.3)", async ({ browser }) => {
  // Dos navegadores a la vez: la estudiante con el canal en vivo abierto y el docente calificando.
  const estCtx = await browser.newContext();
  const est = await estCtx.newPage();
  await login(est, "ANDINO", "estudiante@andino.demo");
  await expect(est.getByText(/En vivo/)).toBeVisible({ timeout: 15_000 });

  await est.goto("/evaluaciones");
  const finalRow = est.locator("li").filter({ hasText: "Examen final" });
  await finalRow.getByRole("button", { name: "Entregar" }).click();
  await est.getByLabel("Tu respuesta").fill("Respuesta desde la prueba E2E");
  await est.getByRole("button", { name: "Entregar" }).last().click();
  await expect(finalRow.getByText("Entregada · por calificar")).toBeVisible();

  const docCtx = await browser.newContext();
  const doc = await docCtx.newPage();
  await login(doc, "ANDINO", "docente@andino.demo");
  await doc.goto("/evaluaciones");
  await doc.locator("li").filter({ hasText: "Examen final" }).filter({ hasText: "Fundamentos de Python" })
    .getByRole("button", { name: "Calificar" }).click();
  const attempt = doc.locator("li").filter({ hasText: "Valeria Mendoza" });
  await attempt.getByLabel("Nota de Valeria Mendoza").fill("17");
  await attempt.getByRole("button", { name: "Calificar" }).click();
  await expect(attempt.getByRole("button", { name: "Corregir" })).toBeVisible();

  // Sin recargar: aviso emergente y contador en la campana.
  await expect(est.getByText("Nota publicada: Examen final")).toBeVisible({ timeout: 10_000 });
  await expect(est.getByRole("button", { name: /Notificaciones, \d+ sin leer/ })).toBeVisible();
  await estCtx.close();
  await docCtx.close();
});

test("el docente ve la lista con progreso y crea un anuncio en la comunidad", async ({ page }) => {
  await login(page, "ANDINO", "docente@andino.demo");
  await page.goto("/cursos");
  await page.getByRole("link", { name: /Fundamentos de Python/ }).click();
  await expect(page.getByRole("heading", { name: "Estudiantes" })).toBeVisible();
  await expect(page.getByText("Valeria Mendoza").first()).toBeVisible();

  await page.goto("/comunidad");
  await page.getByLabel("Curso").selectOption({ label: "Fundamentos de Python · Grupo A" });
  await page.getByRole("button", { name: "Anuncio (notifica a todos)" }).click();
  await page.getByLabel("Título").fill("Repaso del jueves");
  await page.getByLabel("Mensaje").fill("Nos vemos a las 7 p. m. para repasar funciones.");
  await page.getByRole("button", { name: "Publicar" }).click();
  await expect(page.getByText("Repaso del jueves")).toBeVisible();
});
