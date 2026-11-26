"""Endpoints de recomendaciones e IA Tutor (§4.5, §4.11, §10.2)."""

import uuid
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.api.deps import DB, CurrentPrincipal, Principal, require
from app.core.errors import AppError, forbidden, not_found
from app.modules.academic.models import Assessment, AssessmentAttempt, CourseOffering, Enrollment
from app.modules.academic.service import can_manage_offering, can_view_roster, get_offering, offerings_query
from app.modules.identity.models import User
from app.modules.ml.service import latest_predictions
from app.modules.notifications.models import Notification
from app.modules.recommendations import engine
from app.modules.recommendations.models import Recommendation
from app.modules.skills import service as skills
from app.modules.skills.models import LEVELS, CourseSkill, Skill

router = APIRouter(tags=["recomendaciones"])

ORDER = {"nueva": 0, "aceptada": 1, "completada": 2, "descartada": 3, "expirada": 4}


class RecommendationOut(BaseModel):
    id: uuid.UUID
    offering_id: uuid.UUID
    course_title: str
    student_name: str | None = None
    kind: str
    target_type: str
    target_id: uuid.UUID
    title: str
    reason: str
    expected_impact: str
    priority: float
    priority_reason: str
    source: str
    status: str
    useful: bool | None
    feedback_reason: str | None
    created_at: datetime
    resolved_at: datetime | None
    resolution_note: str | None


def _out(r: Recommendation, course_titles: dict, names: dict | None = None) -> RecommendationOut:
    return RecommendationOut(
        id=r.id, offering_id=r.offering_id, course_title=course_titles.get(r.offering_id, ""),
        student_name=names.get(r.student_id) if names else None, kind=r.kind, target_type=r.target_type,
        target_id=r.target_id, title=r.title, reason=r.reason, expected_impact=r.expected_impact, priority=r.priority,
        priority_reason=r.priority_reason or "", source=r.source, status=r.status, useful=r.useful,
        feedback_reason=r.feedback_reason, created_at=r.created_at, resolved_at=r.resolved_at,
        resolution_note=r.resolution_note,
    )


def _course_titles(db: DB, offering_ids) -> dict:
    rows = db.scalars(select(CourseOffering).where(CourseOffering.id.in_(list(offering_ids)))) if offering_ids else []
    return {o.id: o.course.title for o in rows}


def _sorted(rows: list[Recommendation]) -> list[Recommendation]:
    return sorted(rows, key=lambda r: (ORDER[r.status], -r.priority))


@router.get("/recommendations", response_model=list[RecommendationOut])
def my_recommendations(db: DB, principal: Principal = require("learning"), offering_id: uuid.UUID | None = None,
                       history: bool = False) -> list[RecommendationOut]:
    """Recomendaciones vigentes del estudiante. Se recalculan al consultarlas (IA Tutor: "¿qué hago ahora?")."""
    q = select(Enrollment).where(Enrollment.student_id == principal.user.id)
    if offering_id:
        q = q.where(Enrollment.offering_id == offering_id)
    enrollments = list(db.scalars(q))
    if offering_id and not enrollments:
        raise not_found("Matrícula")
    for e in enrollments:
        engine.refresh(db, e)
    db.commit()
    rq = select(Recommendation).where(Recommendation.student_id == principal.user.id)
    if offering_id:
        rq = rq.where(Recommendation.offering_id == offering_id)
    if not history:
        rq = rq.where(Recommendation.status.in_(engine.OPEN))
    rows = _sorted(list(db.scalars(rq)))
    titles = _course_titles(db, {r.offering_id for r in rows})
    return [_out(r, titles) for r in rows]


class FeedbackIn(BaseModel):
    action: Literal["aceptar", "descartar", "util", "no_util"]
    reason: str | None = Field(default=None, max_length=500)


@router.post("/recommendations/{rec_id}/feedback", response_model=RecommendationOut)
def feedback(rec_id: uuid.UUID, body: FeedbackIn, db: DB, principal: Principal = require("learning")) -> RecommendationOut:
    """Aceptar, descartar o valorar (§4.5). La retroalimentación sirve para medir utilidad, no solo clics (§4.11)."""
    r = db.get(Recommendation, rec_id)
    if r is None or r.student_id != principal.user.id:
        raise not_found("Recomendación")
    if body.action in ("aceptar", "descartar") and r.status not in engine.OPEN:
        raise AppError(422, "validation_error", "La recomendación ya no está vigente.")
    now = datetime.now(UTC)
    if body.action == "aceptar":
        r.status = "aceptada"
        if r.kind == "anuncio":  # abrir el anuncio desde la sugerencia cuenta como leerlo
            for n in db.scalars(select(Notification).where(
                    Notification.user_id == principal.user.id, Notification.read_at.is_(None),
                    Notification.link.contains(f"post={r.target_id}"))):
                n.read_at = now
    elif body.action == "descartar":
        r.status, r.resolved_at, r.feedback_reason = "descartada", now, body.reason
    else:
        r.useful = body.action == "util"
        if body.reason:
            r.feedback_reason = body.reason
    db.commit()
    return _out(r, _course_titles(db, {r.offering_id}))


@router.get("/offerings/{offering_id}/recommendations", response_model=list[RecommendationOut])
def offering_recommendations(offering_id: uuid.UUID, db: DB, principal: CurrentPrincipal) -> list[RecommendationOut]:
    """Vista del docente sobre las sugerencias de su grupo (§4.5: revisa, no reemplaza su criterio)."""
    offering = get_offering(db, principal, offering_id)
    if not can_view_roster(principal, offering):
        raise forbidden()
    for e in db.scalars(select(Enrollment).where(Enrollment.offering_id == offering.id)):
        engine.refresh(db, e)
    db.commit()
    rows = _sorted(list(db.scalars(select(Recommendation).where(Recommendation.offering_id == offering.id))))
    names = {u.id: u.full_name for u in db.scalars(select(User).where(User.id.in_({r.student_id for r in rows})))} if rows else {}
    return [_out(r, {offering.id: offering.course.title}, names) for r in rows]


class KindMetrics(BaseModel):
    kind: str
    total: int
    nueva: int
    aceptada: int
    completada: int
    descartada: int
    expirada: int
    acceptance_rate: float | None  # (aceptadas + completadas) / decididas
    useful_rate: float | None  # útiles / valoradas


@router.get("/recommendations/metrics", response_model=list[KindMetrics])
def metrics(db: DB, principal: CurrentPrincipal) -> list[KindMetrics]:
    """Aceptación y utilidad por tipo (§4.11), solo agregados de la institución."""
    if not (principal.can("ml.read") or principal.can("course.read.all")):
        raise forbidden()
    q = select(Recommendation.kind, Recommendation.status, Recommendation.useful, func.count()).group_by(
        Recommendation.kind, Recommendation.status, Recommendation.useful)
    if not principal.is_global:
        q = q.where(Recommendation.organization_id == principal.organization_id)
    data: dict[str, dict] = {}
    for kind, status, useful, n in db.execute(q):
        d = data.setdefault(kind, {s: 0 for s in ORDER} | {"util": 0, "valoradas": 0})
        d[status] += n
        if useful is not None:
            d["valoradas"] += n
            d["util"] += n if useful else 0
    out = []
    for kind, d in sorted(data.items()):
        decided = d["aceptada"] + d["completada"] + d["descartada"]
        out.append(KindMetrics(
            kind=kind, total=sum(d[s] for s in ORDER), **{s: d[s] for s in ORDER},
            acceptance_rate=round((d["aceptada"] + d["completada"]) / decided, 3) if decided else None,
            useful_rate=round(d["util"] / d["valoradas"], 3) if d["valoradas"] else None,
        ))
    return out


# ---------- docente: acciones sugeridas (D55) ----------

class TeacherAction(BaseModel):
    kind: Literal["por_calificar", "alertas", "sin_entregar", "inactivos", "competencia_grupo"]
    offering_id: uuid.UUID
    course: str
    title: str
    reason: str
    count: int
    link: str
    priority: float


@router.get("/recommendations/teacher-actions", response_model=list[TeacherAction])
def teacher_actions(db: DB, principal: Principal = require("assessment.manage")) -> list[TeacherAction]:
    """Qué conviene hacer hoy con los grupos a cargo: se calcula en el momento con datos reales; no se guarda.
    Docente: sus ofertas; coordinación y administración: las de su institución (§3, §4.5)."""
    now = datetime.now(UTC)
    offerings = [o for o in db.scalars(offerings_query(principal).where(CourseOffering.status == "active"))
                 if can_manage_offering(principal, o)]
    out: list[TeacherAction] = []
    for o in offerings:
        course = f"{o.course.code} · {o.cohort}"
        enrollments = list(db.scalars(select(Enrollment).where(Enrollment.offering_id == o.id, Enrollment.status == "active")))
        active_ids = {e.student_id for e in enrollments}
        assessments = list(db.scalars(select(Assessment).where(Assessment.offering_id == o.id)))
        attempts = list(db.scalars(select(AssessmentAttempt).where(
            AssessmentAttempt.assessment_id.in_([a.id for a in assessments])))) if assessments else []

        ungraded = [x for x in attempts if x.score is None]
        if ungraded:
            out.append(TeacherAction(
                kind="por_calificar", offering_id=o.id, course=course, count=len(ungraded),
                title=f"{len(ungraded)} entrega{'s' if len(ungraded) > 1 else ''} por calificar",
                reason="El estudiante recibe su nota en vivo al calificar; la nota oficial la pones tú (§4.6).",
                link="/evaluaciones", priority=0.9))

        pending_alerts = [p for p in latest_predictions(db, o.id).values()
                          if p.risk_level == "alto" and p.review_status == "pendiente" and p.student_id in active_ids]
        if pending_alerts:
            out.append(TeacherAction(
                kind="alertas", offering_id=o.id, course=course, count=len(pending_alerts),
                title=f"{len(pending_alerts)} alerta{'s' if len(pending_alerts) > 1 else ''} de riesgo sin atender",
                reason="Contacta al estudiante y marca la alerta como atendida, o descártala con un motivo (§9.8).",
                link=f"/cursos/{o.id}?seccion=estudiantes", priority=0.95))

        submitted = defaultdict(set)
        for x in attempts:
            submitted[x.assessment_id].add(x.student_id)
        for a in assessments:
            due = a.due_at if a.due_at.tzinfo else a.due_at.replace(tzinfo=UTC)
            missing = active_ids - submitted[a.id]
            if now < due <= now + timedelta(days=7) and missing:
                out.append(TeacherAction(
                    kind="sin_entregar", offering_id=o.id, course=course, count=len(missing),
                    title=f"{len(missing)} estudiante{'s' if len(missing) > 1 else ''} aún sin entregar «{a.title}»",
                    reason=f"Vence el {due.strftime('%d/%m')}. Un recordatorio en el curso puede evitar entregas tardías.",
                    link=f"/comunidad?oferta={o.id}", priority=0.8 - (due - now).days / 70))

        idle = [e for e in enrollments if e.last_activity_at is None or
                now - (e.last_activity_at if e.last_activity_at.tzinfo else e.last_activity_at.replace(tzinfo=UTC)) >= timedelta(days=7)]
        if idle:
            out.append(TeacherAction(
                kind="inactivos", offering_id=o.id, course=course, count=len(idle),
                title=f"{len(idle)} estudiante{'s' if len(idle) > 1 else ''} sin actividad hace 7 días o más",
                reason="La inactividad es la señal más fuerte de abandono; un mensaje a tiempo ayuda (§4.5).",
                link=f"/cursos/{o.id}?seccion=estudiantes", priority=0.7))

        links = list(db.scalars(select(CourseSkill).where(CourseSkill.course_id == o.course_id)))
        if links and enrollments:
            low = Counter()
            evaluated = Counter()
            for e in enrollments:
                states = skills.student_states(db, e.student_id, [o.id])
                for cs in links:
                    s = states.get(cs.skill_id)
                    if s and s.estimated_level is not None and any(ev.source == "evaluacion" for ev in s.evidences):
                        evaluated[cs.skill_id] += 1
                        low[cs.skill_id] += s.estimated_level <= 2
            for cs in links:
                n, total = low[cs.skill_id], evaluated[cs.skill_id]
                if total >= 3 and n / total >= 0.4:
                    skill = db.get(Skill, cs.skill_id)
                    out.append(TeacherAction(
                        kind="competencia_grupo", offering_id=o.id, course=course, count=n,
                        title=f"{n} de {total} estudiantes con nivel bajo en «{skill.name}»",
                        reason=f"Nivel estimado {LEVELS[0]} o {LEVELS[1]} según sus notas. Conviene reforzar la Unidad "
                               f"{cs.position} en clase (§4.9).",
                        link="/habilidades?seccion=mapa", priority=0.6))
    return sorted(out, key=lambda a: -a.priority)


# ---------- gestión: evolución y motivos (D55) ----------

class WeekPoint(BaseModel):
    week_start: datetime
    generated: int
    accepted: int
    completed: int
    discarded: int


class CourseRow(BaseModel):
    course: str
    total: int
    acceptance_rate: float | None
    useful_rate: float | None


class ReasonRow(BaseModel):
    reason: str
    count: int


class Insights(BaseModel):
    weekly: list[WeekPoint]
    by_course: list[CourseRow]
    discard_reasons: list[ReasonRow]


@router.get("/recommendations/insights", response_model=Insights)
def insights(db: DB, principal: CurrentPrincipal) -> Insights:
    """Aceptación por semana y por curso, y motivos de descarte más frecuentes: sirven para ajustar las reglas."""
    if not (principal.can("ml.read") or principal.can("course.read.all")):
        raise forbidden()
    q = select(Recommendation)
    if not principal.is_global:
        q = q.where(Recommendation.organization_id == principal.organization_id)
    rows = list(db.scalars(q))
    weeks: dict[datetime, dict] = {}
    courses: dict[uuid.UUID, Counter] = defaultdict(Counter)
    reasons: Counter = Counter()
    for r in rows:
        created = r.created_at if r.created_at.tzinfo else r.created_at.replace(tzinfo=UTC)
        start = (created - timedelta(days=created.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        w = weeks.setdefault(start, Counter())
        w["generated"] += 1
        w[{"aceptada": "accepted", "completada": "completed", "descartada": "discarded"}.get(r.status, "otro")] += 1
        c = courses[r.offering_id]
        c["total"] += 1
        c[r.status] += 1
        if r.useful is not None:
            c["valoradas"] += 1
            c["util"] += int(r.useful)
        if r.status == "descartada":
            reasons[(r.feedback_reason or "Sin motivo").strip().capitalize()] += 1
    titles = {o.id: f"{o.course.code} · {o.cohort}" for o in db.scalars(
        select(CourseOffering).where(CourseOffering.id.in_(list(courses))))} if courses else {}
    by_course = []
    for oid, c in courses.items():
        decided = c["aceptada"] + c["completada"] + c["descartada"]
        by_course.append(CourseRow(
            course=titles.get(oid, "—"), total=c["total"],
            acceptance_rate=round((c["aceptada"] + c["completada"]) / decided, 3) if decided else None,
            useful_rate=round(c["util"] / c["valoradas"], 3) if c["valoradas"] else None))
    return Insights(
        weekly=[WeekPoint(week_start=k, generated=v["generated"], accepted=v["accepted"], completed=v["completed"],
                          discarded=v["discarded"]) for k, v in sorted(weeks.items())][-8:],
        by_course=sorted(by_course, key=lambda r: -r.total),
        discard_reasons=[ReasonRow(reason=k, count=n) for k, n in reasons.most_common(5)],
    )
