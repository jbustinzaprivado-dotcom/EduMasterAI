"""Servicio de inferencia (§9.7): registro de versiones, despliegue por institución y predicción de riesgo."""

from __future__ import annotations

import json
import time
import uuid
from datetime import UTC, datetime
from functools import lru_cache

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import ROOT
from app.core.errors import AppError
from app.modules.academic.models import Assessment, AssessmentAttempt, CourseOffering, Enrollment, LearningEvent
from app.modules.academic.service import required_activity_ids
from app.modules.audit.service import record
from app.modules.ml.features import (
    FEATURE_SCHEMA_VERSION,
    AssessmentRec,
    EnrollmentContext,
    EventRec,
    compute,
)
from app.modules.ml.inference import RiskModel
from app.modules.identity.models import Role, User
from app.modules.ml.models import ModelDeployment, ModelVersion, Prediction
from app.modules.notifications.service import notify

REGISTRY = ROOT / "ml" / "registry"
LAST_RUN: dict[uuid.UUID, dict] = {}  # última ejecución por institución (latencia para el panel de estado)


def sync_registry(db: Session) -> int:
    """Registra en la base las versiones presentes en ml/registry (model.json + model_card.json). Idempotente."""
    created = 0
    for card_path in sorted(REGISTRY.glob("*/*/model_card.json")):
        card = json.loads(card_path.read_text(encoding="utf-8"))
        exists = db.scalar(select(ModelVersion).where(ModelVersion.name == card["name"],
                                                      ModelVersion.version == card["version"]))
        if exists:
            continue
        spec = json.loads((card_path.parent / "model.json").read_text(encoding="utf-8"))
        db.add(ModelVersion(
            name=card["name"], version=card["version"], kind=card["kind"], task=spec["task"],
            artifact_path=str((card_path.parent / "model.json").relative_to(ROOT)).replace("\\", "/"),
            dataset_version=card["dataset"]["version"], threshold=spec["threshold"], card=card,
        ))
        created += 1
    db.commit()
    return created


@lru_cache(maxsize=8)
def load_model(artifact_path: str) -> RiskModel:
    return RiskModel.load(ROOT / artifact_path)


def active_deployment(db: Session, organization_id: uuid.UUID) -> ModelDeployment | None:
    return db.scalar(select(ModelDeployment).where(ModelDeployment.organization_id == organization_id,
                                                   ModelDeployment.status == "published"))


def publish(db: Session, version: ModelVersion, organization_id: uuid.UUID, approver: uuid.UUID, note: str | None
            ) -> ModelDeployment:
    if version.card.get("selection", {}).get("chosen") is None:
        raise AppError(422, "validation_error", "La versión no tiene model card completa.")
    current = active_deployment(db, organization_id)
    if current and current.model_version_id == version.id:
        raise AppError(409, "conflict", "Esta versión ya está publicada en la institución.")
    if current:
        current.status, current.retired_at = "retired", datetime.now(UTC)
    deployment = ModelDeployment(organization_id=organization_id, model_version_id=version.id,
                                 approved_by=approver, note=note)
    db.add(deployment)
    db.flush()
    record(db, action="model.published", resource="model", resource_id=version.id, actor_id=approver,
           organization_id=organization_id,
           details={"model": version.name, "version": version.version, "replaces": str(current.model_version_id) if current else None})
    staff = db.scalars(select(User.id).where(User.organization_id == organization_id, User.status == "active",
                                             User.roles.any(Role.code.in_(["ml_engineer", "admin", "coordinador"]))))
    notify(db, list(staff), organization_id=organization_id, kind="model.published",
           title=f"Modelo {version.name} v{version.version} publicado",
           body="Ya se pueden generar alertas de riesgo en la institución.", link="/modelos")
    return deployment


def retire(db: Session, version: ModelVersion, organization_id: uuid.UUID, actor: uuid.UUID, reason: str) -> None:
    """Vuelta atrás (§16.3 paso 38, D44): la institución deja de usar el modelo. Las predicciones guardadas se
    conservan como historial; no se generan nuevas alertas hasta aprobar otra versión (o la misma de nuevo)."""
    current = active_deployment(db, organization_id)
    if current is None or current.model_version_id != version.id:
        raise AppError(409, "conflict", "Esta versión no está publicada en la institución.")
    current.status, current.retired_at = "retired", datetime.now(UTC)
    current.note = f"{current.note or ''} | Retirado: {reason}".strip(" |")
    record(db, action="model.retired", resource="model", resource_id=version.id, actor_id=actor,
           organization_id=organization_id, details={"model": version.name, "version": version.version, "reason": reason})
    staff = db.scalars(select(User.id).where(User.organization_id == organization_id, User.status == "active",
                                             User.roles.any(Role.code.in_(["ml_engineer", "admin", "coordinador"]))))
    notify(db, list(staff), organization_id=organization_id, kind="model.retired",
           title=f"Modelo {version.name} v{version.version} retirado",
           body=f"Motivo: {reason}. No se generarán alertas nuevas hasta aprobar otra versión.", link="/modelos")


def features_for(db: Session, enrollment: Enrollment, t: datetime) -> tuple[list[float], list[list[float]]]:
    """Variables de una matrícula en el instante t, desde la base (mismo cálculo que en el entrenamiento)."""
    offering: CourseOffering = enrollment.offering
    ctx = EnrollmentContext(starts_on=offering.starts_on, ends_on=offering.ends_on, level=offering.course.level,
                            required_ids=required_activity_ids(db, offering.course_id))
    events = [
        EventRec(e.occurred_at, e.event_type, e.duration_seconds, e.activity_id)
        for e in db.scalars(select(LearningEvent).where(LearningEvent.student_id == enrollment.student_id,
                                                        LearningEvent.offering_id == offering.id))
    ]
    assessments = []
    for a in db.scalars(select(Assessment).where(Assessment.offering_id == offering.id)):
        attempts = list(db.scalars(select(AssessmentAttempt).where(
            AssessmentAttempt.assessment_id == a.id, AssessmentAttempt.student_id == enrollment.student_id
        ).order_by(AssessmentAttempt.attempt_no)))
        graded = [x for x in attempts if x.score is not None]
        best = max(graded, key=lambda x: x.score) if graded else None
        first = attempts[0] if attempts else None
        assessments.append(AssessmentRec(
            due_at=a.due_at, submitted_at=first.submitted_at if first else None, late=bool(first and first.late),
            graded_at=best.graded_at if best else None, score_ratio=(best.score / a.max_score) if best else None,
        ))
    return compute(ctx, events, assessments, t)


def risk_level(score: float, threshold: float) -> str:
    if score >= threshold:
        return "alto"
    return "medio" if score >= threshold * 0.6 else "bajo"


def score_enrollments(db: Session, organization_id: uuid.UUID, enrollments: list[Enrollment],
                      actor_id: uuid.UUID | None) -> list[Prediction]:
    """Predice el riesgo de las matrículas activas con el modelo publicado en la institución."""
    deployment = active_deployment(db, organization_id)
    if deployment is None:
        raise AppError(409, "no_model", "No hay un modelo aprobado para esta institución. Un administrador debe publicarlo.")
    version = deployment.model_version
    model = load_model(version.artifact_path)
    now = datetime.now(UTC)
    started = time.perf_counter()
    created = []
    for enrollment in enrollments:
        if enrollment.status != "active":
            continue  # quien completó o se retiró no recibe alerta
        tabular, sequence = features_for(db, enrollment, now)
        score = float(model.predict(tabular, sequence)[0])
        factors = [f.__dict__ for f in model.explain(tabular, sequence)] if score >= model.threshold * 0.6 else []
        prediction = Prediction(
            organization_id=organization_id, enrollment_id=enrollment.id, student_id=enrollment.student_id,
            offering_id=enrollment.offering_id, model_version_id=version.id, score=round(score, 4),
            risk_level=risk_level(score, model.threshold), factors=factors,
            feature_schema_version=FEATURE_SCHEMA_VERSION, created_at=now,
        )
        db.add(prediction)
        created.append(prediction)
    elapsed_ms = (time.perf_counter() - started) * 1000
    LAST_RUN[organization_id] = {"at": now, "count": len(created),
                                 "latency_ms": round(elapsed_ms / max(len(created), 1), 2), "version": version.version}
    by_offering: dict = {}
    for p in created:
        if p.risk_level == "alto":
            by_offering[p.offering_id] = by_offering.get(p.offering_id, 0) + 1
    for offering_id, count in by_offering.items():
        offering = db.get(CourseOffering, offering_id)
        notify(db, [offering.instructor_id], organization_id=organization_id, kind="risk.alerts",
               title=f"{count} alerta{'s' if count > 1 else ''} de riesgo en {offering.course.title}",
               body="Revísalas y márcalas como atendidas o descártalas con un motivo.", link=f"/cursos/{offering_id}")
    record(db, action="predictions.generated", resource="model", resource_id=version.id, actor_id=actor_id,
           organization_id=organization_id,
           details={"count": len(created), "alto": sum(p.risk_level == "alto" for p in created)})
    db.flush()
    return created


def latest_predictions(db: Session, offering_id: uuid.UUID) -> dict[uuid.UUID, Prediction]:
    """Última predicción por matrícula de la oferta."""
    latest: dict[uuid.UUID, Prediction] = {}
    for p in db.scalars(select(Prediction).where(Prediction.offering_id == offering_id).order_by(Prediction.created_at)):
        latest[p.enrollment_id] = p
    return latest

