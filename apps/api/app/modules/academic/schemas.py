"""Contratos de la API académica (§10)."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field, field_validator

Level = Literal["basico", "intermedio", "avanzado"]
ActivityKind = Literal["lectura", "video", "practica"]
AssessmentKind = Literal["opcion_multiple", "verdadero_falso", "respuesta_corta", "archivo", "practica"]

# Eventos que el estudiante puede enviar. assessment_submitted lo genera el sistema al entregar.
CLIENT_EVENT_TYPES = ("session_started", "lesson_viewed", "activity_started", "activity_completed")


class ActivityIn(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    kind: ActivityKind = "lectura"
    estimated_minutes: int = Field(default=15, ge=1, le=600)
    required: bool = True


class UnitIn(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    activities: list[ActivityIn] = Field(default_factory=list, max_length=50)


class CourseIn(BaseModel):
    code: str = Field(min_length=2, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")
    title: str = Field(min_length=3, max_length=160)
    description: str = Field(default="", max_length=4000)
    level: Level = "basico"
    units: list[UnitIn] = Field(default_factory=list, max_length=30)

    @field_validator("code")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()


class CoursePatch(BaseModel):
    status: Literal["draft", "published", "archived"]


class ActivityOut(BaseModel):
    id: uuid.UUID
    position: int
    title: str
    kind: str
    estimated_minutes: int
    required: bool


class UnitOut(BaseModel):
    id: uuid.UUID
    position: int
    title: str
    activities: list[ActivityOut]


class CourseOut(BaseModel):
    id: uuid.UUID
    code: str
    title: str
    description: str
    level: str
    status: str
    unit_count: int
    activity_count: int
    offering_count: int
    units: list[UnitOut] | None = None


class OfferingIn(BaseModel):
    course_id: uuid.UUID
    instructor_id: uuid.UUID
    period: str = Field(min_length=3, max_length=16)
    cohort: str = Field(min_length=2, max_length=64)
    starts_on: AwareDatetime  # ISO-8601 con zona (§10.1)
    ends_on: AwareDatetime


class MyEnrollment(BaseModel):
    id: uuid.UUID
    status: str
    progress: float
    completed_activity_ids: list[uuid.UUID]


class OfferingOut(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    course_code: str
    course_title: str
    course_level: str
    instructor_id: uuid.UUID
    instructor_name: str
    period: str
    cohort: str
    starts_on: datetime
    ends_on: datetime
    status: str
    enrolled: int
    completed: int
    avg_progress: float | None
    my_enrollment: MyEnrollment | None = None
    can_manage: bool = False
    units: list[UnitOut] | None = None


class EnrollIn(BaseModel):
    student_ids: list[uuid.UUID] = Field(min_length=1, max_length=500)


class RosterRow(BaseModel):
    enrollment_id: uuid.UUID
    student_id: uuid.UUID
    student_name: str
    student_email: str
    status: str
    progress: float
    last_activity_at: datetime | None
    grade: float | None  # promedio ponderado oficial en escala 0-20 de lo ya calificado
    graded_weight: float


class EventIn(BaseModel):
    event_id: uuid.UUID
    offering_id: uuid.UUID
    activity_id: uuid.UUID | None = None
    event_type: Literal["session_started", "lesson_viewed", "activity_started", "activity_completed"]
    occurred_at: AwareDatetime | None = None
    duration_seconds: int = Field(default=0, ge=0, le=14400)
    source: Literal["web", "mobile"] = "web"


class EventOut(BaseModel):
    event_id: uuid.UUID
    duplicate: bool
    progress: float
    enrollment_status: str


class AssessmentIn(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    kind: AssessmentKind
    instructions: str = Field(default="", max_length=4000)
    max_score: float = Field(default=20, gt=0, le=1000)
    weight: float = Field(default=0.25, gt=0, le=1)
    due_at: AwareDatetime
    max_attempts: int = Field(default=1, ge=1, le=10)


class MyAttempt(BaseModel):
    attempts: int
    last_submitted_at: datetime | None
    best_score: float | None
    feedback: str | None


class AssessmentOut(BaseModel):
    id: uuid.UUID
    offering_id: uuid.UUID
    course_title: str
    cohort: str
    title: str
    kind: str
    instructions: str
    max_score: float
    weight: float
    due_at: datetime
    max_attempts: int
    submissions: int | None = None  # vista docente
    graded: int | None = None
    mine: MyAttempt | None = None  # vista estudiante
    can_manage: bool = False


class SubmissionIn(BaseModel):
    answer: str = Field(min_length=1, max_length=8000)


class AttemptOut(BaseModel):
    id: uuid.UUID
    assessment_id: uuid.UUID
    student_id: uuid.UUID
    student_name: str
    attempt_no: int
    answer: str
    submitted_at: datetime
    late: bool
    score: float | None
    feedback: str | None
    graded_at: datetime | None


class GradeIn(BaseModel):
    score: float = Field(ge=0)
    feedback: str | None = Field(default=None, max_length=4000)
