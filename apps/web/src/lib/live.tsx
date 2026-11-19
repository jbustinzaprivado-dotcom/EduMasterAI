import { useQueryClient } from "@tanstack/react-query";
import { createContext, use, useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { currentAccessToken, refreshSession } from "./api";
import { useAuth } from "./auth";

/**
 * Canal en vivo por Server-Sent Events (§10.3, D28).
 * Se usa fetch (no EventSource) para enviar el token en la cabecera Authorization, nunca en la URL.
 * Reconecta con espera creciente y envía Last-Event-ID para recuperar lo perdido (§13.1 criterio 26).
 */

export interface LiveNotification {
  id: string;
  kind: string;
  title: string;
  body: string;
  link: string | null;
  created_at: string;
  read_at: string | null;
}

type Status = "conectando" | "en vivo" | "reconectando" | "desconectado";

interface LiveState {
  status: Status;
  toasts: LiveNotification[];
  dismiss: (id: string) => void;
}

const LiveContext = createContext<LiveState>({ status: "desconectado", toasts: [], dismiss: () => {} });

// Qué datos de la pantalla se refrescan según el tipo de evento.
const INVALIDATE: Record<string, string[][]> = {
  "grade.recorded": [["assessments"], ["recommendations"], ["dashboard"]],
  "assessment.created": [["assessments"], ["recommendations"]],
  "enrollment.created": [["offerings"], ["dashboard"]],
  "course.completed": [["offerings"], ["dashboard"], ["certificates"]],
  "certificate.issued": [["certificates"]],
  "certificate.revoked": [["certificates"]],
  "risk.alerts": [["risk"], ["dashboard"]],
  "model.published": [["ml"]],
  "community.announcement": [["community"]],
  "community.reply": [["community"]],
  "community.report": [["community"]],
  "path.assigned": [["paths"]],
  "path.completed": [["paths"]],
  "skill.validated": [["skills"]],
};

export function parseSSE(buffer: string): { events: { id?: string; event: string; data: string }[]; rest: string } {
  const blocks = buffer.split("\n\n");
  const rest = blocks.pop() ?? "";
  const events = blocks.flatMap((block) => {
    let id: string | undefined;
    let event = "message";
    const data: string[] = [];
    for (const line of block.split("\n")) {
      if (line.startsWith(":")) continue; // latido
      const [field, ...value] = line.split(":");
      const v = value.join(":").replace(/^ /, "");
      if (field === "id") id = v;
      else if (field === "event") event = v;
      else if (field === "data") data.push(v);
    }
    return data.length ? [{ id, event, data: data.join("\n") }] : [];
  });
  return { events, rest };
}

export function LiveProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const qc = useQueryClient();
  const [status, setStatus] = useState<Status>("desconectado");
  const [toasts, setToasts] = useState<LiveNotification[]>([]);
  const lastId = useRef<string | null>(null);

  const dismiss = useCallback((id: string) => setToasts((t) => t.filter((x) => x.id !== id)), []);

  useEffect(() => {
    if (!user) return;
    const controller = new AbortController();
    let attempt = 0;

    async function connect() {
      while (!controller.signal.aborted) {
        setStatus(attempt === 0 ? "conectando" : "reconectando");
        try {
          const token = await currentAccessToken();
          const headers: Record<string, string> = { Accept: "text/event-stream" };
          if (token) headers.Authorization = `Bearer ${token}`;
          if (lastId.current) headers["Last-Event-ID"] = lastId.current;
          const r = await fetch("/api/v1/notifications/stream", { headers, signal: controller.signal });
          if (r.status === 401) {
            await refreshSession();
            throw new Error("token vencido");
          }
          if (!r.ok || !r.body) throw new Error(`HTTP ${r.status}`);
          const reader = r.body.pipeThrough(new TextDecoderStream()).getReader();
          let buffer = "";
          for (;;) {
            const { value, done } = await reader.read();
            if (done) break;
            buffer += value;
            const parsed = parseSSE(buffer);
            buffer = parsed.rest;
            for (const e of parsed.events) {
              if (e.event === "ready") {
                attempt = 0;
                setStatus("en vivo");
                continue;
              }
              if (e.event !== "notification") continue;
              const n = JSON.parse(e.data) as LiveNotification;
              lastId.current = e.id ?? n.id;
              qc.invalidateQueries({ queryKey: ["notifications"] });
              for (const key of INVALIDATE[n.kind] ?? []) qc.invalidateQueries({ queryKey: key });
              setToasts((t) => [...t.slice(-2), n]);
              setTimeout(() => setToasts((t) => t.filter((x) => x.id !== n.id)), 6000);
            }
          }
        } catch {
          if (controller.signal.aborted) return;
        }
        attempt += 1;
        setStatus("reconectando");
        await new Promise((res) => setTimeout(res, Math.min(30_000, 1000 * 2 ** Math.min(attempt, 5))));
      }
    }

    connect();
    return () => {
      controller.abort();
      setStatus("desconectado");
    };
  }, [user, qc]);

  return <LiveContext value={{ status, toasts, dismiss }}>{children}</LiveContext>;
}

export function useLive() {
  return use(LiveContext);
}
