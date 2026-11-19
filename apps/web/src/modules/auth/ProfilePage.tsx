import { KeyRound, ShieldCheck } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { Badge, Button, PageHeader, Panel } from "../../components/ui";
import { ApiError } from "../../lib/api";
import { ROLE_LABELS, useAuth } from "../../lib/auth";

const RULES = ["Al menos 10 caracteres", "Combina letras y números", "No uses tu usuario de correo", "Evita claves comunes"];

export function ChangePasswordForm({ forced = false }: { forced?: boolean }) {
  const { user, changePassword } = useAuth();
  const navigate = useNavigate();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [repeat, setRepeat] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState(false);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (next !== repeat) {
      setError("Las contraseñas nuevas no coinciden.");
      return;
    }
    setBusy(true);
    try {
      await changePassword(current, next);
      setOk(true);
      setCurrent(""); setNext(""); setRepeat("");
      if (forced) navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo cambiar la contraseña.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="flex flex-col gap-3" onSubmit={submit}>
      <div><label className="label" htmlFor="pw-current">{forced ? "Contraseña temporal" : "Contraseña actual"}</label>
        <input id="pw-current" type="password" className="field" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} required /></div>
      <div><label className="label" htmlFor="pw-new">Nueva contraseña</label>
        <input id="pw-new" type="password" className="field" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} required /></div>
      <div><label className="label" htmlFor="pw-repeat">Repite la nueva contraseña</label>
        <input id="pw-repeat" type="password" className="field" autoComplete="new-password" value={repeat} onChange={(e) => setRepeat(e.target.value)} required /></div>
      <ul className="grid gap-1 text-[11px] text-muted sm:grid-cols-2">{RULES.map((r) => <li key={r}>· {r}</li>)}</ul>
      {error && <p role="alert" className="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">{error}</p>}
      {ok && !forced && <p className="text-sm text-teal">Contraseña actualizada. Se cerraron tus sesiones en otros dispositivos.</p>}
      <Button type="submit" icon={KeyRound} loading={busy} disabled={!current || !next || !repeat} className="self-end">Cambiar contraseña</Button>
      <p className="text-[11px] text-muted">{user?.email} · el cambio queda registrado en la bitácora.</p>
    </form>
  );
}

export function ProfilePage() {
  const { user } = useAuth();
  if (!user) return null;
  return (
    <div className="mx-auto grid max-w-4xl gap-4 md:grid-cols-[1fr_1.2fr]">
      <div className="md:col-span-2"><PageHeader title="Mi perfil" description="Tus datos y la seguridad de tu cuenta." /></div>
      <Panel title={user.full_name} subtitle={user.email}>
        <p className="text-sm">{user.organization.name}</p>
        <div className="mt-2 flex flex-wrap gap-1">{user.roles.map((r) => <Badge key={r} tone="cyan">{ROLE_LABELS[r] ?? r}</Badge>)}</div>
      </Panel>
      <Panel title="Cambiar contraseña" actions={<ShieldCheck className="size-4 text-cyan" />}><ChangePasswordForm /></Panel>
    </div>
  );
}

/** Pantalla obligatoria tras un restablecimiento: el servidor bloquea todo lo demás hasta cambiarla. */
export function ForcedPasswordPage() {
  const { user, signOut } = useAuth();
  return (
    <div className="flex min-h-full items-center justify-center px-4 py-10">
      <div className="panel panel-glow w-full max-w-md p-6">
        <h1 className="text-lg font-semibold">Elige tu nueva contraseña</h1>
        <p className="mb-4 text-sm text-muted">Hola, {user?.full_name.split(" ")[0]}. Iniciaste sesión con una contraseña temporal: por seguridad debes cambiarla antes de continuar.</p>
        <ChangePasswordForm forced />
        <button onClick={signOut} className="mt-3 text-xs text-muted hover:text-text">Cerrar sesión</button>
      </div>
    </div>
  );
}
