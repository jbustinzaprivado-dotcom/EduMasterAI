"""Endpoints de recomendaciones e IA Tutor (§4.5, §4.11, §10.2)."""

import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.api.deps import DB, CurrentPrincipal, Principal, require
from app.core.errors import AppError, forbidden, not_found
from app.modules.academic.models import CourseOffering, Enrollment
from app.modules.academic.service import can_view_roster, get_offering
from app.modules.identity.models import User
from app.modules.recommendations import engine
from app.modules.recommendations.models import Recommendation

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
    source: str
    status: str
    useful: bool | None
    feedback_reason: str | None
    created_at: datetime
    resolved_at: datetime | None


def _out(r: Recommendation, course_titles: dict, names: dict | None = None) -> RecommendationOut:
    return RecommendationOut(
        id=r.id, offering_id=r.offering_id, course_title=course_titles.get(r.offering_id, ""),
        student_name=names.get(r.student_id) if names else None, kind=r.kind, target_type=r.target_type,
        target_id=r.target_id, title=r.title, reason=r.reason, expected_impact=r.expected_impact, priority=r.priority,
        source=r.source, status=r.status, useful=r.useful, feedback_reason=r.feedback_reason,
        created_at=r.created_at, resolved_at=r.resolved_at,
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
