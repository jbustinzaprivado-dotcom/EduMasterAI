import { useInfiniteQuery } from "@tanstack/react-query";
import { api } from "../../lib/api";

export interface AuditItem {
  id: string;
  occurred_at: string;
  action: string;
  label: string;
  resource: string;
  resource_id: string | null;
  actor_id: string | null;
  actor_name: string | null;
  organization_id: string | null;
  ip: string | null;
  correlation_id: string | null;
  details: Record<string, unknown> | null;
}

interface AuditPage {
  items: AuditItem[];
  next_cursor: string | null;
}

/** Bitácora paginada por cursor (§10.1). El backend decide qué ve cada rol. */
export function useActivity(action: string, limit = 20) {
  return useInfiniteQuery({
    queryKey: ["audit", action, limit],
    initialPageParam: null as string | null,
    queryFn: ({ pageParam }) => {
      const params = new URLSearchParams({ limit: String(limit) });
      if (action) params.set("action", action);
      if (pageParam) params.set("cursor", pageParam);
      return api<AuditPage>(`/audit-logs?${params}`);
    },
    getNextPageParam: (last) => last.next_cursor,
  });
}

export const ACTION_TONE: Record<string, "cyan" | "teal" | "violet" | "danger" | "muted"> = {
  "auth.login": "teal",
  "auth.logout": "muted",
  "auth.login_failed": "danger",
  "auth.refresh_reuse": "danger",
  "org.created": "violet",
  "user.created": "cyan",
  "user.updated": "cyan",
  "user.roles_changed": "violet",
};
