"""Dominio Audit & Governance (§6.3, §11.1): bitácora transversal."""

import uuid
from datetime import datetime

from sqlalchemy import Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, JsonType, UTCDateTime, UUIDPk, utcnow


class AuditLog(UUIDPk, Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_org_occurred", "organization_id", "occurred_at"),)

    # Sin clave foránea a propósito: la bitácora debe sobrevivir aunque se borre lo auditado.
    organization_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    action: Mapped[str] = mapped_column(String(64))
    resource: Mapped[str] = mapped_column(String(64))
    resource_id: Mapped[str | None] = mapped_column(String(64))
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    ip: Mapped[str | None] = mapped_column(String(64))
    correlation_id: Mapped[str | None] = mapped_column(String(64))
    details: Mapped[dict | None] = mapped_column(JsonType)
