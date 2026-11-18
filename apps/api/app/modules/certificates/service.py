"""Emisión, anulación y PDF de certificados (§4.7, decisión D29).

Criterio oficial de emisión (D29): progreso 100 % (matrícula completada) y nota final ponderada ≥ 11/20 sobre
las evaluaciones ya calificadas, con al menos el 50 % del peso evaluado. Ninguna predicción de IA interviene.
"""

from __future__ import annotations

import io
import secrets
from datetime import UTC, datetime

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.modules.academic.models import Assessment, Enrollment
from app.modules.academic.service import best_scores, weighted_grade
from app.modules.audit.service import record
from app.modules.certificates.models import Certificate
from app.modules.identity.models import Organization
from app.modules.notifications.service import notify

MIN_GRADE = 11.0
MIN_GRADED_WEIGHT = 0.5
_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sin 0/O ni 1/I para dictarlo sin errores


def eligibility(db: Session, enrollment: Enrollment) -> tuple[bool, str, float | None]:
    """(elegible, motivo, nota final)."""
    if enrollment.status != "completed":
        return False, f"Avance {round(enrollment.progress * 100)} %: debe completar todas las actividades obligatorias.", None
    assessments = list(db.scalars(select(Assessment).where(Assessment.offering_id == enrollment.offering_id)))
    grade, weight = weighted_grade(assessments, best_scores(db, enrollment.offering_id, enrollment.student_id),
                                   enrollment.student_id)
    if assessments and weight < MIN_GRADED_WEIGHT:
        return False, f"Solo hay {round(weight * 100)} % del peso calificado (mínimo 50 %).", grade
    if grade is not None and grade < MIN_GRADE:
        return False, f"Nota final {grade:.1f}: el mínimo aprobatorio es 11.", grade
    return True, "Cumple los criterios oficiales.", grade


def active_certificate(db: Session, enrollment_id) -> Certificate | None:
    return db.scalar(select(Certificate).where(Certificate.enrollment_id == enrollment_id,
                                               Certificate.status == "emitido"))


def _new_code(db: Session) -> str:
    while True:
        code = "".join(secrets.choice(_ALPHABET) for _ in range(10))
        if not db.scalar(select(Certificate.id).where(Certificate.verification_code == code)):
            return code


def _folio(db: Session, enrollment: Enrollment) -> str:
    org_code = db.get(Organization, enrollment.organization_id).code
    year = datetime.now(UTC).year
    count = db.scalar(select(func.count()).select_from(Certificate)
                      .where(Certificate.organization_id == enrollment.organization_id)) or 0
    return f"EDM-{org_code}-{year}-{count + 1:06d}"


def issue(db: Session, enrollment: Enrollment, issued_by=None, replaces: Certificate | None = None) -> Certificate:
    if active_certificate(db, enrollment.id):
        raise AppError(409, "conflict", "Ya existe un certificado vigente para este logro.")
    ok, reason, grade = eligibility(db, enrollment)
    if not ok:
        raise AppError(422, "not_eligible", reason)
    cert = Certificate(
        organization_id=enrollment.organization_id, enrollment_id=enrollment.id, student_id=enrollment.student_id,
        offering_id=enrollment.offering_id, folio=_folio(db, enrollment), verification_code=_new_code(db),
        final_grade=grade, issued_by=issued_by, replaces_id=replaces.id if replaces else None,
    )
    db.add(cert)
    db.flush()
    record(db, action="certificate.issued", resource="certificate", resource_id=cert.id, actor_id=issued_by,
           organization_id=cert.organization_id,
           details={"folio": cert.folio, "student": enrollment.student.full_name, "replaces": str(replaces.id) if replaces else None})
    notify(db, [enrollment.student_id], organization_id=cert.organization_id, kind="certificate.issued",
           title=f"Certificado emitido: {enrollment.offering.course.title}",
           body=f"Folio {cert.folio}. Ya puedes descargarlo.", link="/certificados")
    return cert


def try_auto_issue(db: Session, enrollment: Enrollment) -> Certificate | None:
    """Al completar un curso, el sistema emite el certificado si se cumplen los criterios (§4.7)."""
    if active_certificate(db, enrollment.id):
        return None
    ok, _, _ = eligibility(db, enrollment)
    return issue(db, enrollment) if ok else None


def revoke(db: Session, cert: Certificate, actor_id, reason: str) -> None:
    if cert.status != "emitido":
        raise AppError(422, "validation_error", "El certificado ya está anulado.")
    cert.status, cert.revoked_at, cert.revoked_by, cert.revoke_reason = "anulado", datetime.now(UTC), actor_id, reason
    record(db, action="certificate.revoked", resource="certificate", resource_id=cert.id, actor_id=actor_id,
           organization_id=cert.organization_id, details={"folio": cert.folio, "reason": reason})
    notify(db, [cert.student_id], organization_id=cert.organization_id, kind="certificate.revoked",
           title=f"Certificado anulado ({cert.folio})", body=f"Motivo: {reason}", link="/certificados")


def render_pdf(cert: Certificate, institution: str, verify_url: str) -> bytes:
    """PDF A4 horizontal con la identidad de §5.1 y un QR que lleva a la verificación pública."""
    e = cert.enrollment
    buffer = io.BytesIO()
    w, h = landscape(A4)
    c = canvas.Canvas(buffer, pagesize=(w, h))
    c.setTitle(f"Certificado {cert.folio}")
    c.setFillColor(HexColor("#06152B"))
    c.rect(0, 0, w, h, fill=1, stroke=0)
    c.setStrokeColor(HexColor("#087FE5"))
    c.setLineWidth(2)
    c.roundRect(24, 24, w - 48, h - 48, 16, fill=0, stroke=1)
    c.setFillColor(HexColor("#20C8F5"))
    c.setFont("Helvetica-Bold", 14)
    c.drawString(56, h - 70, "EduMaster.ai")
    c.setFillColor(HexColor("#8EA3C2"))
    c.setFont("Helvetica", 10)
    c.drawString(56, h - 86, institution)
    c.drawRightString(w - 56, h - 70, f"Folio {cert.folio}")
    if cert.status == "anulado":
        c.setFillColor(HexColor("#FF5C7A"))
        c.setFont("Helvetica-Bold", 16)
        c.drawRightString(w - 56, h - 92, "ANULADO")
    c.setFillColor(HexColor("#EAF2FF"))
    c.setFont("Helvetica", 16)
    c.drawCentredString(w / 2, h - 170, "Certifica que")
    c.setFont("Helvetica-Bold", 30)
    c.drawCentredString(w / 2, h - 215, e.student.full_name)
    c.setFont("Helvetica", 15)
    c.drawCentredString(w / 2, h - 255, "completó satisfactoriamente el curso")
    c.setFillColor(HexColor("#20C8F5"))
    c.setFont("Helvetica-Bold", 22)
    c.drawCentredString(w / 2, h - 292, e.offering.course.title)
    c.setFillColor(HexColor("#8EA3C2"))
    c.setFont("Helvetica", 11)
    grade = f" · Nota final {cert.final_grade:.1f}/20" if cert.final_grade is not None else ""
    c.drawCentredString(w / 2, h - 318, f"{e.offering.course.code} · {e.offering.period} · {e.offering.cohort}{grade}")
    c.drawCentredString(w / 2, h - 336, f"Emitido el {cert.issued_at.astimezone(UTC).strftime('%d/%m/%Y')}")
    qr = QrCodeWidget(verify_url)
    x0, y0, x1, y1 = qr.getBounds()
    size = 96
    drawing = Drawing(size, size, transform=[size / (x1 - x0), 0, 0, size / (y1 - y0), 0, 0])
    drawing.add(qr)
    c.setFillColor(HexColor("#FFFFFF"))
    c.rect(56, 52, size + 8, size + 8, fill=1, stroke=0)
    renderPDF.draw(drawing, c, 60, 56)
    c.setFillColor(HexColor("#8EA3C2"))
    c.setFont("Helvetica", 9)
    c.drawString(170, 92, "Verifica la autenticidad escaneando el código o en:")
    c.setFillColor(HexColor("#EAF2FF"))
    c.drawString(170, 78, verify_url)
    c.setFillColor(HexColor("#8EA3C2"))
    c.drawString(170, 64, f"Código de verificación: {cert.verification_code}")
    c.drawRightString(w - 56, 64, "Documento DEMO generado por un proyecto académico.")
    c.showPage()
    c.save()
    return buffer.getvalue()
