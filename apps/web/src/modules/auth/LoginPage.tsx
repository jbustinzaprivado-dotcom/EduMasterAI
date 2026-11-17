import { KeyRound, LogIn } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Navigate } from "react-router";
import { ApiError } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { Badge, Button } from "../../components/ui";

// Cuentas DEMO creadas por app.seed (sin contraseña: la define el equipo en el .env).
const DEMO_ACCOUNTS = [
  { org: "PLATAFORMA", email: "superadmin@edumaster.demo", role: "Superadministrador" },
  { org: "ANDINO", email: "admin@andino.demo", role: "Administrador" },
  { org: "ANDINO", email: "coordinacion@andino.demo", role: "Coordinador" },
  { org: "ANDINO", email: "docente@andino.demo", role: "Docente" },
  { org: "ANDINO", email: "estudiante@andino.demo", role: "Estudiante" },
  { org: "ANDINO", email: "auditoria@andino.demo", role: "Auditor" },
  { org: "PACIFICO", email: "admin@pacifico.demo", role: "Admin (otra institución)" },
];

export function LoginPage() {
  const { user, signIn } = useAuth();
  const [org, setOrg] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to="/" replace />;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await signIn(org, email, password);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo conectar con el servidor.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="relative flex min-h-full items-center justify-center overflow-hidden px-4 py-10">
      <div aria-hidden className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,rgb(8_127_229/0.22),transparent_45%),radial-gradient(circle_at_80%_80%,rgb(139_77_255/0.18),transparent_45%)]" />
      <div className="relative grid w-full max-w-4xl gap-6 md:grid-cols-[1.1fr_1fr]">
        <div className="flex flex-col justify-center gap-4">
          <img src="/favicon.svg" alt="" className="size-12" />
          <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">
            EduMaster<span className="text-cyan">.ai</span>
          </h1>
          <p className="text-xs font-semibold uppercase tracking-[0.25em] text-muted">Aprende · Practica · Destaca</p>
          <p className="max-w-md text-sm text-muted">
            Plataforma de aprendizaje inteligente: gestión académica, analítica y redes neuronales bajo supervisión humana.
          </p>
          <div className="hidden flex-wrap gap-2 md:flex">
            <Badge tone="cyan">Multi-institución</Badge>
            <Badge tone="violet">Roles y permisos</Badge>
            <Badge tone="teal">Bitácora auditada</Badge>
          </div>
        </div>

        <form onSubmit={submit} className="panel panel-glow flex flex-col gap-4 p-6" noValidate>
          <div>
            <h2 className="text-lg font-semibold">Iniciar sesión</h2>
            <p className="text-xs text-muted">Usa el código de tu institución.</p>
          </div>
          <div>
            <label className="label" htmlFor="org">Código de institución</label>
            <input id="org" className="field uppercase" value={org} onChange={(e) => setOrg(e.target.value)}
              autoComplete="organization" required placeholder="ANDINO" />
          </div>
          <div>
            <label className="label" htmlFor="email">Correo</label>
            <input id="email" type="email" className="field" value={email} onChange={(e) => setEmail(e.target.value)}
              autoComplete="username" required />
          </div>
          <div>
            <label className="label" htmlFor="password">Contraseña</label>
            <input id="password" type="password" className="field" value={password}
              onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
          </div>
          {error && <p role="alert" className="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">{error}</p>}
          <Button type="submit" icon={LogIn} loading={busy} disabled={!org || !email || !password}>
            Entrar
          </Button>

          <details className="rounded-xl border border-line bg-bg/40 p-3 text-xs">
            <summary className="flex cursor-pointer items-center gap-2 text-muted">
              <KeyRound className="size-3.5" /> Cuentas DEMO para la demostración
            </summary>
            <p className="mt-2 text-muted">Completa institución y correo; la contraseña la comparte el equipo.</p>
            <ul className="mt-2 grid gap-1">
              {DEMO_ACCOUNTS.map((a) => (
                <li key={a.email}>
                  <button type="button" onClick={() => { setOrg(a.org); setEmail(a.email); }}
                    className="flex w-full items-center justify-between rounded-lg px-2 py-1.5 text-left hover:bg-surface-2">
                    <span>{a.role}</span>
                    <span className="text-muted">{a.org}</span>
                  </button>
                </li>
              ))}
            </ul>
          </details>
        </form>
      </div>
    </div>
  );
}
