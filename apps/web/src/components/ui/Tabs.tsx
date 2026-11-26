import { useId, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { useSearchParams } from "react-router";
import { cx } from "./index";

export interface TabItem {
  id: string;
  label: string;
  /** Contador o etiqueta corta junto al nombre (p. ej. cuántos reportes hay). */
  badge?: ReactNode;
  content: ReactNode;
}

/**
 * Pestañas accesibles (D54) para ordenar módulos con mucha información.
 * - Con `param`, la pestaña activa queda en la URL (?param=id): se puede enlazar y sobrevive a recargar.
 * - Solo se dibuja el contenido de la pestaña activa; con una sola pestaña no se muestra la barra.
 * - Teclado: flechas izquierda/derecha, Inicio y Fin (patrón WAI-ARIA de pestañas).
 */
export function Tabs({ items, label, param }: { items: TabItem[]; label: string; param?: string }) {
  const [params, setParams] = useSearchParams();
  const [local, setLocal] = useState(items[0]?.id ?? "");
  const base = useId();
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});
  const wanted = param ? params.get(param) : local;
  const active = items.find((t) => t.id === wanted)?.id ?? items[0]?.id ?? "";

  const select = (id: string) => {
    if (param) {
      const next = new URLSearchParams(params);
      if (id === items[0]?.id) next.delete(param); else next.set(param, id);
      setParams(next, { replace: true });
    } else setLocal(id);
  };
  const onKey = (e: KeyboardEvent) => {
    const i = items.findIndex((t) => t.id === active);
    const to = e.key === "ArrowRight" ? (i + 1) % items.length : e.key === "ArrowLeft" ? (i - 1 + items.length) % items.length
      : e.key === "Home" ? 0 : e.key === "End" ? items.length - 1 : -1;
    if (to < 0) return;
    e.preventDefault();
    select(items[to]!.id);
    refs.current[items[to]!.id]?.focus();
  };

  if (items.length === 1) return <>{items[0]!.content}</>;
  const current = items.find((t) => t.id === active);
  return (
    <div className="flex flex-col gap-4">
      <div role="tablist" aria-label={label} className="flex gap-1 overflow-x-auto border-b border-line" onKeyDown={onKey}>
        {items.map((t) => {
          const on = t.id === active;
          return (
            <button key={t.id} ref={(el) => { refs.current[t.id] = el; }} type="button" role="tab" id={`${base}-${t.id}`}
              aria-selected={on} aria-controls={`${base}-${t.id}-panel`} tabIndex={on ? 0 : -1} onClick={() => select(t.id)}
              className={cx("-mb-px flex shrink-0 items-center gap-1.5 border-b-2 px-3.5 py-2 text-sm transition-colors",
                on ? "border-cyan font-medium text-cyan" : "border-transparent text-muted hover:text-text")}>
              {t.label}{t.badge}
            </button>
          );
        })}
      </div>
      <div role="tabpanel" id={`${base}-${active}-panel`} aria-labelledby={`${base}-${active}`} className="flex flex-col gap-4">
        {current?.content}
      </div>
    </div>
  );
}
