"""Conexión a la base de datos y sesión por petición."""

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings

# Los endpoints síncronos corren en un pool de 40 hilos (anyio). El pool de conexiones admite las mismas 40, para
# que con muchas personas a la vez la petición espere su turno de CPU y no un "QueuePool limit" (prueba de carga,
# D43). Si aun así no hay conexión en 10 s, se responde error rápido en vez de colgar al resto (degradación elegante).
POOL = {"pool_size": 20, "max_overflow": 20, "pool_timeout": 10}


def build_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        kwargs: dict = {"connect_args": {"check_same_thread": False}}
        if url in ("sqlite://", "sqlite:///:memory:"):
            kwargs["poolclass"] = StaticPool  # una sola conexión compartida para pruebas en memoria
        else:
            Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
            kwargs.update(POOL)
        engine = create_engine(url, **kwargs)

        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_conn, _record):  # SQLite no valida claves foráneas si no se le pide
            dbapi_conn.execute("PRAGMA foreign_keys=ON")

        return engine
    return create_engine(url, pool_pre_ping=True, **POOL)


engine = build_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
