"""Dominios Academic Core y Learning Tracking (§6.3, §7.1).

- Curso: catálogo con unidades y actividades (contenido).
- Oferta: edición concreta del curso (periodo, docente, cohorte). La cohorte se modela como el grupo de la
  oferta en esta versión (decisión D15).
- Matrícula: estudiante en una oferta, con progreso calculado desde los eventos.
- Evaluación e intentos: la nota oficial la registra el docente; nunca la IA (§4.6).
- Evento de aprendizaje: hecho idempotente (event_id único) que alimenta progreso y analítica (§7.4).
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, JsonType, Timestamps, UTCDateTime, UUIDPk, utcnow
from app.modules.identity.models import User


class Course(UUIDPk, Timestamps, Base):
    __tablename__ = "courses"
    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_courses_org_code"),
        CheckConstraint("status IN ('draft', 'published', 'archived')", name="status"),
        CheckConstraint("level IN ('basico', 'intermedio', 'avanzado')", name="level"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), index=True)
    code: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    level: Mapped[str] = mapped_column(String(16), default="basico")
    status: Mapped[str] = mapped_column(String(16), default="draft")

    units: Mapped[list["CourseUnit"]] = relationship(
        back_populates="course", order_by="CourseUnit.position", cascade="all, delete-orphan", lazy="selectin"
    )


class CourseUnit(UUIDPk, Base):
    __tablename__ = "course_units"

    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(160))

    course: Mapped[Course] = relationship(back_populates="units")
    activities: Mapped[list["CourseActivity"]] = relationship(
        back_populates="unit", order_by="CourseActivity.position", cascade="all, delete-orphan", lazy="selectin"
    )


class CourseActivity(UUIDPk, Base):
    __tablename__ = "course_activities"
    __table_args__ = (CheckConstraint("kind IN ('lectura', 'video', 'practica')", name="kind"),)

    unit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("course_units.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(160))
    kind: Mapped[str] = mapped_column(String(16), default="lectura")
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=15)
    required: Mapped[bool] = mapped_column(Boolean, default=True)

    unit: Mapped[CourseUnit] = relationship(back_populates="activities")


class CourseOffering(UUIDPk, Timestamps, Base):
    __tablename__ = "course_offerings"
    __table_args__ = (CheckConstraint("status IN ('planned', 'active', 'closed')", name="status"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), index=True)
    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id", ondelete="RESTRICT"), index=True)
    instructor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    period: Mapped[str] = mapped_column(String(16))
    cohort: Mapped[str] = mapped_column(String(64))
    starts_on: Mapped[datetime] = mapped_column(UTCDateTime)
    ends_on: Mapped[datetime] = mapped_column(UTCDateTime)
    status: Mapped[str] = mapped_column(String(16), default="active")

    course: Mapped[Course] = relationship(lazy="joined")
    instructor: Mapped[User] = relationship(lazy="joined")


class Enrollment(UUIDPk, Base):
    __tablename__ = "enrollments"
    __table_args__ = (
        UniqueConstraint("offering_id", "student_id", name="uq_enrollments_offering_student"),
        CheckConstraint("status IN ('active', 'completed', 'dropped')", name="status"),
        CheckConstraint("progress >= 0 AND progress <= 1", name="progress"),
        Index("ix_enrollments_student_offering", "student_id", "offering_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    offering_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("course_offerings.id", ondelete="CASCADE"))
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(16), default="active")
    progress: Mapped[float] = mapped_column(Float, default=0.0)  # actividades requeridas completadas / total
    enrolled_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    last_activity_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    offering: Mapped[CourseOffering] = relationship(lazy="joined")
    student: Mapped[User] = relationship(lazy="joined")


class Assessment(UUIDPk, Timestamps, Base):
    __tablename__ = "assessments"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('opcion_multiple', 'verdadero_falso', 'respuesta_corta', 'archivo', 'practica')", name="kind"
        ),
        CheckConstraint("max_score > 0", name="max_score"),
        CheckConstraint("weight > 0 AND weight <= 1", name="weight"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    offering_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("course_offerings.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    kind: Mapped[str] = mapped_column(String(24))
    instructions: Mapped[str] = mapped_column(Text, default="")
    max_score: Mapped[float] = mapped_column(Float, default=20.0)  # escala vigesimal peruana por defecto
    weight: Mapped[float] = mapped_column(Float, default=0.25)
    due_at: Mapped[datetime] = mapped_column(UTCDateTime)
    max_attempts: Mapped[int] = mapped_column(Integer, default=1)

    offering: Mapped[CourseOffering] = relationship(lazy="joined")


class AssessmentAttempt(UUIDPk, Base):
    __tablename__ = "assessment_attempts"
    __table_args__ = (
        UniqueConstraint("assessment_id", "student_id", "attempt_no", name="uq_attempts_assessment_student_no"),
    )

    assessment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assessments.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    attempt_no: Mapped[int] = mapped_column(Integer)
    answer: Mapped[str] = mapped_column(Text, default="")
    submitted_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    late: Mapped[bool] = mapped_column(Boolean, default=False)
    # Calificación oficial: la registra el docente (§4.6). Nula mientras no se califica.
    score: Mapped[float | None] = mapped_column(Float)
    feedback: Mapped[str | None] = mapped_column(Text)
    graded_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    graded_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    assessment: Mapped[Assessment] = relationship(lazy="joined")
    student: Mapped[User] = relationship(lazy="joined")


class LearningEvent(Base):
    """Evento de aprendizaje (§7.4). El event_id lo genera el cliente: reenviar el mismo evento no duplica."""

    __tablename__ = "learning_events"
    __table_args__ = (
        Index("ix_learning_events_org_occurred", "organization_id", "occurred_at"),
        Index("ix_learning_events_student_offering", "student_id", "offering_id"),
        CheckConstraint("duration_seconds >= 0 AND duration_seconds <= 14400", name="duration"),
    )

    event_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    offering_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("course_offerings.id", ondelete="CASCADE"))
    activity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    event_type: Mapped[str] = mapped_column(String(48))
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime)
    received_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str] = mapped_column(String(16), default="web")  # web, mobile, import, integration
    payload_schema_version: Mapped[int] = mapped_column(Integer, default=1)
    payload: Mapped[dict | None] = mapped_column(JsonType)
