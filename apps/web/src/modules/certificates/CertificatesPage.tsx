import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Award, BadgeCheck, Download, ExternalLink, ShieldAlert, ShieldCheck } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { Badge, Button, EmptyState, ErrorState, PageHeader, Skeleton } from "../../components/ui";
import { ApiError, api, apiBlob } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { formatDateTime } from "../../lib/format";

export interface Certificate {
  id: string;
  folio: string;
  verification_code: string;
  status: "emitido" | "anulado";
  student_id: string;
  student_name: string;
  course_title: string;
  course_code: string;
  cohort: string;
  period: string;
  offering_id: string;
  final_grade: number | null;
  issued_at: string;
  issued_by_system: boolean;
  revoked_at: string | null;
  revoke_reason: string | null;
}

export async function downloadPdf(c: Certificate) {
  const blob = await apiBlob(`/certificates/${c.id}/pdf`);
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${c.folio}.pdf`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function CertificateCard({ c, canRevoke }: { c: Certificate; canRevoke: boolean }) {
  const qc = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const revoke = useMutation({
    mutationFn: (reason: string) => api<Certificate>(`/certificates/${c.id}/revoke`, { method: "POST", body: JSON.stringify({ reason }) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["certificates"] }),
    onError: (e) => setError(e instanceof ApiError ? e.message : "Error"),
  });
  return (
    <article className={`panel flex flex-col gap-2 p-4 ${c.status === "emitido" ? "panel-glow" : "opacity-70"}`}>
      <div className="flex items-center justify-between gap-2">
        <Award className="size-6 text-cyan" aria-hidden />
        <Badge tone={c.status === "emitido" ? "teal" : "danger"}>{c.status}</Badge>
      </div>
      <h3 className="font-semibold">{c.course_title}</h3>
      <p className="text-sm">{c.student_name}</p>
      <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
        <dt className="text-muted">Folio</dt><dd className="font-mono">{c.folio}</dd>
        <dt className="text-muted">Código</dt><dd className="font-mono">{c.verification_code}</dd>
        <dt className="text-muted">Emitido</dt><dd>{formatDateTime(c.issued_at)}{c.issued_by_system && " · automático"}</dd>
        {c.final_grade !== null && <><dt className="text-muted">Nota final</dt><dd>{c.final_grade.toFixed(1)} / 20</dd></>}
        {c.revoke_reason && <><dt className="text-muted">Motivo de anulación</dt><dd>{c.revoke_reason}</dd></>}
      </dl>
      <div className="mt-1 flex flex-wrap gap-2">
        <Button variant="ghost" icon={Download} className="px-2.5 py-1.5 text-xs" loading={busy}
          onClick={async () => { setBusy(true); try { await downloadPdf(c); } catch (e) { setError(e instanceof ApiError ? e.message : "Error"); } finally { setBusy(false); } }}>
          PDF
        </Button>
        <Link to={`/verificar/${c.verification_code}`} target="_blank" className="inline-flex items-center gap-1 px-2 py-1.5 text-xs text-cyan hover:underline">
          Verificación pública <ExternalLink className="size-3" />
        </Link>
        {canRevoke && c.status === "emitido" && (
          <Button variant="danger" className="ml-auto px-2.5 py-1.5 text-xs" loading={revoke.isPending} onClick={() => {
            const reason = window.prompt("Motivo de la anulación (queda en la bitácora):");
            if (reason && reason.trim().length >= 5) revoke.mutate(reason.trim());
          }}>Anular</Button>
        )}
      </div>
      {error && <p role="alert" className="text-xs text-danger">{error}</p>}
    </article>
  );
}

export function CertificatesPage() {
  const { can } = useAuth();
  const certs = useQuery({ queryKey: ["certificates"], queryFn: () => api<Certificate[]>("/certificates") });
  const student = can("learning") && !can("course.read.all");
  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader title={student ? "Mis certificados" : "Certificados"}
        description="Se emiten automáticamente al completar el curso con nota final ≥ 11 y al menos 50 % del peso calificado (D29). Cada uno tiene folio único y código de verificación pública." />
      {certs.isPending && <Skeleton className="h-48" />}
      {certs.isError && <ErrorState error={certs.error} onRetry={() => certs.refetch()} />}
      {certs.data?.length === 0 && (
        <EmptyState icon={Award} title="Aún no hay certificados" description={student ? "Completa un curso y aprueba sus evaluaciones para obtener el tuyo." : "No hay certificados en tus cursos."} />
      )}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {certs.data?.map((c) => <CertificateCard key={c.id} c={c} canRevoke={can("course.manage")} />)}
      </div>
    </div>
  );
}

interface Verification {
  valid: boolean;
  status: string;
  folio: string;
  student_name: string;
  course_title: string;
  institution: string;
  issued_at: string;
  revoked_at: string | null;
}

/** Portal público de verificación (§4.7): sin sesión y con datos mínimos. */
export function VerifyPage() {
  const { code = "" } = useParams();
  const navigate = useNavigate();
  const [input, setInput] = useState(code);
  const result = useQuery({
    queryKey: ["verify", code],
    enabled: !!code,
    retry: false,
    queryFn: async () => {
      const r = await fetch(`/api/v1/certificates/verify/${encodeURIComponent(code)}`);
      if (r.status === 404) return null;
      if (!r.ok) throw new Error((await r.json()).message ?? "No se pudo verificar.");
      return (await r.json()) as Verification;
    },
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (input.trim()) navigate(`/verificar/${input.trim().toUpperCase()}`);
  };
  const v = result.data;
  return (
    <div className="flex min-h-full items-center justify-center px-4 py-10">
      <div className="w-full max-w-lg">
        <div className="mb-6 flex items-center gap-2.5">
          <img src="/favicon.svg" alt="" className="size-9" />
          <div>
            <p className="font-bold">EduMaster<span className="text-cyan">.ai</span></p>
            <p className="text-xs text-muted">Verificación pública de certificados</p>
          </div>
        </div>
        <form onSubmit={submit} className="panel mb-4 flex gap-2 p-4">
          <label className="sr-only" htmlFor="code">Código de verificación</label>
          <input id="code" className="field font-mono uppercase" placeholder="Código de 10 caracteres" value={input}
            onChange={(e) => setInput(e.target.value)} />
          <Button type="submit">Verificar</Button>
        </form>
        {result.isFetching && <Skeleton className="h-40" />}
        {result.isError && <ErrorState error={result.error} />}
        {code && result.isSuccess && !v && (
          <div className="panel flex items-center gap-3 p-5 text-sm"><ShieldAlert className="size-6 text-danger" /> No existe un certificado con ese código.</div>
        )}
        {v && (
          <div className={`panel p-5 ${v.valid ? "panel-glow" : ""}`}>
            <div className="mb-3 flex items-center gap-2">
              {v.valid ? <ShieldCheck className="size-7 text-teal" /> : <ShieldAlert className="size-7 text-danger" />}
              <p className="text-lg font-semibold">{v.valid ? "Certificado válido" : "Certificado ANULADO"}</p>
            </div>
            <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
              <dt className="text-muted">Estudiante</dt><dd>{v.student_name}</dd>
              <dt className="text-muted">Curso</dt><dd>{v.course_title}</dd>
              <dt className="text-muted">Institución</dt><dd>{v.institution}</dd>
              <dt className="text-muted">Folio</dt><dd className="font-mono">{v.folio}</dd>
              <dt className="text-muted">Emitido</dt><dd>{formatDateTime(v.issued_at)}</dd>
              {v.revoked_at && <><dt className="text-muted">Anulado</dt><dd>{formatDateTime(v.revoked_at)}</dd></>}
            </dl>
            <p className="mt-3 flex items-center gap-1 text-[11px] text-muted"><BadgeCheck className="size-3.5" /> Solo se muestran datos mínimos (§4.7). Proyecto académico DEMO.</p>
          </div>
        )}
      </div>
    </div>
  );
}
