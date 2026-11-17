import { useQueryClient } from "@tanstack/react-query";
import { createContext, use, useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import * as client from "./api";

interface AuthState {
  user: client.Me | null;
  loading: boolean;
  signIn: (org: string, email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  can: (permission: string) => boolean;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<client.Me | null>(null);
  const [loading, setLoading] = useState(true);
  const queryClient = useQueryClient();

  useEffect(() => {
    // Al abrir la página se intenta recuperar la sesión con la cookie de renovación.
    client.setSessionLostHandler(() => setUser(null));
    client.refreshSession().then((me) => {
      setUser(me);
      setLoading(false);
    });
  }, []);

  const signIn = useCallback(async (org: string, email: string, password: string) => {
    setUser(await client.login(org, email, password));
  }, []);

  const signOut = useCallback(async () => {
    await client.logout();
    queryClient.clear(); // no dejar datos de la sesión anterior en caché
    setUser(null);
  }, [queryClient]);

  const value = useMemo<AuthState>(
    () => ({
      user,
      loading,
      signIn,
      signOut,
      can: (permission) => user?.permissions.includes(permission) ?? false,
    }),
    [user, loading, signIn, signOut],
  );

  return <AuthContext value={value}>{children}</AuthContext>;
}

export function useAuth(): AuthState {
  const ctx = use(AuthContext);
  if (!ctx) throw new Error("useAuth debe usarse dentro de AuthProvider");
  return ctx;
}

/** Nombres visibles de los roles (§3). */
export const ROLE_LABELS: Record<string, string> = {
  superadmin: "Superadministrador",
  admin: "Administrador institucional",
  coordinador: "Director / coordinador",
  docente: "Docente",
  estudiante: "Estudiante",
  analista: "Analista de datos",
  ml_engineer: "ML Engineer",
  auditor: "Auditor",
};
