import { expect, test } from "@playwright/test";
import { login } from "./helpers";

test("mapa mundial con los estudiantes DEMO en Sudamérica y vista del Perú (D47)", async ({ page }) => {
  await login(page, "ANDINO", "admin@andino.demo");
  const map = page.locator("section").filter({ hasText: "Mapa de progreso de aprendizaje" }).first();
  await expect(map.getByRole("img", { name: /Mapa mundial/ })).toBeVisible();
  const continents = map.getByRole("list", { name: "Estudiantes por continente" });
  await expect(continents.getByText("América del Sur")).toBeVisible();
  await expect(continents.getByText("Europa")).toBeVisible();
  await map.getByRole("tab", { name: "Perú" }).click();
  await expect(map.getByText("LIM", { exact: true })).toBeVisible();
});

test("la red neuronal aparece capa por capa y simula por capas (D48)", async ({ page }) => {
  await login(page, "ANDINO", "admin@andino.demo");
  const net = page.getByRole("img", { name: /^Arquitectura/ }).first();
  // La primera capa aparece de inmediato; la de salida, cuando la red termina de armarse.
  await expect(net.getByRole("button", { name: "Capa Entrada" })).toBeVisible();
  await expect(net.getByRole("button", { name: "Capa Cabezas de salida" })).toBeVisible({ timeout: 5000 });
  await page.getByRole("button", { name: "Simular" }).first().click();
  // Sin modelo publicado dice "SIMULACIÓN DEMO"; con modelo publicado, "Ilustración del recorrido de la inferencia".
  await expect(page.getByText(/SIMULACIÓN DEMO|Ilustración del recorrido/).first()).toBeVisible();
  await page.getByRole("button", { name: "Pausar" }).first().click();
});
