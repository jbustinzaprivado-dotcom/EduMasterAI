import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, CheckCircle2, ExternalLink, Pencil, PlayCircle, Plus, Trash2 } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router";
import { RichText } from "../../components/ui/RichText";
import { Badge, Button, ErrorState, PageHeader, Panel, Skeleton } from "../../components/ui";
import { ApiError, api } from "../../lib/api";
import { formatDateTime } from "../../lib/format";
import { KIND_LABEL, sendEvent, type Offering } from "./api";

interface Lesson {
  id: string; offering_id: string; unit_position: number; unit_title: string; position: number; title: string;
  kind: "lectura" | "video" | "practica"; estimated_minutes: number; required: boolean; content: string;
  resources: { title: string; url: string }[]; video_url: string | null; content_version: number;
  content_updated_at: string | null; content_updated_by: string | null; can_edit: boolean;
  previous_id: string | null; next_id: string | null;
}

const err = (e: unknown) => (e instanceof ApiError ? `${e.message}` : "No se pudo guardar.");

function Editor({ lesson, onDone }: { lesson: Lesson; onDone: () => void }) {
  const qc = useQueryClient();
  const [content, setContent] = useState(lesson.content);
  const [video, setVideo] = useState(lesson.video_url ?? "");
  const [resources, setResources] = useState(lesson.resources);
  const save = useMutation({
    mutationFn: () => api<Lesson>(`/offerings/${lesson.offering_id}/activities/${lesson.id}`, {
      method: "PATCH", body: JSON.stringify({ content, video_url: video || null, resources: resources.filter((r) => r.title && r.url) }),
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["lesson", lesson.id] }); onDone(); },
  });
  return (
    <form className="flex flex-col gap-3" onSubmit={(e: FormEvent) => { e.preventDefault(); save.mutate(); }}>
      <div>
        <label className="label" htmlFor="l-content">Contenido (## título, - lista, **negrita**, `código`)</label>
        <textarea id="l-content" className="field min-h-64 font-mono text-xs" value={content} onChange={(e) => setContent(e.target.value)} />
      </div>
      <div>
        <label className="label" htmlFor="l-video">Video (enlace https, opcional)</label>
        <input id="l-video" className="field" value={video} onChange={(e) => setVideo(e.target.value)} placeholder="https://…" />
      </div>
      <fieldset className="flex flex-col gap-2">
        <legend className="label">Recursos (solo enlaces http/https)</legend>
        {resources.map((r, i) => (
          <div key={i} className="flex gap-2">
            <input className="field" aria-label={`Título del recurso ${i + 1}`} value={r.title} placeholder="Título"
              onChange={(e) => setResources((x) => x.map((y, j) => (j === i ? { ...y, title: e.target.value } : y)))} />
            <input className="field" aria-label={`Enlace del recurso ${i + 1}`} value={r.url} placeholder="https://…"
              onChange={(e) => setResources((x) => x.map((y, j) => (j === i ? { ...y, url: e.target.value } : y)))} />
            <Button type="button" variant="ghost" icon={Trash2} aria-label="Quitar recurso" onClick={() => setResources((x) => x.filter((_, j) => j !== i))} />
          </div>
        ))}
        <Button type="button" variant="ghost" icon={Plus} className="self-start" onClick={() => setResources((x) => [...x, { title: "", url: "" }])}>Agregar recurso</Button>
      </fieldset>
      {save.isError && <p role="alert" className="text-sm text-danger">{err(save.error)}</p>}
      <div className="flex justify-end gap-2">
        <Button type="button" variant="ghost" onClick={onDone}>Cancelar</Button>
        <Button type="submit" loading={save.isPending}>Guardar (nueva versión)</Button>
      </div>
    </form>
  );
}

export function LessonPage() {
  const { offeringId = "", activityId = "" } = useParams();
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);
  const opened = useRef(Date.now());
  const lesson = useQuery({ queryKey: ["lesson", activityId], queryFn: () => api<Lesson>(`/offerings/${offeringId}/activities/${activityId}`) });
  const offering = useQuery({ queryKey: ["offering", offeringId], queryFn: () => api<Offering>(`/offerings/${offeringId}`) });
  const enrollment = offering.data?.my_enrollment;
  const done = enrollment?.completed_activity_ids.includes(activityId) ?? false;

  // Registrar que el estudiante abrió la lección (evento idempotente lesson_viewed, §7.4).
  useEffect(() => {
    opened.current = Date.now();
    if (enrollment && enrollment.status === "active") sendEvent(offeringId, "lesson_viewed", activityId).catch(() => {});
  }, [activityId, offeringId, enrollment?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const complete = useMutation({
    mutationFn: () => sendEvent(offeringId, "activity_completed", activityId, Math.round((Date.now() - opened.current) / 1000)),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["offering", offeringId] });
      qc.invalidateQueries({ queryKey: ["offerings"] });
      qc.invalidateQueries({ queryKey: ["recommendations"] });
    },
  });

  if (lesson.isPending) return <Skeleton className="mx-auto h-96 max-w-4xl" />;
  if (lesson.isError) return <div className="mx-auto max-w-xl"><ErrorState error={lesson.error} /></div>;
  const l = lesson.data;

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-4">
      <Link to={`/cursos/${offeringId}`} className="inline-flex items-center gap-1 text-xs text-muted hover:text-cyan"><ArrowLeft className="size-3.5" /> Volver al curso</Link>
      <PageHeader title={l.title}
        description={`Unidad ${l.unit_position} · ${l.unit_title} · ${KIND_LABEL[l.kind]} · ${l.estimated_minutes} min${l.required ? "" : " · opcional"}`}
        actions={l.can_edit && !editing && <Button variant="ghost" icon={Pencil} onClick={() => setEditing(true)}>Editar contenido</Button>} />
      <Panel>
        {editing ? <Editor lesson={l} onDone={() => setEditing(false)} /> : (
          <>
            {l.video_url && (
              <a href={l.video_url} target="_blank" rel="noopener noreferrer" className="mb-3 inline-flex items-center gap-2 rounded-xl border border-violet/40 bg-violet/10 px-3 py-2 text-sm text-[#b593ff] hover:border-violet">
                <PlayCircle className="size-4" /> Ver video de la lección <ExternalLink className="size-3" />
              </a>
            )}
            {l.content ? <RichText text={l.content} /> : <p className="text-sm text-muted">Esta lección aún no tiene contenido.</p>}
            {l.resources.length > 0 && (
              <div className="mt-5">
                <p className="mb-1 text-xs font-semibold tracking-wide text-muted uppercase">Recursos</p>
                <ul className="space-y-1">
                  {l.resources.map((r) => (
                    <li key={r.url}><a href={r.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-sm text-cyan hover:underline">{r.title} <ExternalLink className="size-3" /></a></li>
                  ))}
                </ul>
              </div>
            )}
            <p className="mt-5 text-[11px] text-muted">Versión {l.content_version}{l.content_updated_by ? ` · editada por ${l.content_updated_by} el ${formatDateTime(l.content_updated_at)}` : ""}</p>
          </>
        )}
      </Panel>
      {!editing && (
        <div className="flex flex-wrap items-center gap-2">
          {l.previous_id && <Link to={`/cursos/${offeringId}/actividad/${l.previous_id}`} className="inline-flex items-center gap-1 text-sm text-muted hover:text-cyan"><ArrowLeft className="size-4" /> Anterior</Link>}
          <div className="ml-auto flex items-center gap-2">
            {enrollment && (done
              ? <Badge tone="teal"><CheckCircle2 className="size-3" /> Completada</Badge>
              : enrollment.status !== "dropped" && <Button icon={CheckCircle2} loading={complete.isPending} onClick={() => complete.mutate()}>Marcar como completada</Button>)}
            {l.next_id && <Link to={`/cursos/${offeringId}/actividad/${l.next_id}`} className="inline-flex items-center gap-1 rounded-[10px] border border-line px-3 py-2 text-sm hover:border-cyan">Siguiente <ArrowRight className="size-4" /></Link>}
          </div>
          {complete.isError && <p role="alert" className="w-full text-sm text-danger">{err(complete.error)}</p>}
        </div>
      )}
    </div>
  );
}
