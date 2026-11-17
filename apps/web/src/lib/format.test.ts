import { describe, expect, it } from "vitest";
import { relativeTime, variation } from "./format";

describe("variation", () => {
  it("calcula el porcentaje frente al periodo anterior", () => {
    expect(variation(15, 10)).toBe(50);
    expect(variation(5, 10)).toBe(-50);
  });
  it("no inventa una variación sin base de comparación", () => {
    expect(variation(3, 0)).toBeNull();
    expect(variation(3, null)).toBeNull();
  });
});

describe("relativeTime", () => {
  it("expresa minutos y horas", () => {
    const now = Date.parse("2026-11-17T12:00:00Z");
    expect(relativeTime("2026-11-17T11:59:30Z", now)).toBe("hace un momento");
    expect(relativeTime("2026-11-17T11:45:00Z", now)).toBe("hace 15 min");
    expect(relativeTime("2026-11-17T09:00:00Z", now)).toBe("hace 3 h");
  });
});
