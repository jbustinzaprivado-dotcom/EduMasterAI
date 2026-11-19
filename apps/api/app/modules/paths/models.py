"""Planes y rutas de aprendizaje (§4.2): secuencia de cursos con objetivo, competencias y prerrequisitos."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, Float, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, JsonType, Timestamps, UTCDateTime, UUIDPk, utcnow
from app.modules.academic.models import Course
from app.modules.identity.models import User


class LearningPath(UUIDPk, Timestamps, Base):
    __tablename__ = "learning_paths"
    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_learning_paths_org_code"),
        CheckConstraint("status IN ('draft', 'published', 'archived')", name="status"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), index=True)
    code: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(160))
    objective: Mapped[str] = mapped_column(Text)
    # Competencias como etiquetas hasta que exista el catálogo jerárquico de §4.9 (decisión D32).
    competencies: Mapped[list] = mapped_column(JsonType, default=list)
    target_weeks: Mapped[int] = mapped_column(Integer, default=12)
    status: Mapped[str] = mapped_column(String(12), default="draft")
    version: Mapped[int] = mapped_column(Integer, default=1)  # sube con cada cambio después de publicar
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid)

    steps: Mapped[list["PathStep"]] = relationship(
        back_populates="path", order_by="PathStep.position", cascade="all, delete-orphan", lazy="selectin"
    )


class PathStep(UUIDPk, Base):
    """Etapa de la ruta. Cada etapa exige completar las anteriores (prerrequisito secuencial)."""

    __tablename__ = "learning_path_steps"

    path_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("learning_paths.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id", ondelete="RESTRICT"))
    # Criterio de logro: curso completado y, si se indica, nota final mínima (0-20).
    min_grade: Mapped[float | None] = mapped_column(Float)

    path: Mapped[LearningPath] = relationship(back_populates="steps")
    course: Mapped[Course] = relationship(lazy="joined")


class PathAssignment(UUIDPk, Base):
    """Asignación de una ruta a un estudiante (individual o por cohorte), con fecha objetivo y excepciones."""

    __tablename__ = "learning_path_assignments"
    __table_args__ = (CheckConstraint("status IN ('active', 'completed', 'cancelled')", name="status"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    path_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("learning_paths.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    assigned_by: Mapped[uuid.UUID] = mapped_column(Uuid)
    assigned_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    source: Mapped[str] = mapped_column(String(80))  # "individual" o "cohorte <grupo>"
    target_date: Mapped[datetime | None] = mapped_column(UTCDateTime)
    status: Mapped[str] = mapped_column(String(12), default="active")
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    # Excepciones autorizadas (§4.2): [{step_id, reason, granted_by, granted_at}]
    exceptions: Mapped[list] = mapped_column(JsonType, default=list)

    path: Mapped[LearningPath] = relationship(lazy="joined")
    student: Mapped[User] = relationship(lazy="joined")
