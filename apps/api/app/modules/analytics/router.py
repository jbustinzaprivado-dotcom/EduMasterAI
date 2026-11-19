"""Endpoints de analítica y exportación (§4.4, §10.2 GET /analytics/progress).

Permisos (§3): administración, coordinación, auditoría y analista ven agregados de la institución; el docente,
solo sus ofertas. El detalle por estudiante (con nombres) NO está disponible para el analista: solo agregados.
Toda exportación queda auditada con formato, nivel, filtros y número de filas.
"""

import csv
import io
import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Query
from fastapi.responses import Response
from pydantic import AwareDatetime

from app.api.deps import DB, CurrentPrincipal, Principal
from app.core.errors import AppError, forbidden
from app.modules.analytics import service
from app.modules.audit.service import record

router = APIRouter(prefix="/analytics", tags=["analítica"])


def _check(principal: Principal) -> None:
    if not principal.can("analytics.read"):
        raise forbidden()


def _students_allowed(principal: Principal) -> bool:
    """Detalle nominal: gestión, docentes (sus ofertas) y auditoría. El analista solo ve agregados (§3)."""
    return principal.can("course.manage") or principal.can("assessment.manage") or principal.can("audit.read")


def _filters(date_from, date_to, offering_id, instructor_id, cohort, period) -> service.Filters:
    default_from, default_to = service.default_range()
    f = service.Filters(date_from=date_from or default_from, date_to=date_to or default_to, offering_id=offering_id,
                        instructor_id=instructor_id, cohort=cohort or None, period=period or None)
    if f.date_to <= f.date_from:
        raise AppError(422, "validation_error", "La fecha final debe ser posterior a la inicial.")
    if (f.date_to - f.date_from).days > 400:
        raise AppError(422, "validation_error", "El rango máximo es de 400 días.")
    return f


@router.get("/overview")
def overview(db: DB, principal: CurrentPrincipal,
             date_from: AwareDatetime | None = None, date_to: AwareDatetime | None = None,
             offering_id: uuid.UUID | None = None, instructor_id: uuid.UUID | None = None,
             cohort: str | None = Query(default=None, max_length=64),
             period: str | None = Query(default=None, max_length=16)) -> dict:
    _check(principal)
    f = _filters(date_from, date_to, offering_id, instructor_id, cohort, period)
    offerings = service.visible_offerings(db, principal, f)
    data = service.compute(db, offerings, f)
    if not _students_allowed(principal):
        data["students"] = None
    all_visible = service.visible_offerings(db, principal, service.Filters(f.date_from, f.date_to))
    return {
        "generated_at": datetime.now(UTC).isoformat(), "filters": f.describe(db),
        "definitions": {k: {"label": v[0], "unit": v[1], "definition": v[2]} for k, v in service.DEFINITIONS.items()},
        "options": {
            "offerings": [{"id": str(o.id), "label": f"{o.course.code} · {o.cohort} · {o.period}"} for o in all_visible],
            "cohorts": sorted({o.cohort for o in all_visible}),
            "periods": sorted({o.period for o in all_visible}, reverse=True),
            "instructors": sorted({(str(o.instructor_id), o.instructor.full_name) for o in all_visible}, key=lambda x: x[1]),
        },
        "students_visible": _students_allowed(principal),
        **data,
    }


OFFERING_COLUMNS = [
    ("course_code", "Curso"), ("cohort", "Cohorte"), ("period", "Periodo"), ("instructor", "Docente"),
    ("enrolled", "Matriculados"), ("participation_rate", "Participación"), ("active_hours", "Horas activas"),
    ("avg_active_days", "Días activos/estudiante"), ("submissions", "Entregas"), ("on_time_rate", "A tiempo"),
    ("attempts_per_assessment", "Intentos/evaluación"), ("avg_progress", "Progreso promedio"),
    ("completion_rate", "Finalización"), ("avg_grade", "Nota promedio"),
]
STUDENT_COLUMNS = [
    ("student_name", "Estudiante"), ("student_email", "Correo"), ("course_code", "Curso"), ("cohort", "Cohorte"),
    ("active_days", "Días activos"), ("active_hours", "Horas activas"), ("submissions", "Entregas"),
    ("late_submissions", "Tardías"), ("progress", "Progreso"), ("status", "Estado"), ("grade", "Nota"),
    ("last_activity_at", "Última actividad"),
]
PERCENT = {"participation_rate", "on_time_rate", "avg_progress", "completion_rate", "progress"}


def _cell(key: str, value):
    if value is None:
        return ""
    if key in PERCENT:
        return round(value * 100, 1)
    return value


def _header_lines(generated: str, filters: dict, level: str) -> list[str]:
    return [
        "EduMaster.ai · Analítica educativa (datos DEMO)",
        f"Generado (UTC): {generated}",
        f"Nivel: {'por oferta' if level == 'offerings' else 'por estudiante'}",
        "Filtros: " + "; ".join(f"{k}={v}" for k, v in filters.items()),
        "Porcentajes en %, horas en horas, notas en escala 0-20.",
    ]


def _csv(header, columns, rows) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")  # ";" para que Excel en español separe bien las columnas
    for line in header:
        w.writerow([line])
    w.writerow([])
    w.writerow([label for _, label in columns])
    for r in rows:
        w.writerow([_cell(k, r.get(k)) for k, _ in columns])
    return ("﻿" + buf.getvalue()).encode("utf-8")  # BOM: acentos correctos al abrir en Excel


def _xlsx(header, columns, rows) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    wb = Workbook()
    ws = wb.active
    ws.title = "Analítica"
    for line in header:
        ws.append([line])
    ws["A1"].font = Font(bold=True, size=13)
    ws.append([])
    ws.append([label for _, label in columns])
    for cell in ws[ws.max_row]:
        cell.font, cell.fill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="087FE5")
    for r in rows:
        ws.append([_cell(k, r.get(k)) for k, _ in columns])
    for i, (_, label) in enumerate(columns, start=1):
        ws.column_dimensions[ws.cell(row=len(header) + 2, column=i).column_letter].width = max(12, len(label) + 4)
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def _pdf(header, columns, rows) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    out = io.BytesIO()
    doc = SimpleDocTemplate(out, pagesize=landscape(A4), leftMargin=24, rightMargin=24, topMargin=24, bottomMargin=24,
                            title="Analítica EduMaster.ai")
    styles = getSampleStyleSheet()
    story = [Paragraph(header[0], styles["Title"])] + [Paragraph(line, styles["Normal"]) for line in header[1:]]
    story.append(Spacer(0, 10))
    data = [[label for _, label in columns]] + [[str(_cell(k, r.get(k))) for k, _ in columns] for r in rows]
    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#087FE5")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 7), ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#8EA3C2")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#EEF5FF")]),
    ]))
    story.append(table)
    doc.build(story)
    return out.getvalue()


MEDIA = {"csv": "text/csv; charset=utf-8",
         "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
         "pdf": "application/pdf"}


@router.get("/export")
def export(db: DB, principal: CurrentPrincipal, format: Literal["csv", "xlsx", "pdf"] = "csv",
           level: Literal["offerings", "students"] = "offerings",
           date_from: AwareDatetime | None = None, date_to: AwareDatetime | None = None,
           offering_id: uuid.UUID | None = None, instructor_id: uuid.UUID | None = None,
           cohort: str | None = Query(default=None, max_length=64),
           period: str | None = Query(default=None, max_length=16)) -> Response:
    """Exporta lo mismo que se ve, con fecha y filtros en el encabezado, y deja constancia en la bitácora (§4.4)."""
    _check(principal)
    if level == "students" and not _students_allowed(principal):
        raise forbidden()
    f = _filters(date_from, date_to, offering_id, instructor_id, cohort, period)
    data = service.compute(db, service.visible_offerings(db, principal, f), f)
    rows, columns = (data["students"], STUDENT_COLUMNS) if level == "students" else (data["by_offering"], OFFERING_COLUMNS)
    generated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M")
    filters = f.describe(db)
    header = _header_lines(generated, filters, level)
    content = {"csv": _csv, "xlsx": _xlsx, "pdf": _pdf}[format](header, columns, rows)
    record(db, action="analytics.exported", resource="analytics", actor_id=principal.user.id,
           organization_id=principal.organization_id,
           details={"format": format, "level": level, "rows": len(rows), "filters": filters})
    db.commit()
    name = f"edumaster-analitica-{level}-{datetime.now(UTC).strftime('%Y%m%d-%H%M')}.{format}"
    return Response(content, media_type=MEDIA[format], headers={"Content-Disposition": f'attachment; filename="{name}"'})
