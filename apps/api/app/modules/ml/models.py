"""Dominio AI Platform (§6.3, §7.1): versiones de modelo, despliegues por institución y predicciones."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, JsonType, UTCDateTime, UUIDPk, utcnow


class ModelVersion(UUIDPk, Base):
    """Versión registrada desde ml/registry (model card + pesos). Es de plataforma: la usan varias instituciones."""

    __tablename__ = "model_versions"
    __table_args__ = (UniqueConstraint("name", "version", name="uq_model_versions_name_version"),)

    name: Mapped[str] = mapped_column(String(64))
    version: Mapped[str] = mapped_column(String(32))
    kind: Mapped[str] = mapped_column(String(32))
    task: Mapped[str] = mapped_column(String(64))
    artifact_path: Mapped[str] = mapped_column(String(255))  # relativo a la raíz del repositorio
    dataset_version: Mapped[str] = mapped_column(String(64))
    threshold: Mapped[float]
    card: Mapped[dict] = mapped_column(JsonType)
    registered_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class ModelDeployment(UUIDPk, Base):
    """Aprobación de una versión para una institución (§9.6 pasos 17-19). Solo una activa por institución."""

    __tablename__ = "model_deployments"
    __table_args__ = (
        CheckConstraint("status IN ('published', 'retired')", name="status"),
        Index("ix_model_deployments_org_status", "organization_id", "status"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    model_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("model_versions.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(16), default="published")
    approved_by: Mapped[uuid.UUID] = mapped_column(Uuid)
    approved_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    retired_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    note: Mapped[str | None] = mapped_column(Text)

    model_version: Mapped[ModelVersion] = relationship(lazy="joined")


class Prediction(UUIDPk, Base):
    """Resultado de inferencia (§9.7). Es una estimación de apoyo: el docente la revisa (§9.8)."""

    __tablename__ = "predictions"
    __table_args__ = (
        Index("ix_predictions_offering_created", "offering_id", "created_at"),
        CheckConstraint("score >= 0 AND score <= 1", name="score"),
        CheckConstraint("review_status IN ('pendiente', 'atendida', 'descartada')", name="review_status"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    enrollment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("enrollments.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    offering_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    model_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("model_versions.id", ondelete="RESTRICT"))
    task: Mapped[str] = mapped_column(String(32), default="dropout_risk")
    score: Mapped[float]
    risk_level: Mapped[str] = mapped_column(String(8))  # alto, medio, bajo
    factors: Mapped[list | None] = mapped_column(JsonType)
    feature_schema_version: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    review_status: Mapped[str] = mapped_column(String(12), default="pendiente")
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    reviewed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    review_note: Mapped[str | None] = mapped_column(Text)

    model_version: Mapped[ModelVersion] = relationship(lazy="joined")
