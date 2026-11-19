"""Entorno de Alembic: usa la misma URL de base de datos y los mismos modelos que la API."""

from alembic import context

from app.core.config import get_settings
from app.core.database import engine
from app.db.base import UTCDateTime
from app.db.models import Base

config = context.config
config.set_main_option("sqlalchemy.url", get_settings().database_url.replace("%", "%%"))
target_metadata = Base.metadata


def render_item(type_, obj, autogen_context):
    """UTCDateTime se escribe en las migraciones como DateTime con zona (las migraciones no importan la app)."""
    if type_ == "type" and isinstance(obj, UTCDateTime):
        return "sa.DateTime(timezone=True)"
    return False


def run_migrations_offline() -> None:
    context.configure(url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata,
                      literal_binds=True, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    with engine.connect() as connection:  # mismo motor que la API (crea la carpeta de SQLite si falta)
        if connection.dialect.name == "sqlite":
            # SQLite modifica tablas copiándolas ("batch"): con las FK activas, borrar la tabla vieja falla si hay
            # datos que la referencian. Se desactivan solo durante la migración (PostgreSQL no lo necesita).
            connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
            connection.commit()
        context.configure(connection=connection, target_metadata=target_metadata,
                          render_as_batch=connection.dialect.name == "sqlite", render_item=render_item)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
