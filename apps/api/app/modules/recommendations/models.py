"""Dominio Recommendation (§6.3, §4.11): recomendaciones, su estado y la retroalimentación del usuario."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, Float, ForeignKey, Index, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UTCDateTime, UUIDPk, utcnow


# Tipos de sugerencia del motor (D27 y D55). Al agregar uno, la migración actualiza la restricción.
KINDS = ("siguiente_actividad", "entrega_proxima", "reforzar", "retomar",
         "vencida", "mejorar_nota", "competencia", "certificado", "ruta", "anuncio")


class Recommendation(UUIDPk, Base):
    __tablename__ = "recommendations"
    __table_args__ = (
        # Una recomendación por tipo y objetivo en cada matrícula: al refrescar se actualiza, no se duplica.
        UniqueConstraint("enrollment_id", "kind", "target_id", name="uq_recommendations_enrollment_kind_target"),
        CheckConstraint("status IN ('nueva', 'aceptada', 'descartada', 'completada', 'expirada')", name="status"),
        CheckConstraint(f"kind IN ({', '.join(repr(k) for k in KINDS)})", name="kind"),
        Index("ix_recommendations_student_status", "student_id", "status"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    enrollment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("enrollments.id", ondelete="CASCADE"))
    student_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    offering_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    kind: Mapped[str] = mapped_column(String(24))
    target_type: Mapped[str] = mapped_column(String(16))  # activity | assessment | skill | path | post | offering
    target_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    title: Mapped[str] = mapped_column(String(200))
    reason: Mapped[str] = mapped_column(Text)  # por qué se sugiere (§4.5: explicación obligatoria)
    expected_impact: Mapped[str] = mapped_column(String(160))
    priority: Mapped[float] = mapped_column(Float)
    priority_reason: Mapped[str] = mapped_column(String(160), default="")  # por qué va en ese lugar (D55)
    source: Mapped[str] = mapped_column(String(64))  # motor y versión que la generó
    status: Mapped[str] = mapped_column(String(12), default="nueva")
    useful: Mapped[bool | None] = mapped_column(Boolean)
    feedback_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    resolution_note: Mapped[str | None] = mapped_column(String(200))  # por qué se cerró (completada / expirada)
