"""Endpoints de certificados (§4.7, §10.2): emisión, anulación, PDF y verificación pública."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import DB, CurrentPrincipal, Principal, require
from app.core.context import client_ip
from app.core.errors import AppError, forbidden, not_found
from app.core.rate_limit import SlidingWindowLimiter
from app.modules.academic.models import CourseOffering, Enrollment
from app.modules.academic.service import can_manage_offering, can_view_roster, get_offering, offerings_query
from app.modules.audit.service import record
from app.modules.certificates import service
from app.modules.certificates.models import Certificate
from app.modules.identity.models import Organization

router = APIRouter(prefix="/certificates", tags=["certificados"])
verify_limiter = SlidingWindowLimiter(max_hits=30, window_seconds=60)  # endpoint público


class CertificateOut(BaseModel):
    id: uuid.UUID
    folio: str
    verification_code: str
    status: str
    student_id: uuid.UUID
    student_name: str
    course_title: str
    course_code: str
    cohort: str
    period: str
    offering_id: uuid.UUID
    final_grade: float | None
    issued_at: datetime
    issued_by_system: bool
    revoked_at: datetime | None
    revoke_reason: str | None


def _out(c: Certificate) -> CertificateOut:
    e = c.enrollment
    return CertificateOut(
        id=c.id, folio=c.folio, verification_code=c.verification_code, status=c.status, student_id=c.student_id,
        student_name=e.student.full_name, course_title=e.offering.course.title, course_code=e.offering.course.code,
        cohort=e.offering.cohort, period=e.offering.period, offering_id=c.offering_id, final_grade=c.final_grade,
        issued_at=c.issued_at, issued_by_system=c.issued_by is None, revoked_at=c.revoked_at,
        revoke_reason=c.revoke_reason,
    )


def _visible(db: DB, principal: Principal, cert: Certificate | None) -> Certificate:
    if cert is None:
        raise not_found("Certificado")
    if cert.student_id == principal.user.id:
        return cert
    offering = db.get(CourseOffering, cert.offering_id)
    if offering is None or not can_view_roster(principal, offering):
        raise not_found("Certificado")
    return cert


@router.get("", response_model=list[CertificateOut])
def list_certificates(db: DB, principal: CurrentPrincipal) -> list[CertificateOut]:
    """Estudiante: los suyos. Docente: los de sus ofertas. Administración/auditoría: los de la institución."""
    q = select(Certificate).order_by(Certificate.issued_at.desc())
    if principal.can("learning") and not principal.can("course.read.all"):
        q = q.where(Certificate.student_id == principal.user.id)
    else:
        visible = [o for o in db.scalars(offerings_query(principal)) if can_view_roster(principal, o)]
        q = q.where(Certificate.offering_id.in_([o.id for o in visible]))
    return [_out(c) for c in db.scalars(q)]


class EligibilityRow(BaseModel):
    enrollment_id: uuid.UUID
    student_name: str
    progress: float
    eligible: bool
    reason: str
    final_grade: float | None
    certificate: CertificateOut | None


@router.get("/offerings/{offering_id}", response_model=list[EligibilityRow])
def offering_eligibility(offering_id: uuid.UUID, db: DB, principal: CurrentPrincipal) -> list[EligibilityRow]:
    offering = get_offering(db, principal, offering_id)
    if not can_view_roster(principal, offering):
        raise forbidden()
    rows = []
    for e in sorted(db.scalars(select(Enrollment).where(Enrollment.offering_id == offering.id)),
                    key=lambda e: e.student.full_name):
        ok, reason, grade = service.eligibility(db, e)
        cert = service.active_certificate(db, e.id)
        rows.append(EligibilityRow(enrollment_id=e.id, student_name=e.student.full_name, progress=e.progress,
                                   eligible=ok, reason=reason, final_grade=grade, certificate=_out(cert) if cert else None))
    return rows


class IssueIn(BaseModel):
    enrollment_id: uuid.UUID


@router.post("", response_model=CertificateOut, status_code=201)
def issue(body: IssueIn, db: DB, principal: CurrentPrincipal) -> CertificateOut:
    """Emisión manual (docente de la oferta o administración) cuando el sistema no la hizo automáticamente."""
    enrollment = db.get(Enrollment, body.enrollment_id)
    if enrollment is None or not principal.can_see_org(enrollment.organization_id):
        raise not_found("Matrícula")
    offering = get_offering(db, principal, enrollment.offering_id)
    if not (principal.can("course.manage") or can_manage_offering(principal, offering)):
        raise forbidden()
    previous = db.scalar(select(Certificate).where(Certificate.enrollment_id == enrollment.id,
                                                   Certificate.status == "anulado")
                         .order_by(Certificate.revoked_at.desc()).limit(1))
    cert = service.issue(db, enrollment, issued_by=principal.user.id, replaces=previous)
    db.commit()
    return _out(cert)


class RevokeIn(BaseModel):
    reason: str = Field(min_length=5, max_length=500)


@router.post("/{certificate_id}/revoke", response_model=CertificateOut)
def revoke(certificate_id: uuid.UUID, body: RevokeIn, db: DB, principal: Principal = require("course.manage")) -> CertificateOut:
    cert = db.get(Certificate, certificate_id)
    if cert is None or not principal.can_see_org(cert.organization_id):
        raise not_found("Certificado")
    service.revoke(db, cert, principal.user.id, body.reason.strip())
    db.commit()
    return _out(cert)


def _public_base(request: Request) -> str:
    """Dirección pública real (detrás del túnel llega en Host y X-Forwarded-Proto)."""
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("host", request.url.netloc)
    return f"{proto}://{host}"


@router.get("/{certificate_id}/pdf")
def download_pdf(certificate_id: uuid.UUID, request: Request, db: DB, principal: CurrentPrincipal) -> Response:
    cert = _visible(db, principal, db.get(Certificate, certificate_id))
    institution = db.get(Organization, cert.organization_id).name
    pdf = service.render_pdf(cert, institution, f"{_public_base(request)}/verificar/{cert.verification_code}")
    record(db, action="certificate.downloaded", resource="certificate", resource_id=cert.id,
           actor_id=principal.user.id, organization_id=cert.organization_id, details={"folio": cert.folio})
    db.commit()
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{cert.folio}.pdf"'})


class VerificationOut(BaseModel):
    valid: bool
    status: str
    folio: str
    student_name: str
    course_title: str
    institution: str
    issued_at: datetime
    revoked_at: datetime | None


@router.get("/verify/{code}", response_model=VerificationOut)
def verify(code: str, db: DB) -> VerificationOut:
    """Verificación pública SIN sesión (§4.7): solo datos mínimos, nunca notas ni correos."""
    if not verify_limiter.allow(client_ip.get() or "?"):
        raise AppError(429, "too_many_requests", "Demasiadas consultas. Espera un minuto.")
    cert = db.scalar(select(Certificate).where(Certificate.verification_code == code.strip().upper()))
    if cert is None:
        raise not_found("Certificado")
    e = cert.enrollment
    return VerificationOut(
        valid=cert.status == "emitido", status=cert.status, folio=cert.folio, student_name=e.student.full_name,
        course_title=e.offering.course.title, institution=db.get(Organization, cert.organization_id).name,
        issued_at=cert.issued_at, revoked_at=cert.revoked_at,
    )
