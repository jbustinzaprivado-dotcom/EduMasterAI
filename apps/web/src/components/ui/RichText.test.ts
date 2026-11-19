import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { RichText } from "./RichText";

const html = (text: string) => renderToStaticMarkup(createElement(RichText, { text }));

describe("RichText", () => {
  it("convierte títulos, listas, negrita y código", () => {
    const out = html("## Idea\n- uno\n- **dos**\nUsa `print()`");
    expect(out).toContain("<h3");
    expect(out).toContain("<li>uno</li>");
    expect(out).toContain("<strong");
    expect(out).toContain("<code");
  });

  it("nunca interpreta HTML del contenido (XSS)", () => {
    const out = html('<script>alert(1)</script>\n<img src=x onerror="alert(2)">');
    expect(out).not.toContain("<script>");
    expect(out).not.toContain("<img");
    expect(out).toContain("&lt;script&gt;");
  });
});
