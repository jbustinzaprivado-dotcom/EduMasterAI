"""Endpoints de IA (§4.10, §9.6, §9.7, §10.2): modelos, aprobación, predicciones de riesgo y revisión humana."""

import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import DB, CurrentPrincipal, Principal, require
from app.core.errors import AppError, forbidden, not_found
from app.modules.academic.models import CourseOffering, Enrollment
from app.modules.academic.service import can_manage_offering, can_view_roster, get_offering
from app.modules.audit.service import record
from app.modules.ml import service
from app.modules.ml.models import ModelVersion, Prediction

router = APIRouter(prefix="/ml", tags=["ml"])


# ---------- arquitectura para el visualizador ----------

class Layer(BaseModel):
    id: str
    name: str
    role: str  # input | projection | hidden | temporal | fusion | output
    display_nodes: int  # nodos que dibuja la interfaz (resumen visual, no el total real)
    units: str
    operation: str
    dimension: str
    detail: list[str]


class Architecture(BaseModel):
    model_name: str
    status: str  # design | published | inference | error
    status_label: str
    version: str | None
    dataset: str | None
    source: str
    note: str
    metrics: dict | None = None
    last_run: dict | None = None
    layers: list[Layer]


def _layers(spec_dims: dict | None) -> list[Layer]:
    tab = spec_dims.get("tab", 24) if spec_dims else 24
    gru = spec_dims.get("gru", 24) if spec_dims else 24
    fusion = spec_dims.get("fusion", 32) if spec_dims else 32
    return [
        Layer(id="input", name="Entrada", role="input", display_nodes=8, units="13 variables + secuencia",
              operation="Variables agregadas (§8.3) y secuencia semanal", dimension="[lote, 13] + [lote, 6, 4]",
              detail=["active_days_14d", "sessions_14d", "completion_ratio", "pace_gap", "assessment_mean",
                      "assessment_trend", "late_submissions_30d", "missed_assessments", "content_engagement",
                      "days_since_last_activity", "nivel del curso (3)"]),
        Layer(id="projection", name="Rama tabular", role="projection", display_nodes=6, units=str(tab),
              operation="Dense + ReLU sobre variables normalizadas", dimension=f"[lote, {tab}]",
              detail=["Perfil académico y métricas agregadas"]),
        Layer(id="temporal", name="Bloque temporal", role="temporal", display_nodes=6, units=str(gru),
              operation="GRU sobre 6 semanas (días activos, sesiones, actividades, horas)", dimension=f"[lote, {gru}]",
              detail=["Captura la evolución del comportamiento", "Rama temporal de §9.1"]),
        Layer(id="fusion", name="Fusión compartida", role="fusion", display_nodes=5, units=str(fusion),
              operation="Concatenación + Dense + LayerNorm + Dropout 0.2", dimension=f"[lote, {fusion}]",
              detail=["Combina patrones estáticos y temporales"]),
        Layer(id="heads", name="Cabezas de salida", role="output", display_nodes=4, units="1 activa · 3 planificadas",
              operation="Sigmoid calibrada (Platt)", dimension="[lote, 1]",
              detail=["C · Riesgo de abandono — ACTIVA", "A · Finalización — planificada", "B · Dominio — planificada",
                      "D · Ranking de recursos — planificada"]),
    ]


@router.get("/architecture", response_model=Architecture)
def architecture(db: DB, principal: Principal = require("dashboard.read")) -> Architecture:
    deployment = service.active_deployment(db, principal.organization_id)
    if deployment is None:
        return Architecture(
            model_name="EduMaster Multi-Task Learning Network", status="design",
            status_label="Diseño · sin modelo publicado en tu institución", version=None, dataset=None,
            source="Especificación §9.1", layers=_layers(None),
            note="Hay versiones entrenadas en el registro; un administrador debe aprobar su publicación (§9.6).",
        )
    v = deployment.model_version
    chosen = v.card["selection"]["chosen"]
    test = v.card["results"][chosen]["test"]
    run = service.LAST_RUN.get(principal.organization_id)
    return Architecture(
        model_name=f"{v.name} · {chosen}", status="inference" if run else "published",
        status_label="Publicado · inferencia activa" if run else "Publicado · listo para inferencia",
        version=v.version, dataset=f"{v.dataset_version} (sintético DEMO)", source=f"Model card {v.name} {v.version}",
        note="Pulsos de izquierda a derecha = propagación hacia delante. No hay entrenamiento en producción (§2.4).",
        metrics={"roc_auc": test["roc_auc"], "pr_auc": test["pr_auc"], "brier": test["brier"],
                 "threshold": round(v.threshold, 2)},
        last_run={"at": run["at"].isoformat(), "count": run["count"], "latency_ms": run["latency_ms"]} if run else None,
        layers=_layers({"tab": 24, "gru": 24, "fusion": 32}) if v.kind == "multitask_gru" else _layers(None),
    )


# ---------- modelos ----------

class ModelOut(BaseModel):
    id: uuid.UUID
    name: str
    version: str
    kind: str
    task: str
    dataset_version: str
    threshold: float
    registered_at: datetime
    published_here: bool
    card: dict


@router.get("/models", response_model=list[ModelOut])
def list_models(db: DB, principal: Principal = require("ml.read")) -> list[ModelOut]:
    deployment = service.active_deployment(db, principal.organization_id)
    return [
        ModelOut(id=v.id, name=v.name, version=v.version, kind=v.kind, task=v.task, dataset_version=v.dataset_version,
                 threshold=v.threshold, registered_at=v.registered_at, card=v.card,
                 published_here=bool(deployment and deployment.model_version_id == v.id))
        for v in db.scalars(select(ModelVersion).order_by(ModelVersion.registered_at.desc()))
    ]


class ApproveIn(BaseModel):
    note: str | None = Field(default=None, max_length=1000)


@router.post("/models/{model_id}/approve", response_model=ModelOut)
def approve(model_id: uuid.UUID, body: ApproveIn, db: DB, principal: Principal = require("ml.approve")) -> ModelOut:
    """Publica la versión en la institución del aprobador (§9.6: aprobación humana antes de producción)."""
    version = db.get(ModelVersion, model_id)
    if version is None:
        raise not_found("Modelo")
    service.publish(db, version, principal.organization_id, principal.user.id, body.note)
    db.commit()
    return ModelOut(id=version.id, name=version.name, version=version.version, kind=version.kind, task=version.task,
                    dataset_version=version.dataset_version, threshold=version.threshold,
                    registered_at=version.registered_at, card=version.card, published_here=True)


class RetireIn(BaseModel):
    reason: str = Field(min_length=5, max_length=1000)


@router.post("/models/{model_id}/retire", response_model=ModelOut)
def retire(model_id: uuid.UUID, body: RetireIn, db: DB, principal: Principal = require("ml.approve")) -> ModelOut:
    """Retira la versión publicada en la institución (rollback, §16.3). Motivo obligatorio y auditado."""
    version = db.get(ModelVersion, model_id)
    if version is None:
        raise not_found("Modelo")
    service.retire(db, version, principal.organization_id, principal.user.id, body.reason)
    db.commit()
    return ModelOut(id=version.id, name=version.name, version=version.version, kind=version.kind, task=version.task,
                    dataset_version=version.dataset_version, threshold=version.threshold,
                    registered_at=version.registered_at, card=version.card, published_here=False)


# ---------- predicciones ----------

class RunIn(BaseModel):
    offering_id: uuid.UUID | None = None


class RunOut(BaseModel):
    predictions: int
    high_risk: int
    model_version: str


@router.post("/predictions/run", response_model=RunOut)
def run_predictions(body: RunIn, db: DB, principal: CurrentPrincipal) -> RunOut:
    """Calcula el riesgo de las matrículas activas. ML Engineer: toda la institución; docente/coordinación: una oferta."""
    if body.offering_id:
        offering = get_offering(db, principal, body.offering_id)
        if not (principal.can("ml.manage") or can_manage_offering(principal, offering)):
            raise forbidden()
        offering_ids = [offering.id]
    else:
        if not principal.can("ml.manage"):
            raise forbidden()
        # Alcance del ML Engineer: todas las ofertas activas de SU institución (no ve notas ni nombres aquí).
        offering_ids = list(db.scalars(select(CourseOffering.id).where(
            CourseOffering.organization_id == principal.organization_id, CourseOffering.status == "active")))
    enrollments = list(db.scalars(select(Enrollment).where(Enrollment.offering_id.in_(offering_ids))))
    created = service.score_enrollments(db, principal.organization_id, enrollments, principal.user.id)
    db.commit()
    version = created[0].model_version.version if created else service.active_deployment(db, principal.organization_id).model_version.version
    return RunOut(predictions=len(created), high_risk=sum(p.risk_level == "alto" for p in created), model_version=version)


class RiskRow(BaseModel):
    prediction_id: uuid.UUID
    enrollment_id: uuid.UUID
    student_id: uuid.UUID
    score: float
    risk_level: str
    factors: list[dict]
    model_version: str
    created_at: datetime
    review_status: str
    review_note: str | None


@router.get("/offerings/{offering_id}/risk", response_model=list[RiskRow])
def offering_risk(offering_id: uuid.UUID, db: DB, principal: CurrentPrincipal) -> list[RiskRow]:
    """Riesgo por estudiante: solo para quien puede ver la lista nominal (docente de la oferta, administración,
    auditoría). El estudiante no ve su puntaje de riesgo (decisión D22)."""
    offering = get_offering(db, principal, offering_id)
    if not can_view_roster(principal, offering):
        raise forbidden()
    return [
        RiskRow(prediction_id=p.id, enrollment_id=p.enrollment_id, student_id=p.student_id, score=p.score,
                risk_level=p.risk_level, factors=p.factors or [], model_version=p.model_version.version,
                created_at=p.created_at, review_status=p.review_status, review_note=p.review_note)
        for p in service.latest_predictions(db, offering.id).values()
    ]


class ReviewIn(BaseModel):
    status: Literal["atendida", "descartada"]
    note: str | None = Field(default=None, max_length=1000)


@router.patch("/predictions/{prediction_id}/review", response_model=RiskRow)
def review(prediction_id: uuid.UUID, body: ReviewIn, db: DB, principal: CurrentPrincipal) -> RiskRow:
    """Revisión humana de la alerta (§9.8): el docente decide; su respuesta queda como retroalimentación."""
    p = db.get(Prediction, prediction_id)
    if p is None or not principal.can_see_org(p.organization_id):
        raise not_found("Predicción")
    offering = db.get(CourseOffering, p.offering_id)
    if not can_manage_offering(principal, offering):
        raise forbidden()
    if body.status == "descartada" and not (body.note and body.note.strip()):
        raise AppError(422, "validation_error", "Indica por qué descartas la alerta: sirve para evaluar el modelo.")
    p.review_status, p.review_note = body.status, body.note
    p.reviewed_by, p.reviewed_at = principal.user.id, datetime.now(UTC)
    record(db, action="prediction.reviewed", resource="prediction", resource_id=p.id, actor_id=principal.user.id,
           organization_id=p.organization_id, details={"status": body.status, "score": p.score})
    db.commit()
    return RiskRow(prediction_id=p.id, enrollment_id=p.enrollment_id, student_id=p.student_id, score=p.score,
                   risk_level=p.risk_level, factors=p.factors or [], model_version=p.model_version.version,
                   created_at=p.created_at, review_status=p.review_status, review_note=p.review_note)
