"""Base declarativa y tipos comunes (§7.2: UUID internos, timestamps en UTC)."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, MetaData, TypeDecorator, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Nombres de restricciones estables: Alembic los necesita para comparar el esquema.
NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# JSONB en PostgreSQL (§7.2), JSON simple en SQLite para las pruebas.
JsonType = JSON().with_variant(JSONB(), "postgresql")


class UTCDateTime(TypeDecorator):
    """Fecha con zona horaria que siempre vuelve en UTC (§7.2). SQLite no guarda la zona: se la
    devuelve marcada como UTC para que la API nunca envíe horas ambiguas."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        # SQLite compara fechas como texto: se guardan todas en UTC sin zona para que el orden sea correcto.
        if value is not None and dialect.name == "sqlite" and value.tzinfo is not None:
            return value.astimezone(UTC).replace(tzinfo=None)
        return value

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)


class UUIDPk:
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)
