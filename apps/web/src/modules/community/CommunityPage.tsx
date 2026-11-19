import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, BellOff, BellRing, EyeOff, Flag, Megaphone, MessagesSquare, Send, ShieldCheck } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useSearchParams } from "react-router";
import { Badge, Button, EmptyState, ErrorState, PageHeader, Panel, Skeleton, cx } from "../../components/ui";
import { ApiError, api } from "../../lib/api";
import { relativeTime } from "../../lib/format";
import type { Offering } from "../courses/api";

interface Post {
  id: string;
  offering_id: string;
  kind: "anuncio" | "debate";
  title: string;
  body: string;
  author_name: string;
  author_is_teacher: boolean;
  created_at: string;
  comments: number;
  hidden: boolean;
  hidden_reason: string | null;
  mine: boolean;
}
interface Comment {
  id: string;
  body: string;
  author_name: string;
  author_is_teacher: boolean;
  created_at: string;
  hidden: boolean;
  hidden_reason: string | null;
  mine: boolean;
}
interface Space {
  offering_id: string;
  course_title: string;
  can_post: boolean;
  can_announce: boolean;
  can_moderate: boolean;
  muted: boolean;
  open_reports: number;
  rules: string[];
  posts: Post[];
}
interface Thread { post: Post; comments: Comment[]; can_comment: boolean; can_moderate: boolean }
interface ReportRow { id: string; target_type: "post" | "comment"; target_id: string; post_id: string; excerpt: string; reason: string; reports: number }

const err = (e: unknown) => (e instanceof ApiError ? e.message : "No se pudo completar la acción.");

function useModerate(onDone: () => void) {
  return useMutation({
    mutationFn: ({ type, id, action, reason }: { type: string; id: string; action: string; reason?: string }) =>
      api(`/community/${type}/${id}/moderate`, { method: "POST", body: JSON.stringify({ action, reason }) }),
    onSuccess: onDone,
  });
}

function Author({ name, teacher }: { name: string; teacher: boolean }) {
  return <span className="inline-flex items-center gap-1.5 font-medium">{name}{teacher && <Badge tone="violet">docente</Badge>}</span>;
}

function ThreadView({ postId, onBack }: { postId: string; onBack: () => void }) {
  const qc = useQueryClient();
  const [text, setText] = useState("");
  const thread = useQuery({ queryKey: ["community", "thread", postId], queryFn: () => api<Thread>(`/community/posts/${postId}`) });
  const refresh = () => qc.invalidateQueries({ queryKey: ["community"] });
  const comment = useMutation({
    mutationFn: () => api<Thread>(`/community/posts/${postId}/comments`, { method: "POST", body: JSON.stringify({ body: text }) }),
    onSuccess: () => { setText(""); refresh(); },
  });
  const report = useMutation({
    mutationFn: (b: { target_type: string; target_id: string; reason: string }) => api("/community/reports", { method: "POST", body: JSON.stringify(b) }),
  });
  const moderate = useModerate(refresh);
  const askReport = (type: string, id: string) => {
    const reason = window.prompt("¿Qué regla incumple? (mínimo 5 caracteres)");
    if (reason && reason.trim().length >= 5) report.mutate({ target_type: type, target_id: id, reason: reason.trim() });
  };
  const askHide = (type: string, id: string) => {
    const reason = window.prompt("Motivo para ocultar (queda en la bitácora):");
    if (reason?.trim()) moderate.mutate({ type, id, action: "ocultar", reason: reason.trim() });
  };

  if (thread.isPending) return <Skeleton className="h-64" />;
  if (thread.isError) return <ErrorState error={thread.error} onRetry={() => thread.refetch()} />;
  const { post, comments } = thread.data;
  return (
    <div className="flex flex-col gap-3">
      <button onClick={onBack} className="inline-flex items-center gap-1 self-start text-xs text-muted hover:text-cyan"><ArrowLeft className="size-3.5" /> Volver al espacio</button>
      <Panel glow>
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
          <Badge tone={post.kind === "anuncio" ? "warning" : "cyan"}>{post.kind}</Badge>
          <Author name={post.author_name} teacher={post.author_is_teacher} /> · {relativeTime(post.created_at)}
          {post.hidden && <Badge tone="danger">oculto: {post.hidden_reason}</Badge>}
        </div>
        <h2 className="mt-2 text-lg font-semibold">{post.title}</h2>
        <p className="mt-1 text-sm whitespace-pre-line text-text/90">{post.body}</p>
        <div className="mt-3 flex gap-2">
          {!post.mine && <Button variant="ghost" icon={Flag} className="px-2 py-1 text-xs" onClick={() => askReport("post", post.id)}>Reportar</Button>}
          {thread.data.can_moderate && (post.hidden
            ? <Button variant="ghost" className="px-2 py-1 text-xs" onClick={() => moderate.mutate({ type: "post", id: post.id, action: "mostrar" })}>Restaurar</Button>
            : <Button variant="danger" icon={EyeOff} className="px-2 py-1 text-xs" onClick={() => askHide("post", post.id)}>Ocultar</Button>)}
        </div>
      </Panel>
      <Panel title={`${comments.length} respuestas`}>
        <ul className="divide-y divide-line">
          {comments.map((c) => (
            <li key={c.id} className={cx("py-2.5 text-sm", c.hidden && "opacity-60")}>
              <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
                <Author name={c.author_name} teacher={c.author_is_teacher} /> · {relativeTime(c.created_at)}
                {c.hidden && <Badge tone="danger">oculto: {c.hidden_reason}</Badge>}
                <span className="ml-auto flex gap-1">
                  {!c.mine && <button className="hover:text-warning" aria-label="Reportar comentario" onClick={() => askReport("comment", c.id)}><Flag className="size-3.5" /></button>}
                  {thread.data.can_moderate && !c.hidden && <button className="hover:text-danger" aria-label="Ocultar comentario" onClick={() => askHide("comment", c.id)}><EyeOff className="size-3.5" /></button>}
                </span>
              </div>
              <p className="mt-1 whitespace-pre-line">{c.body}</p>
            </li>
          ))}
        </ul>
        {thread.data.can_comment && (
          <form className="mt-3 flex gap-2" onSubmit={(e: FormEvent) => { e.preventDefault(); comment.mutate(); }}>
            <label className="sr-only" htmlFor="reply">Tu respuesta</label>
            <textarea id="reply" className="field min-h-12" placeholder="Escribe una respuesta respetuosa…" value={text} onChange={(e) => setText(e.target.value)} />
            <Button type="submit" icon={Send} loading={comment.isPending} disabled={!text.trim()} aria-label="Enviar" />
          </form>
        )}
        {[comment, report, moderate].map((m, i) => m.isError && <p key={i} role="alert" className="mt-2 text-sm text-danger">{err(m.error)}</p>)}
        {report.isSuccess && <p className="mt-2 text-sm text-teal">Reporte enviado al docente.</p>}
      </Panel>
    </div>
  );
}

function NewPost({ space }: { space: Space }) {
  const qc = useQueryClient();
  const [kind, setKind] = useState<"debate" | "anuncio">("debate");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const create = useMutation({
    mutationFn: () => api<Post>(`/offerings/${space.offering_id}/community/posts`, { method: "POST", body: JSON.stringify({ kind, title, body }) }),
    onSuccess: () => { setTitle(""); setBody(""); qc.invalidateQueries({ queryKey: ["community"] }); },
  });
  return (
    <form className="flex flex-col gap-2" onSubmit={(e: FormEvent) => { e.preventDefault(); create.mutate(); }}>
      {space.can_announce && (
        <div className="flex gap-2 text-xs">
          {(["debate", "anuncio"] as const).map((k) => (
            <button type="button" key={k} onClick={() => setKind(k)}
              className={cx("rounded-full border px-3 py-1", kind === k ? "border-cyan text-cyan" : "border-line text-muted")}>
              {k === "anuncio" ? "Anuncio (notifica a todos)" : "Debate"}
            </button>
          ))}
        </div>
      )}
      <label className="sr-only" htmlFor="p-title">Título</label>
      <input id="p-title" className="field" placeholder="Título" value={title} onChange={(e) => setTitle(e.target.value)} minLength={3} required />
      <label className="sr-only" htmlFor="p-body">Mensaje</label>
      <textarea id="p-body" className="field min-h-20" placeholder="¿Qué quieres compartir o preguntar?" value={body} onChange={(e) => setBody(e.target.value)} required />
      {create.isError && <p role="alert" className="text-sm text-danger">{err(create.error)}</p>}
      <Button type="submit" icon={kind === "anuncio" ? Megaphone : Send} loading={create.isPending} disabled={title.length < 3 || !body.trim()} className="self-end">Publicar</Button>
    </form>
  );
}

function Reports({ space }: { space: Space }) {
  const qc = useQueryClient();
  const reports = useQuery({ queryKey: ["community", "reports", space.offering_id], queryFn: () => api<ReportRow[]>(`/offerings/${space.offering_id}/community/reports`) });
  const moderate = useModerate(() => qc.invalidateQueries({ queryKey: ["community"] }));
  if (!reports.data?.length) return <p className="text-xs text-muted">No hay reportes abiertos.</p>;
  return (
    <ul className="space-y-2">
      {reports.data.map((r) => (
        <li key={r.id} className="rounded-lg border border-warning/30 p-2 text-xs">
          <p className="font-medium">«{r.excerpt}»</p>
          <p className="text-muted">Motivo: {r.reason} · {r.reports} reporte(s)</p>
          <div className="mt-1.5 flex gap-2">
            <Button variant="danger" className="px-2 py-1 text-xs" onClick={() => {
              const reason = window.prompt("Motivo para ocultar:", r.reason);
              if (reason?.trim()) moderate.mutate({ type: r.target_type, id: r.target_id, action: "ocultar", reason: reason.trim() });
            }}>Ocultar</Button>
            <Button variant="ghost" className="px-2 py-1 text-xs" onClick={() => moderate.mutate({ type: r.target_type, id: r.target_id, action: "desestimar" })}>Desestimar</Button>
          </div>
        </li>
      ))}
    </ul>
  );
}

export function CommunityPage() {
  const qc = useQueryClient();
  const [params, setParams] = useSearchParams();
  const offerings = useQuery({ queryKey: ["offerings"], queryFn: () => api<Offering[]>("/offerings") });
  const offeringId = params.get("oferta") ?? offerings.data?.[0]?.id ?? "";
  const postId = params.get("post");
  const space = useQuery({
    queryKey: ["community", "space", offeringId], enabled: !!offeringId,
    queryFn: () => api<Space>(`/offerings/${offeringId}/community`),
  });
  const mute = useMutation({
    mutationFn: (muted: boolean) => api(`/offerings/${offeringId}/community/mute`, { method: "PUT", body: JSON.stringify({ muted }) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["community", "space", offeringId] }),
  });
  const go = (next: Record<string, string | null>) => {
    const p = new URLSearchParams(params);
    for (const [k, v] of Object.entries(next)) (v ? p.set(k, v) : p.delete(k));
    setParams(p);
  };

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader title="Comunidad" description="Espacio por curso: anuncios del docente, debates y respuestas, con moderación (§4.8)."
        actions={offerings.data && offerings.data.length > 0 && (
          <select className="field w-72" aria-label="Curso" value={offeringId} onChange={(e) => go({ oferta: e.target.value, post: null })}>
            {offerings.data.map((o) => <option key={o.id} value={o.id}>{o.course_title} · {o.cohort}</option>)}
          </select>
        )} />
      {offerings.data?.length === 0 && <EmptyState icon={MessagesSquare} title="Sin cursos" description="No participas en ningún curso todavía." />}
      {space.isPending && offeringId && <Skeleton className="h-64" />}
      {space.isError && <ErrorState error={space.error} onRetry={() => space.refetch()} />}
      {space.data && (
        <div className="grid gap-4 lg:grid-cols-[1fr_300px]">
          <div className="flex flex-col gap-3">
            {postId ? <ThreadView postId={postId} onBack={() => go({ post: null })} /> : (
              <>
                {space.data.can_post && <Panel title="Nueva publicación"><NewPost space={space.data} /></Panel>}
                {space.data.posts.length === 0 && <EmptyState icon={MessagesSquare} title="Aún no hay publicaciones" description="Inicia el primer debate del curso." />}
                {space.data.posts.map((p) => (
                  <button key={p.id} onClick={() => go({ post: p.id })}
                    className={cx("panel flex flex-col gap-1 p-4 text-left transition-colors hover:border-cyan/50", p.kind === "anuncio" && "panel-glow", p.hidden && "opacity-60")}>
                    <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
                      {p.kind === "anuncio" ? <Badge tone="warning"><Megaphone className="size-3" /> anuncio</Badge> : <Badge tone="cyan">debate</Badge>}
                      <Author name={p.author_name} teacher={p.author_is_teacher} /> · {relativeTime(p.created_at)}
                      {p.hidden && <Badge tone="danger">oculto</Badge>}
                    </div>
                    <p className="font-semibold">{p.title}</p>
                    {p.body && <p className="line-clamp-2 text-sm text-muted">{p.body}</p>}
                    <p className="text-xs text-muted">{p.comments} respuesta(s)</p>
                  </button>
                ))}
              </>
            )}
          </div>
          <div className="flex flex-col gap-4">
            <Panel title={space.data.course_title}>
              <Button variant="ghost" icon={space.data.muted ? BellRing : BellOff} loading={mute.isPending} onClick={() => mute.mutate(!space.data.muted)}>
                {space.data.muted ? "Activar notificaciones" : "Silenciar este curso"}
              </Button>
              <p className="mt-2 text-xs text-muted">{space.data.muted ? "No recibes avisos de anuncios ni respuestas de este curso." : "Recibes avisos de anuncios y respuestas a tus publicaciones."}</p>
            </Panel>
            {space.data.can_moderate && (
              <Panel title="Moderación" subtitle={`${space.data.open_reports} reporte(s) abierto(s)`} actions={<ShieldCheck className="size-4 text-cyan" />}>
                <Reports space={space.data} />
              </Panel>
            )}
            <Panel title="Reglas de convivencia">
              <ol className="list-inside list-decimal space-y-1 text-xs text-muted">{space.data.rules.map((r) => <li key={r}>{r}</li>)}</ol>
            </Panel>
          </div>
        </div>
      )}
    </div>
  );
}
