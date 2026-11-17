"""Identificador de correlación de la petición en curso (§10.1, §12)."""

from contextvars import ContextVar

correlation_id: ContextVar[str] = ContextVar("correlation_id", default="-")
client_ip: ContextVar[str | None] = ContextVar("client_ip", default=None)
