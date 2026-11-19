"""Dominio de habilidades (§4.9, §7.1): catálogo jerárquico, vínculos curso/evaluación y validación docente."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, Float, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UTCDateTime, UUIDPk, utcnow

LEVELS = ["principiante", "elemental", "intermedio", "avanzado", "experto"]


class Skill(UUIDPk, Base):
    __tablename__ = "skills"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_skills_org_code"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), index=True)
    code: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    parent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("skills.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class CourseSkill(Base):
    """Competencia que desarrolla un curso. `position` enlaza la unidad del mismo orden (decisión D34)."""

    __tablename__ = "course_skills"

    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), primary_key=True)
    skill_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, default=1)
    weight: Mapped[float] = mapped_column(Float, default=1.0)

    skill: Mapped[Skill] = relationship(lazy="joined")


class AssessmentSkill(Base):
    """Competencias que evidencia una evaluación (rúbrica/nota oficial → evidencia)."""

    __tablename__ = "assessment_skills"

    assessment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assessments.id", ondelete="CASCADE"), primary_key=True)
    skill_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True)


class SkillValidation(UUIDPk, Base):
    """Nivel validado por el docente: es el oficial y se muestra separado del estimado (§4.9)."""

    __tablename__ = "skill_validations"
    __table_args__ = (CheckConstraint("level >= 1 AND level <= 5", name="level"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    skill_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("skills.id", ondelete="CASCADE"))
    level: Mapped[int] = mapped_column(Integer)  # 1 principiante … 5 experto
    note: Mapped[str] = mapped_column(Text)
    estimated_level_at_validation: Mapped[int | None] = mapped_column(Integer)
    validated_by: Mapped[uuid.UUID] = mapped_column(Uuid)
    validated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
