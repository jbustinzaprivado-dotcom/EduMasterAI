/**
 * Cliente HTTP de la API (§10.1).
 * - El token de acceso vive solo en memoria (no en localStorage): un script inyectado no puede robarlo.
 * - Si la API responde 401, se renueva una vez con la cookie protegida y se repite la petición.
 * - Cada petición lleva un X-Correlation-ID para rastrearla en los logs del servidor.
 */

export interface ApiErrorBody {
  code: string;
  message: string;
  details: unknown;
  correlation_id: string;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public body: ApiErrorBody,
  ) {
    super(body.message);
  }
}

export interface Organization {
  id: string;
  code: string;
  name: string;
  status: string;
  timezone: string;
  is_platform: boolean;
}

export interface Me {
  id: string;
  email: string;
  full_name: string;
  roles: string[];
  permissions: string[];
  organization: Organization;
  must_change_password: boolean;
}

interface TokenResponse {
  access_token: string;
  expires_in: number;
  user: Me;
}

let accessToken: string | null = null;
let refreshing: Promise<Me | null> | null = null;
let onSessionLost: () => void = () => {};

export function setSessionLostHandler(handler: () => void) {
  onSessionLost = handler;
}

function newCorrelationId(): string {
  return crypto.randomUUID().replaceAll("-", "");
}

async function parseError(response: Response): Promise<ApiError> {
  let body: ApiErrorBody;
  try {
    body = (await response.json()) as ApiErrorBody;
  } catch {
    body = {
      code: "network_error",
      message: `El servidor respondió ${response.status}.`,
      details: null,
      correlation_id: response.headers.get("X-Correlation-ID") ?? "-",
    };
  }
  return new ApiError(response.status, body);
}

/** Renueva la sesión con la cookie. Varias llamadas simultáneas comparten la misma renovación,
 *  porque usar dos veces el mismo token de renovación cerraría la sesión (detección de robo). */
export function refreshSession(): Promise<Me | null> {
  refreshing ??= (async () => {
    try {
      const r = await fetch("/api/v1/auth/refresh", { method: "POST", credentials: "same-origin" });
      if (!r.ok) {
        accessToken = null;
        return null;
      }
      const data = (await r.json()) as TokenResponse;
      accessToken = data.access_token;
      return data.user;
    } catch {
      return null;
    } finally {
      refreshing = null;
    }
  })();
  return refreshing;
}

export async function login(organization_code: string, email: string, password: string): Promise<Me> {
  const r = await fetch("/api/v1/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Correlation-ID": newCorrelationId() },
    body: JSON.stringify({ organization_code, email, password }),
    credentials: "same-origin",
  });
  if (!r.ok) throw await parseError(r);
  const data = (await r.json()) as TokenResponse;
  accessToken = data.access_token;
  return data.user;
}

export async function changePassword(current_password: string, new_password: string): Promise<Me> {
  const user = await api<TokenResponse>("/auth/password", { method: "POST", body: JSON.stringify({ current_password, new_password }) });
  accessToken = user.access_token;
  return user.user;
}

export async function logout(): Promise<void> {
  try {
    await fetch("/api/v1/auth/logout", { method: "POST", credentials: "same-origin" });
  } finally {
    accessToken = null;
  }
}

/** Token vigente para el canal en vivo (se envía en la cabecera, nunca en la URL). */
export async function currentAccessToken(): Promise<string | null> {
  if (!accessToken) await refreshSession();
  return accessToken;
}

/** Descarga binaria autenticada (PDF de certificados). */
export async function apiBlob(path: string, retry = true): Promise<Blob> {
  const headers = new Headers({ "X-Correlation-ID": newCorrelationId() });
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  const r = await fetch(`/api/v1${path}`, { headers, credentials: "same-origin" });
  if (r.status === 401 && retry && (await refreshSession())) return apiBlob(path, false);
  if (!r.ok) throw await parseError(r);
  return r.blob();
}

export async function api<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("X-Correlation-ID", newCorrelationId());
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);

  const r = await fetch(`/api/v1${path}`, { ...init, headers, credentials: "same-origin" });
  if (r.status === 401 && retry) {
    const user = await refreshSession();
    if (user) return api<T>(path, init, false);
    onSessionLost();
  }
  if (!r.ok) throw await parseError(r);
  if (r.status === 204) return undefined as T;
  return (await r.json()) as T;
}
