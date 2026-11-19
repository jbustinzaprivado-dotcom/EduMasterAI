"""Endurecimiento HTTP (§11, Fase 7, decisión D40).

- Cabeceras de seguridad en todas las respuestas (CSP, anti-clickjacking, nosniff, HSTS con HTTPS).
- Límite de tamaño del cuerpo: una petición enorme se rechaza antes de leerla (413).
- Límite general de peticiones por IP y minuto en /api (429 con Retry-After); el login tiene el suyo, más estricto.
"""

from __future__ import annotations

from fastapi.responses import JSONResponse
from starlette.requests import Request

from app.core.config import get_settings
from app.core.rate_limit import SlidingWindowLimiter

# La web solo carga código propio; las fuentes vienen de Google Fonts (index.html).
CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",  # React usa style= en línea
    "font-src 'self' https://fonts.gstatic.com",
    "img-src 'self' data: blob:",
    "connect-src 'self'",
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "object-src 'none'",
])

BASE_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
    "Cross-Origin-Opener-Policy": "same-origin",
}

# Swagger UI (/api/docs) carga sus scripts desde un CDN: esa página no lleva la CSP estricta.
_NO_CSP = ("/api/docs", "/api/v1/openapi.json")

_settings = get_settings()
api_limiter = SlidingWindowLimiter(max_hits=_settings.api_rate_limit, window_seconds=60)


def _error(status: int, code: str, message: str, cid: str, headers: dict | None = None) -> JSONResponse:
    body = {"code": code, "message": message, "details": None, "correlation_id": cid}
    return JSONResponse(body, status, headers=headers)


def precheck(request: Request, ip: str | None, cid: str) -> JSONResponse | None:
    """Rechazos baratos antes de ejecutar el endpoint. Devuelve la respuesta de error o None."""
    path = request.url.path
    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > _settings.max_body_bytes:
        mb = _settings.max_body_bytes / 1_000_000
        return _error(413, "payload_too_large", f"La petición supera el máximo de {mb:g} MB.", cid)
    # Health checks y el flujo de notificaciones quedan fuera: los consultan monitores y reconexiones.
    if path.startswith("/api/") and not path.startswith(("/api/v1/health", "/api/v1/notifications/stream")):
        if not api_limiter.allow(ip or "desconocida"):
            return _error(429, "rate_limited", "Demasiadas peticiones. Espera un momento e inténtalo de nuevo.", cid,
                          {"Retry-After": "60"})
    return None


def apply_headers(request: Request, response) -> None:
    for k, v in BASE_HEADERS.items():
        response.headers.setdefault(k, v)
    if not request.url.path.startswith(_NO_CSP):
        response.headers.setdefault("Content-Security-Policy", CSP)
    if _settings.cookie_secure:  # solo detrás de HTTPS (túnel de Cloudflare)
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")  # datos personales: el navegador no los guarda
