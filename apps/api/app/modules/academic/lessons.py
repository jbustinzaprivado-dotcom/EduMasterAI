"""Contenido de las lecciones (§4.3): lectura, recursos y video, con versionado y trazabilidad.

- Leer: cualquiera que vea la oferta (estudiante matriculado, su docente, gestión, auditoría, analista).
- Editar: coordinación/administración (course.manage) o el docente que dicta una oferta del curso.
  Cada edición sube la versión del contenido y queda en la bitácora: quién modificó qué y cuándo.
Seguridad: el texto se guarda tal cual y la web lo muestra como texto (nunca como HTML); los enlaces solo
pueden ser http(s) para evitar `javascript:` y similares (§11: XSS).
"""

import uuid
from datetime import UTC, datetime
from urllib.parse import urlparse

from fastapi import APIRouter
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from app.api.deps import DB, CurrentPrincipal, Principal
from app.core.errors import AppError, forbidden, not_found
from app.modules.academic.models import CourseActivity, CourseOffering
from app.modules.academic.service import get_offering
from app.modules.audit.service import record
from app.modules.identity.models import User

router = APIRouter(tags=["lecciones"])


def _check_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("Solo se permiten enlaces http(s).")
    return url.strip()


class Resource(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    url: str = Field(max_length=500)

    @field_validator("url")
    @classmethod
    def _url(cls, v: str) -> str:
        return _check_url(v)


class LessonOut(BaseModel):
    id: uuid.UUID
    offering_id: uuid.UUID
    unit_position: int
    unit_title: str
    position: int
    title: str
    kind: str
    estimated_minutes: int
    required: bool
    content: str
    resources: list[Resource]
    video_url: str | None
    content_version: int
    content_updated_at: datetime | None
    content_updated_by: str | None
    can_edit: bool
    previous_id: uuid.UUID | None
    next_id: uuid.UUID | None


class LessonPatch(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=160)
    estimated_minutes: int | None = Field(default=None, ge=1, le=600)
    content: str | None = Field(default=None, max_length=20000)
    resources: list[Resource] | None = Field(default=None, max_length=10)
    video_url: str | None = Field(default=None, max_length=500)

    @field_validator("video_url")
    @classmethod
    def _video(cls, v: str | None) -> str | None:
        return _check_url(v) if v else None


def _can_edit(db: DB, principal: Principal, course_id: uuid.UUID, organization_id: uuid.UUID) -> bool:
    if not principal.can_see_org(organization_id):
        return False
    if principal.can("course.manage"):
        return True
    return principal.can("assessment.manage") and db.scalar(select(CourseOffering.id).where(
        CourseOffering.course_id == course_id, CourseOffering.instructor_id == principal.user.id).limit(1)) is not None


def _lesson(db: DB, principal: Principal, offering: CourseOffering, activity: CourseActivity) -> LessonOut:
    ordered = [a for u in offering.course.units for a in u.activities]
    i = next(k for k, a in enumerate(ordered) if a.id == activity.id)
    editor = db.get(User, activity.content_updated_by) if activity.content_updated_by else None
    return LessonOut(
        id=activity.id, offering_id=offering.id, unit_position=activity.unit.position, unit_title=activity.unit.title,
        position=activity.position, title=activity.title, kind=activity.kind,
        estimated_minutes=activity.estimated_minutes, required=activity.required, content=activity.content or "",
        resources=[Resource(**r) for r in activity.resources or []], video_url=activity.video_url,
        content_version=activity.content_version, content_updated_at=activity.content_updated_at,
        content_updated_by=editor.full_name if editor else None,
        can_edit=_can_edit(db, principal, offering.course_id, offering.organization_id),
        previous_id=ordered[i - 1].id if i > 0 else None, next_id=ordered[i + 1].id if i + 1 < len(ordered) else None,
    )


def _activity_in(offering: CourseOffering, activity_id: uuid.UUID) -> CourseActivity:
    for unit in offering.course.units:
        for a in unit.activities:
            if a.id == activity_id:
                return a
    raise not_found("Actividad")


@router.get("/offerings/{offering_id}/activities/{activity_id}", response_model=LessonOut)
def get_lesson(offering_id: uuid.UUID, activity_id: uuid.UUID, db: DB, principal: CurrentPrincipal) -> LessonOut:
    offering = get_offering(db, principal, offering_id)  # ABAC: solo quien ve la oferta
    return _lesson(db, principal, offering, _activity_in(offering, activity_id))


@router.patch("/offerings/{offering_id}/activities/{activity_id}", response_model=LessonOut)
def update_lesson(offering_id: uuid.UUID, activity_id: uuid.UUID, body: LessonPatch, db: DB,
                  principal: CurrentPrincipal) -> LessonOut:
    offering = get_offering(db, principal, offering_id)
    activity = _activity_in(offering, activity_id)
    if not _can_edit(db, principal, offering.course_id, offering.organization_id):
        raise forbidden()
    changed = []
    for field in ("title", "estimated_minutes", "content", "video_url"):
        if field in body.model_fields_set and getattr(body, field) != getattr(activity, field):
            setattr(activity, field, getattr(body, field))
            changed.append(field)
    if body.resources is not None:
        new = [r.model_dump() for r in body.resources]
        if new != (activity.resources or []):
            activity.resources = new
            changed.append("resources")
    if not changed:
        raise AppError(422, "validation_error", "No hay cambios que guardar.")
    activity.content_version += 1
    activity.content_updated_at, activity.content_updated_by = datetime.now(UTC), principal.user.id
    record(db, action="activity.updated", resource="activity", resource_id=activity.id, actor_id=principal.user.id,
           organization_id=offering.organization_id,
           details={"course": offering.course.code, "activity": activity.title, "fields": changed,
                    "version": activity.content_version})
    db.commit()
    return _lesson(db, principal, offering, activity)

