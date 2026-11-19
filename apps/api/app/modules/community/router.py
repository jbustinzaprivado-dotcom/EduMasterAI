"""Comunidad por curso (§4.8): publicar, comentar, reportar, moderar y silenciar.

Quién participa (decisión D31):
- Miembros: estudiantes matriculados (no retirados), el docente de la oferta y coordinación/administración.
- Anuncios: solo docente y coordinación/administración. Debates y comentarios: cualquier miembro.
- Moderación (ocultar con motivo, resolver reportes): docente de la oferta y coordinación/administración.
- La auditoría puede leer; el analista no ve contenido nominal (§3).
"""

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import DB, CurrentPrincipal, Principal
from app.core.errors import AppError, forbidden, not_found
from app.modules.academic.models import CourseOffering, Enrollment
from app.modules.academic.service import get_offering
from app.modules.audit.service import record
from app.modules.community.models import Comment, Mute, Post, Report
from app.modules.notifications.service import notify

router = APIRouter(tags=["comunidad"])

RULES = [
    "Respeta a las personas: critica ideas, no a quien las expone.",
    "No compartas datos personales propios ni de terceros.",
    "Mantén el tema del curso; usa el debate adecuado.",
    "Sin spam, publicidad ni contenido ofensivo.",
    "Si algo no cumple estas reglas, repórtalo: lo revisa el docente.",
]


def _role(db: DB, principal: Principal, offering: CourseOffering) -> dict:
    staff = principal.can("course.manage") and principal.can_see_org(offering.organization_id)
    teacher = offering.instructor_id == principal.user.id
    student = db.scalar(select(func.count()).select_from(Enrollment).where(
        Enrollment.offering_id == offering.id, Enrollment.student_id == principal.user.id,
        Enrollment.status != "dropped")) == 1
    reader = principal.can("audit.read") and principal.can_see_org(offering.organization_id)
    return {"read": staff or teacher or student or reader, "post": staff or teacher or student,
            "announce": staff or teacher, "moderate": staff or teacher}


def _offering_for(db: DB, principal: Principal, offering_id: uuid.UUID, need: str) -> tuple[CourseOffering, dict]:
    offering = get_offering(db, principal, offering_id)
    role = _role(db, principal, offering)
    if not role["read"]:
        raise forbidden()
    if not role[need]:
        raise forbidden()
    return offering, role


class PostOut(BaseModel):
    id: uuid.UUID
    offering_id: uuid.UUID
    kind: str
    title: str
    body: str
    author_name: str
    author_is_teacher: bool
    created_at: datetime
    comments: int
    hidden: bool
    hidden_reason: str | None
    mine: bool


class CommentOut(BaseModel):
    id: uuid.UUID
    body: str
    author_name: str
    author_is_teacher: bool
    created_at: datetime
    hidden: bool
    hidden_reason: str | None
    mine: bool


class SpaceOut(BaseModel):
    offering_id: uuid.UUID
    course_title: str
    can_post: bool
    can_announce: bool
    can_moderate: bool
    muted: bool
    open_reports: int
    rules: list[str]
    posts: list[PostOut]


def _post_out(p: Post, offering: CourseOffering, principal: Principal, comments: int, moderator: bool) -> PostOut:
    hide = p.hidden and not moderator
    return PostOut(
        id=p.id, offering_id=p.offering_id, kind=p.kind, title="Publicación oculta por moderación" if hide else p.title,
        body="" if hide else p.body, author_name=p.author.full_name, author_is_teacher=p.author_id == offering.instructor_id,
        created_at=p.created_at, comments=comments, hidden=p.hidden, hidden_reason=p.hidden_reason if moderator else None,
        mine=p.author_id == principal.user.id,
    )


@router.get("/offerings/{offering_id}/community", response_model=SpaceOut)
def space(offering_id: uuid.UUID, db: DB, principal: CurrentPrincipal) -> SpaceOut:
    offering, role = _offering_for(db, principal, offering_id, "read")
    posts = list(db.scalars(select(Post).where(Post.offering_id == offering.id)
                            .order_by((Post.kind == "anuncio").desc(), Post.created_at.desc())))
    counts = dict(db.execute(select(Comment.post_id, func.count()).where(
        Comment.post_id.in_([p.id for p in posts]), Comment.hidden.is_(False)).group_by(Comment.post_id)).all()) if posts else {}
    reports = db.scalar(select(func.count()).select_from(Report).where(
        Report.offering_id == offering.id, Report.status == "abierto")) if role["moderate"] else 0
    muted = db.get(Mute, (principal.user.id, offering.id)) is not None
    return SpaceOut(
        offering_id=offering.id, course_title=offering.course.title, can_post=role["post"],
        can_announce=role["announce"], can_moderate=role["moderate"], muted=muted, open_reports=reports or 0,
        rules=RULES, posts=[_post_out(p, offering, principal, counts.get(p.id, 0), role["moderate"]) for p in posts],
    )


class PostIn(BaseModel):
    kind: Literal["anuncio", "debate"] = "debate"
    title: str = Field(min_length=3, max_length=160)
    body: str = Field(min_length=2, max_length=5000)


def _members_to_notify(db: DB, offering: CourseOffering, exclude: uuid.UUID) -> list[uuid.UUID]:
    students = set(db.scalars(select(Enrollment.student_id).where(Enrollment.offering_id == offering.id,
                                                                  Enrollment.status != "dropped")))
    muted = set(db.scalars(select(Mute.user_id).where(Mute.offering_id == offering.id)))
    return [u for u in students | {offering.instructor_id} if u not in muted and u != exclude]


@router.post("/offerings/{offering_id}/community/posts", response_model=PostOut, status_code=201)
def create_post(offering_id: uuid.UUID, body: PostIn, db: DB, principal: CurrentPrincipal) -> PostOut:
    offering, role = _offering_for(db, principal, offering_id, "post")
    if body.kind == "anuncio" and not role["announce"]:
        raise AppError(403, "forbidden", "Solo el docente o la coordinación publican anuncios.")
    post = Post(organization_id=offering.organization_id, offering_id=offering.id, author_id=principal.user.id,
                kind=body.kind, title=body.title.strip(), body=body.body.strip())
    db.add(post)
    db.flush()
    if body.kind == "anuncio":
        notify(db, _members_to_notify(db, offering, principal.user.id), organization_id=offering.organization_id,
               kind="community.announcement", title=f"Anuncio en {offering.course.title}: {post.title}",
               body=post.body[:140], link=f"/comunidad?oferta={offering.id}&post={post.id}")
    db.commit()
    db.refresh(post)
    return _post_out(post, offering, principal, 0, role["moderate"])


class ThreadOut(BaseModel):
    post: PostOut
    comments: list[CommentOut]
    can_comment: bool
    can_moderate: bool


def _thread(db: DB, principal: Principal, post_id: uuid.UUID) -> tuple[Post, CourseOffering, dict]:
    post = db.get(Post, post_id)
    if post is None or not principal.can_see_org(post.organization_id):
        raise not_found("Publicación")
    offering, role = _offering_for(db, principal, post.offering_id, "read")
    if post.hidden and not role["moderate"]:
        raise not_found("Publicación")
    return post, offering, role


@router.get("/community/posts/{post_id}", response_model=ThreadOut)
def get_thread(post_id: uuid.UUID, db: DB, principal: CurrentPrincipal) -> ThreadOut:
    post, offering, role = _thread(db, principal, post_id)
    comments = list(db.scalars(select(Comment).where(Comment.post_id == post.id).order_by(Comment.created_at)))
    visible = [c for c in comments if role["moderate"] or not c.hidden]
    out = [
        CommentOut(id=c.id, body="" if c.hidden and not role["moderate"] else c.body, author_name=c.author.full_name,
                   author_is_teacher=c.author_id == offering.instructor_id, created_at=c.created_at, hidden=c.hidden,
                   hidden_reason=c.hidden_reason if role["moderate"] else None, mine=c.author_id == principal.user.id)
        for c in visible
    ]
    return ThreadOut(post=_post_out(post, offering, principal, sum(not c.hidden for c in comments), role["moderate"]),
                     comments=out, can_comment=role["post"], can_moderate=role["moderate"])


class CommentIn(BaseModel):
    body: str = Field(min_length=1, max_length=3000)


@router.post("/community/posts/{post_id}/comments", response_model=ThreadOut, status_code=201)
def add_comment(post_id: uuid.UUID, body: CommentIn, db: DB, principal: CurrentPrincipal) -> ThreadOut:
    post, offering, role = _thread(db, principal, post_id)
    if not role["post"]:
        raise forbidden()
    db.add(Comment(post_id=post.id, author_id=principal.user.id, body=body.body.strip()))
    # Avisa al autor de la publicación (si no la silenció y no es quien comenta).
    if post.author_id != principal.user.id and db.get(Mute, (post.author_id, offering.id)) is None:
        notify(db, [post.author_id], organization_id=offering.organization_id, kind="community.reply",
               title=f"{principal.user.full_name} respondió en «{post.title}»", body=body.body.strip()[:140],
               link=f"/comunidad?oferta={offering.id}&post={post.id}")
    db.commit()
    return get_thread(post_id, db, principal)


class ReportIn(BaseModel):
    target_type: Literal["post", "comment"]
    target_id: uuid.UUID
    reason: str = Field(min_length=5, max_length=500)


def _target(db: DB, target_type: str, target_id: uuid.UUID) -> tuple[Post | Comment, Post]:
    if target_type == "post":
        post = db.get(Post, target_id)
        if post is None:
            raise not_found("Contenido")
        return post, post
    comment = db.get(Comment, target_id)
    if comment is None:
        raise not_found("Contenido")
    return comment, db.get(Post, comment.post_id)


@router.post("/community/reports", status_code=201)
def report(body: ReportIn, db: DB, principal: CurrentPrincipal) -> dict:
    target, post = _target(db, body.target_type, body.target_id)
    if not principal.can_see_org(post.organization_id):
        raise not_found("Contenido")
    offering, _ = _offering_for(db, principal, post.offering_id, "post")
    db.add(Report(organization_id=offering.organization_id, offering_id=offering.id, target_type=body.target_type,
                  target_id=target.id, reporter_id=principal.user.id, reason=body.reason.strip()))
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise AppError(409, "conflict", "Ya reportaste este contenido.") from None
    notify(db, [offering.instructor_id], organization_id=offering.organization_id, kind="community.report",
           title=f"Contenido reportado en {offering.course.title}", body=body.reason.strip()[:140],
           link=f"/comunidad?oferta={offering.id}")
    db.commit()
    return {"status": "abierto"}


class ReportOut(BaseModel):
    id: uuid.UUID
    target_type: str
    target_id: uuid.UUID
    post_id: uuid.UUID
    excerpt: str
    reason: str
    reports: int
    created_at: datetime


@router.get("/offerings/{offering_id}/community/reports", response_model=list[ReportOut])
def open_reports(offering_id: uuid.UUID, db: DB, principal: CurrentPrincipal) -> list[ReportOut]:
    offering, _ = _offering_for(db, principal, offering_id, "moderate")
    rows = list(db.scalars(select(Report).where(Report.offering_id == offering.id, Report.status == "abierto")
                           .order_by(Report.created_at)))
    grouped: dict[uuid.UUID, list[Report]] = {}
    for r in rows:
        grouped.setdefault(r.target_id, []).append(r)
    out = []
    for target_id, reports in grouped.items():
        target, post = _target(db, reports[0].target_type, target_id)
        text = target.title if isinstance(target, Post) else target.body
        out.append(ReportOut(id=reports[0].id, target_type=reports[0].target_type, target_id=target_id, post_id=post.id,
                             excerpt=text[:200], reason=reports[0].reason, reports=len(reports),
                             created_at=reports[0].created_at))
    return out


class ModerateIn(BaseModel):
    action: Literal["ocultar", "mostrar", "desestimar"]
    reason: str | None = Field(default=None, max_length=500)


@router.post("/community/{target_type}/{target_id}/moderate")
def moderate(target_type: Literal["post", "comment"], target_id: uuid.UUID, body: ModerateIn, db: DB,
             principal: CurrentPrincipal) -> dict:
    """Ocultar/mostrar contenido o desestimar reportes. Siempre auditado (§4.8: trazabilidad)."""
    target, post = _target(db, target_type, target_id)
    if not principal.can_see_org(post.organization_id):
        raise not_found("Contenido")
    offering, _ = _offering_for(db, principal, post.offering_id, "moderate")
    if body.action == "ocultar":
        if not (body.reason and body.reason.strip()):
            raise AppError(422, "validation_error", "Indica el motivo: lo verá el resto de moderadores y la bitácora.")
        target.hidden, target.hidden_reason, target.hidden_by = True, body.reason.strip(), principal.user.id
    elif body.action == "mostrar":
        target.hidden, target.hidden_reason, target.hidden_by = False, None, None
    resolution = {"ocultar": "ocultado", "mostrar": "restaurado", "desestimar": "desestimado"}[body.action]
    for r in db.scalars(select(Report).where(Report.target_id == target.id, Report.status == "abierto")):
        r.status, r.resolved_by, r.resolution = "resuelto", principal.user.id, resolution
    record(db, action=f"community.{resolution}", resource=target_type, resource_id=target.id,
           actor_id=principal.user.id, organization_id=offering.organization_id,
           details={"reason": body.reason, "offering": offering.course.title})
    db.commit()
    return {"hidden": target.hidden, "resolution": resolution}


class MuteIn(BaseModel):
    muted: bool


@router.put("/offerings/{offering_id}/community/mute")
def set_mute(offering_id: uuid.UUID, body: MuteIn, db: DB, principal: CurrentPrincipal) -> dict:
    offering, _ = _offering_for(db, principal, offering_id, "read")
    if body.muted:
        if db.get(Mute, (principal.user.id, offering.id)) is None:
            db.add(Mute(user_id=principal.user.id, offering_id=offering.id))
    else:
        db.execute(delete(Mute).where(Mute.user_id == principal.user.id, Mute.offering_id == offering.id))
    db.commit()
    return {"muted": body.muted}
