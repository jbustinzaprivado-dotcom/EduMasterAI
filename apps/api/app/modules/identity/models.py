"""Dominio Identity & Access (§6.3): instituciones, usuarios, roles, permisos y sesiones."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    String,
    Table,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamps, UTCDateTime, UUIDPk, utcnow

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", Uuid, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", Uuid, ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)

user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", Uuid, ForeignKey("roles.id", ondelete="RESTRICT"), primary_key=True),
)


class Organization(UUIDPk, Timestamps, Base):
    __tablename__ = "organizations"
    __table_args__ = (CheckConstraint("status IN ('active', 'suspended')", name="status"),)

    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(16), default="active")
    timezone: Mapped[str] = mapped_column(String(64), default="America/Lima")
    # La institución de plataforma aloja al superadministrador (decisión D09).
    is_platform: Mapped[bool] = mapped_column(Boolean, default=False)


class Permission(UUIDPk, Base):
    __tablename__ = "permissions"

    code: Mapped[str] = mapped_column(String(64), unique=True)
    description: Mapped[str] = mapped_column(String(200))


class Role(UUIDPk, Base):
    __tablename__ = "roles"

    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(String(240))
    permissions: Mapped[list[Permission]] = relationship(secondary=role_permissions, lazy="selectin")


class User(UUIDPk, Timestamps, Base):
    __tablename__ = "users"
    __table_args__ = (
        # §7.3: correo normalizado único por institución.
        UniqueConstraint("organization_id", "email", name="uq_users_org_email"),
        CheckConstraint("status IN ('active', 'disabled')", name="status"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), index=True)
    email: Mapped[str] = mapped_column(String(254))
    full_name: Mapped[str] = mapped_column(String(160))
    password_hash: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(16), default="active")
    last_login_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    organization: Mapped[Organization] = relationship(lazy="joined")
    roles: Mapped[list[Role]] = relationship(secondary=user_roles, lazy="selectin")

    @property
    def role_codes(self) -> list[str]:
        return sorted(r.code for r in self.roles)

    @property
    def permission_codes(self) -> set[str]:
        return {p.code for r in self.roles for p in r.permissions}


class RefreshToken(UUIDPk, Base):
    """Sesión renovable. Cada uso crea un token nuevo de la misma familia y revoca el anterior."""

    __tablename__ = "refresh_tokens"
    __table_args__ = (Index("ix_refresh_tokens_family", "family_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    family_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
