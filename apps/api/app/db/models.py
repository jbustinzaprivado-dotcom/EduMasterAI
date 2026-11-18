"""Importa todos los modelos para que Alembic y create_all los conozcan."""

from app.db.base import Base
from app.modules.academic.models import (
    Assessment,
    AssessmentAttempt,
    Course,
    CourseActivity,
    CourseOffering,
    CourseUnit,
    Enrollment,
    LearningEvent,
)
from app.modules.audit.models import AuditLog
from app.modules.identity.models import Organization, Permission, RefreshToken, Role, User
from app.modules.ml.models import ModelDeployment, ModelVersion, Prediction
from app.modules.recommendations.models import Recommendation

__all__ = [
    "Assessment", "AssessmentAttempt", "Course", "CourseActivity", "CourseOffering", "CourseUnit", "Enrollment",
    "LearningEvent", "Base", "AuditLog", "Organization", "Permission", "RefreshToken", "Role", "User",
    "ModelDeployment", "ModelVersion", "Prediction", "Recommendation",
]
