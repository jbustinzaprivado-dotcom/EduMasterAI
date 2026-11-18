"""Punto de entrada de la API de EduMaster.ai (monolito modular, §6.1)."""

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.core import errors
from app.core.config import get_settings
from app.core.context import client_ip, correlation_id
from app.core.database import SessionLocal
from app.core.logging import configure_logging
from app.modules.academic.router import router as academic_router
from app.modules.audit.router import router as audit_router
from app.modules.certificates.router import router as certificates_router
from app.modules.dashboard.router import router as dashboard_router
from app.modules.identity.router_admin import router as admin_router
from app.modules.identity.router_auth import router as auth_router
from app.modules.identity.service import sync_catalog
from app.modules.ml.router import router as ml_router
from app.modules.ml.service import sync_registry
from app.modules.notifications.router import router as notifications_router
from app.modules.recommendations.router import router as recommendations_router
from app.modules.system.router import router as system_router

log = logging.getLogger("edumaster.http")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    settings.validate_for_environment()
    with SessionLocal() as db:
        sync_catalog(db)  # roles y permisos siempre iguales a catalog.py
        sync_registry(db)  # versiones de modelo presentes en ml/registry
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_format)

    app = FastAPI(
        title="EduMaster.ai API",
        version="0.1.0",
        description="Plataforma de aprendizaje inteligente. Contrato OpenAPI v1 (§10.1).",
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/v1/openapi.json",
    )
    errors.install(app)

    @app.middleware("http")
    async def correlation(request: Request, call_next):
        cid = request.headers.get("X-Correlation-ID") or uuid.uuid4().hex
        correlation_id.set(cid[:64])
        # Detrás del túnel de Cloudflare todas las peticiones llegan desde 127.0.0.1 y la IP real viene
        # en CF-Connecting-IP. Solo se confía en esa cabecera si se activa (si no, cualquiera la falsifica).
        direct = request.client.host if request.client else None
        forwarded = request.headers.get("CF-Connecting-IP") if settings.trust_cloudflare_ip else None
        client_ip.set(forwarded or direct)
        start = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = cid[:64]
        if request.url.path.startswith("/api/"):
            log.info(
                "petición",
                extra={"extra_data": {
                    "method": request.method, "path": request.url.path, "status": response.status_code,
                    "ms": round((time.perf_counter() - start) * 1000, 1),
                }},
            )
        return response

    api = APIRouter(prefix="/api/v1")
    for router in (system_router, auth_router, admin_router, audit_router, dashboard_router, ml_router,
                   academic_router, recommendations_router,
                   certificates_router, notifications_router):
        api.include_router(router)
    app.include_router(api)

    _mount_web(app, settings.web_dist)
    return app


def _mount_web(app: FastAPI, dist) -> None:
    """Si la web está compilada, la API la sirve: una sola dirección pública para el túnel (D03)."""
    index = dist / "index.html"
    if not index.exists():
        return
    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise errors.not_found("Recurso")
        file = (dist / path).resolve()
        if path and file.is_file() and dist.resolve() in file.parents:
            return FileResponse(file)
        return FileResponse(index)  # rutas de React (SPA)


app = create_app()
