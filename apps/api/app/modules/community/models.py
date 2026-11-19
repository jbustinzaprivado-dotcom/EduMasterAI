"""Comunidad y colaboración (§4.8): espacios por curso, anuncios, debates, comentarios y moderación."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UTCDateTime, UUIDPk, utcnow
from app.modules.identity.models import User


class Post(UUIDPk, Base):
    __tablename__ = "community_posts"
    __table_args__ = (
        CheckConstraint("kind IN ('anuncio', 'debate')", name="kind"),
        Index("ix_community_posts_offering_created", "offering_id", "created_at"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    offering_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("course_offerings.id", ondelete="CASCADE"))
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    kind: Mapped[str] = mapped_column(String(12))
    title: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    hidden_reason: Mapped[str | None] = mapped_column(Text)
    hidden_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)

    author: Mapped[User] = relationship(lazy="joined")


class Comment(UUIDPk, Base):
    __tablename__ = "community_comments"
    __table_args__ = (Index("ix_community_comments_post_created", "post_id", "created_at"),)

    post_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("community_posts.id", ondelete="CASCADE"))
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    hidden_reason: Mapped[str | None] = mapped_column(Text)
    hidden_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)

    author: Mapped[User] = relationship(lazy="joined")


class Report(UUIDPk, Base):
    """Reporte de contenido por un miembro (§4.8: reportes de contenido y trazabilidad)."""

    __tablename__ = "community_reports"
    __table_args__ = (
        CheckConstraint("target_type IN ('post', 'comment')", name="target_type"),
        CheckConstraint("status IN ('abierto', 'resuelto')", name="status"),
        UniqueConstraint("target_id", "reporter_id", name="uq_community_reports_target_reporter"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    offering_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    target_type: Mapped[str] = mapped_column(String(8))
    target_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    reporter_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10), default="abierto")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    resolution: Mapped[str | None] = mapped_column(String(32))


class Mute(Base):
    """Silenciar las notificaciones de la comunidad de un curso (§4.8)."""

    __tablename__ = "community_mutes"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    offering_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("course_offerings.id", ondelete="CASCADE"), primary_key=True)
