import { expect, test } from "@playwright/test";
import { login } from "./helpers";

test("operación: métricas reales frente a los objetivos de §10.5 (D41)", async ({ page }) => {
  await login(page, "ANDINO", "admin@andino.demo");
  await page.getByRole("link", { name: "Operación" }).click();
  await expect(page.getByRole("heading", { name: "Operación" })).toBeVisible();
  await expect(page.getByText("Latencia p95 (todas las rutas)")).toBeVisible();
  await expect(page.getByText("/api/v1/dashboard/summary").first()).toBeVisible();
});

test("vuelta atrás: retirar el modelo con motivo y volver a publicarlo (§16.3, D44)", async ({ page }) => {
  await login(page, "ANDINO", "admin@andino.demo");
  await page.getByRole("link", { name: "Modelos de IA" }).click();
  const approve = page.getByRole("button", { name: "Aprobar publicación" });
  if (await approve.isVisible()) {
    await approve.click();
    await page.getByRole("button", { name: "Sí, aprobar" }).click();
  }
  await page.getByRole("button", { name: "Retirar" }).click();
  const confirm = page.getByRole("button", { name: "Sí, retirar" });
  await expect(confirm).toBeDisabled(); // el motivo es obligatorio
  await page.getByLabel("Motivo (obligatorio)").fill("Prueba E2E de rollback");
  await confirm.click();
  await expect(page.getByText("Candidato · requiere aprobación")).toBeVisible();
  // Se vuelve a publicar para dejar la demo como estaba.
  await page.getByRole("button", { name: "Aprobar publicación" }).click();
  await page.getByRole("button", { name: "Sí, aprobar" }).click();
  await expect(page.getByText("Publicado en tu institución")).toBeVisible();
});
