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

test("recorrido real de una predicción por la red (D51)", async ({ page }) => {
  // El modelo quedó publicado en 06; el docente traza a Valeria (perfil en riesgo) con sus datos actuales.
  await login(page, "ANDINO", "docente@andino.demo");
  await page.getByRole("link", { name: "Red neuronal" }).click();
  const offering = page.getByLabel("Oferta", { exact: true });
  const py101 = await offering.locator("option", { hasText: "PY-101" }).first().getAttribute("value");
  await offering.selectOption(py101!);
  await page.getByLabel("Estudiante", { exact: true }).selectOption({ label: "Valeria Mendoza" });
  const trace = page.getByTestId("trace-svg");
  await expect(trace).toHaveAccessibleName(/Recorrido de la predicción de Valeria Mendoza: \d+ % de riesgo/);
  await expect(page.getByText(/Datos reales · modelo v/)).toBeVisible();
  // La señal llega a la salida: solo la cabeza C tiene valor; las otras están sin entrenar.
  const riskHead = trace.getByRole("button", { name: /Cabezas de salida, C · Riesgo de abandono: 0\.\d{3}/ });
  await expect(riskHead).toBeVisible({ timeout: 5000 });
  await expect(trace.getByRole("button", { name: "Cabezas de salida, A · Finalización: sin entrenar" })).toBeVisible();
  await riskHead.click();
  await expect(page.getByText("Recibe sobre todo de:")).toBeVisible();
  // Al terminar el recorrido, la salida muestra la probabilidad.
  await expect(trace.getByText(/C · Riesgo de abandono · \d+ %/)).toBeVisible({ timeout: 8000 });

  // D52: «Todos los estudiantes» recorre la red con el promedio del grupo.
  await page.getByLabel("Estudiante", { exact: true }).selectOption("todos");
  await expect(trace).toHaveAccessibleName(/Recorrido del grupo de \d+ estudiantes: \d+ % de riesgo promedio/);
  await expect(page.getByText(/^Alto: \d+$/)).toBeVisible();
  // Y «Ver la arquitectura» vuelve al plano de la red.
  await page.getByLabel("Estudiante", { exact: true }).selectOption("");
  await expect(page.getByRole("img", { name: /^Arquitectura/ })).toBeVisible();
});

test("el estudiante no ve el recorrido de su predicción (D22)", async ({ page }) => {
  await login(page, "ANDINO", "estudiante@andino.demo");
  await page.getByRole("link", { name: "Red neuronal" }).click();
  await expect(page.getByRole("heading", { name: "Arquitectura neuronal" })).toBeVisible();
  await expect(page.getByRole("img", { name: /^Arquitectura/ })).toBeVisible();
  await expect(page.getByLabel("Estudiante", { exact: true })).toHaveCount(0);
});
