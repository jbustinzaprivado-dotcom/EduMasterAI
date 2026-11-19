import { expect, type Page } from "@playwright/test";

export const PASSWORD = process.env.E2E_PASSWORD ?? "ClaveE2E-2026";

/** Inicia sesión como lo haría una persona: escribe en el formulario y pulsa "Entrar". */
export async function login(page: Page, org: string, email: string) {
  await page.goto("/login");
  await page.getByLabel("Código de institución").fill(org);
  await page.getByLabel("Correo").fill(email);
  await page.getByLabel("Contraseña").fill(PASSWORD);
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page.getByRole("navigation", { name: "Módulos" })).toBeVisible();
}

export async function logout(page: Page) {
  await page.getByRole("button", { name: "Perfil" }).click();
  await page.getByRole("button", { name: "Cerrar sesión" }).click();
  await expect(page).toHaveURL(/\/login$/);
}
