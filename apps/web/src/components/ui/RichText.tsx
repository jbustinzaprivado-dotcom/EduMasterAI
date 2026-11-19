import type { ReactNode } from "react";

/**
 * Formato ligero para el contenido de las lecciones, SIN HTML (§11: XSS).
 * Soporta: "## título", listas con "- ", **negrita** y `código`. Todo lo demás se muestra como texto.
 * React escapa cada fragmento: aunque el contenido traiga <script>, se ve como texto plano.
 */
function inline(text: string, keyBase: string): ReactNode[] {
  const parts: ReactNode[] = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    const token = m[0];
    parts.push(token.startsWith("**")
      ? <strong key={`${keyBase}-${i++}`} className="font-semibold text-text">{token.slice(2, -2)}</strong>
      : <code key={`${keyBase}-${i++}`} className="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-[0.85em] text-cyan">{token.slice(1, -1)}</code>);
    last = m.index + token.length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

export function RichText({ text }: { text: string }) {
  const blocks: ReactNode[] = [];
  let list: string[] = [];
  const flush = (key: string) => {
    if (list.length) {
      blocks.push(<ul key={key} className="my-2 list-inside list-disc space-y-1">{list.map((li, i) => <li key={i}>{inline(li, `${key}-${i}`)}</li>)}</ul>);
      list = [];
    }
  };
  text.split("\n").forEach((raw, n) => {
    const line = raw.trimEnd();
    if (line.startsWith("- ")) {
      list.push(line.slice(2));
      return;
    }
    flush(`l${n}`);
    if (line.startsWith("## ")) blocks.push(<h3 key={n} className="mt-4 mb-1 text-base font-semibold text-cyan">{inline(line.slice(3), `h${n}`)}</h3>);
    else if (line.trim()) blocks.push(<p key={n} className="my-1.5">{inline(line, `p${n}`)}</p>);
  });
  flush("end");
  return <div className="text-sm leading-relaxed text-text/90">{blocks}</div>;
}
