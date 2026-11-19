import { expect, test } from "@playwright/test";
import { login, logout } from "./helpers";

test.describe.configure({ mode: "serial" });

test("el estudiante abre una lección con contenido y recursos (§4.3)", async ({ page }) => {
  await login(page, "ANDINO", "estudiante@andino.demo");
  await page.goto("/cursos");
  await page.getByRole("link", { name: /Fundamentos de Python/ }).click();
  await page.getByRole("link", { name: "Instalación del entorno" }).click();
  await expect(page.getByRole("heading", { name: "Instalación del entorno" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Objetivo" })).toBeVisible();
  await expect(page.getByRole("link", { name: /Descargar Python/ })).toHaveAttribute("href", /^https:\/\//);
  await expect(page.getByRole("button", { name: "Editar contenido" })).toHaveCount(0);
  await page.getByRole("link", { name: /Siguiente/ }).click();
  await expect(page.getByRole("heading", { name: "Variables y tipos de datos" })).toBeVisible();
});

test("el docente edita una lección y sube la versión", async ({ page }) => {
  await login(page, "ANDINO", "docente@andino.demo");
  await page.goto("/cursos");
  await page.getByRole("link", { name: /Fundamentos de Python/ }).click();
  await page.getByRole("link", { name: "Condicionales" }).click();
  await page.getByRole("button", { name: "Editar contenido" }).click();
  await page.getByLabel(/Contenido/).fill("## Repaso\n- `if` evalúa una condición\n- **Ojo** con la sangría");
  await page.getByRole("button", { name: "Guardar (nueva versión)" }).click();
  await expect(page.getByRole("heading", { name: "Repaso" })).toBeVisible();
  await expect(page.getByText(/Versión 2 · editada por Jorge Huamán/)).toBeVisible();
});

test("restablecer contraseña obliga a elegir una nueva (§11.1)", async ({ page }) => {
  await login(page, "ANDINO", "admin@andino.demo");
  await page.goto("/administracion/usuarios");
  await page.getByLabel("Buscar usuarios").fill("Karen");
  page.once("dialog", (d) => d.accept());
  await page.getByRole("button", { name: "Restablecer contraseña de Karen Silva" }).click();
  const temp = (await page.locator("[aria-label='Contraseña temporal'] p.font-mono").textContent())!.trim();
  await page.getByRole("button", { name: "Entendido" }).click();
  await logout(page);

  await page.getByLabel("Código de institución").fill("ANDINO");
  await page.getByLabel("Correo").fill("estudiante12@andino.demo");
  await page.getByLabel("Contraseña").fill(temp);
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page.getByRole("heading", { name: "Elige tu nueva contraseña" })).toBeVisible();
  await page.getByLabel("Contraseña temporal").fill(temp);
  await page.getByLabel("Nueva contraseña", { exact: true }).fill("KarenElige-2026");
  await page.getByLabel("Repite la nueva contraseña").fill("KarenElige-2026");
  await page.getByRole("button", { name: "Cambiar contraseña" }).click();
  await expect(page.getByRole("navigation", { name: "Módulos" })).toBeVisible();
});
