import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { login, logout, PASSWORD } from "./helpers";

test.describe("Acceso y permisos (§3, §11)", () => {
  test("credenciales incorrectas muestran mensaje genérico", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Código de institución").fill("ANDINO");
    await page.getByLabel("Correo").fill("admin@andino.demo");
    await page.getByLabel("Contraseña").fill("incorrecta");
    await page.getByRole("button", { name: "Entrar" }).click();
    await expect(page.getByRole("alert")).toHaveText("Institución, correo o contraseña incorrectos.");
  });

  test("una ruta protegida sin sesión lleva al login", async ({ page }) => {
    await page.goto("/administracion/usuarios");
    await expect(page).toHaveURL(/\/login$/);
  });

  test("la sesión sobrevive a recargar la página y se cierra con logout", async ({ page }) => {
    await login(page, "ANDINO", "admin@andino.demo");
    await page.reload();
    await expect(page.getByRole("heading", { name: /Hola, Martín/ })).toBeVisible();
    await logout(page);
    await page.goto("/");
    await expect(page).toHaveURL(/\/login$/);
  });

  test("el estudiante no ve módulos de gestión ni entra por URL", async ({ page }) => {
    await login(page, "ANDINO", "estudiante@andino.demo");
    const nav = page.getByRole("navigation", { name: "Módulos" });
    await expect(nav.getByRole("link", { name: "Mis cursos" }).or(nav.getByRole("link", { name: "Cursos" }))).toBeVisible();
    await expect(nav.getByRole("link", { name: "Usuarios y roles" })).toHaveCount(0);
    await page.goto("/administracion/usuarios");
    await expect(page.getByText("Sin permiso")).toBeVisible();
  });

  test("el login y el resumen no tienen fallas de accesibilidad críticas", async ({ page }) => {
    await page.goto("/login");
    const loginScan = await new AxeBuilder({ page }).analyze();
    expect(loginScan.violations.filter((v) => v.impact === "critical")).toEqual([]);
    await login(page, "ANDINO", "docente@andino.demo");
    await expect(page.getByText("Indicadores")).toBeVisible();
    const dash = await new AxeBuilder({ page }).analyze();
    expect(dash.violations.filter((v) => v.impact === "critical").map((v) => v.id)).toEqual([]);
  });

  test("en celular no hay desplazamiento horizontal", async ({ browser }) => {
    const context = await browser.newContext({ viewport: { width: 375, height: 812 }, isMobile: true });
    const page = await context.newPage();
    await page.goto("/login");
    await page.getByLabel("Código de institución").fill("ANDINO");
    await page.getByLabel("Correo").fill("estudiante@andino.demo");
    await page.getByLabel("Contraseña").fill(PASSWORD);
    await page.getByRole("button", { name: "Entrar" }).click();
    await expect(page.getByRole("button", { name: "Abrir menú" })).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
    expect(overflow).toBe(false);
    await context.close();
  });
});
