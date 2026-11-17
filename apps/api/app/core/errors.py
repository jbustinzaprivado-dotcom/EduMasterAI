"""Errores normalizados: code, message, details, correlation_id (§10.1)."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.context import correlation_id

log = logging.getLogger("edumaster.errors")


class AppError(Exception):
    def __init__(self, status: int, code: str, message: str, details: object = None):
        self.status, self.code, self.message, self.details = status, code, message, details


def not_found(resource: str) -> AppError:
    # Un recurso de otra institución responde igual que uno inexistente: no se revela que existe.
    return AppError(404, "not_found", f"{resource} no encontrado.")


def forbidden() -> AppError:
    return AppError(403, "forbidden", "No tienes permiso para esta acción.")


def _body(code: str, message: str, details: object = None) -> dict:
    return {"code": code, "message": message, "details": details, "correlation_id": correlation_id.get()}


_HTTP_CODES = {401: "unauthorized", 403: "forbidden", 404: "not_found", 405: "method_not_allowed"}


def install(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_req: Request, exc: AppError):
        headers = {"WWW-Authenticate": "Bearer"} if exc.status == 401 else None
        return JSONResponse(_body(exc.code, exc.message, exc.details), exc.status, headers=headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(_req: Request, exc: RequestValidationError):
        details = [
            {"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()
        ]
        return JSONResponse(_body("validation_error", "Datos inválidos.", details), 422)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_req: Request, exc: StarletteHTTPException):
        code = _HTTP_CODES.get(exc.status_code, "http_error")
        return JSONResponse(_body(code, str(exc.detail)), exc.status_code)

    @app.exception_handler(Exception)
    async def _unexpected(_req: Request, exc: Exception):
        log.exception("Error no controlado")
        return JSONResponse(_body("internal_error", "Error interno. Usa el correlation_id para rastrearlo."), 500)
