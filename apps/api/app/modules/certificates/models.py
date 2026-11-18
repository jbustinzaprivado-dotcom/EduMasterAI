"""Dominio Certification (§6.3, §4.7): certificados con folio único y código de verificación."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, Float, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UTCDateTime, UUIDPk, utcnow
from app.modules.academic.models import Enrollment


class Certificate(UUIDPk, Base):
    __tablename__ = "certificates"
    __table_args__ = (
        CheckConstraint("status IN ('emitido', 'anulado')", name="status"),
        Index("ix_certificates_enrollment_status", "enrollment_id", "status"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    enrollment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("enrollments.id", ondelete="RESTRICT"))
    student_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    offering_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    folio: Mapped[str] = mapped_column(String(48), unique=True)
    # Código público corto para verificar (§4.7). No revela ids internos.
    verification_code: Mapped[str] = mapped_column(String(16), unique=True)
    status: Mapped[str] = mapped_column(String(12), default="emitido")
    final_grade: Mapped[float | None] = mapped_column(Float)
    issued_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    issued_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)  # None = emisión automática del sistema
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    revoked_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    revoke_reason: Mapped[str | None] = mapped_column(Text)
    replaces_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)  # reemisión

    enrollment: Mapped[Enrollment] = relationship(lazy="joined")
