"""Endpoints de sesión: login, renovación, cierre y perfil (§10.1, §11.1)."""

from datetime import UTC, datetime

from fastapi import APIRouter, Cookie, Response

from app.api.deps import DB, CurrentPrincipal
from app.core.config import get_settings
from app.core.context import client_ip
from app.core.errors import AppError
from app.core.rate_limit import login_limiter
from app.modules.audit.service import record
from app.modules.identity import service
from app.modules.identity.models import User
from app.modules.identity.schemas import LoginIn, MeOut, TokenOut

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "edumaster_refresh"
_COOKIE_PATH = "/api/v1/auth"  # la cookie solo viaja a las rutas de sesión


def _set_refresh_cookie(response: Response, raw: str) -> None:
    settings = get_settings()
    response.set_cookie(
        REFRESH_COOKIE,
        raw,
        max_age=settings.refresh_token_days * 86400,
        httponly=True,  # JavaScript no puede leerla (protege contra XSS)
        secure=settings.cookie_secure,
        samesite="strict",  # no viaja desde otros sitios (protege contra CSRF)
        path=_COOKIE_PATH,
    )


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, response: Response, db: DB) -> TokenOut:
    if not login_limiter.allow(client_ip.get() or "desconocida"):
        raise AppError(429, "too_many_requests", "Demasiados intentos. Espera un minuto.")

    user = service.authenticate(db, body.organization_code, body.email, body.password)
    if user is None:
        record(db, action="auth.login_failed", resource="session",
               details={"organization_code": body.organization_code, "email": service.normalize_email(body.email)})
        db.commit()
        # Mensaje genérico: no revela si falló la institución, el correo o la contraseña.
        raise AppError(401, "invalid_credentials", "Institución, correo o contraseña incorrectos.")

    user.last_login_at = datetime.now(UTC)
    access, expires_in, raw = service.issue_session(db, user)
    record(db, action="auth.login", resource="session", actor_id=user.id, organization_id=user.organization_id)
    db.commit()
    _set_refresh_cookie(response, raw)
    return TokenOut(access_token=access, expires_in=expires_in, user=service.me_out(user))


@router.post("/refresh", response_model=TokenOut)
def refresh(response: Response, db: DB, edumaster_refresh: str | None = Cookie(default=None)) -> TokenOut:
    if not edumaster_refresh:
        raise AppError(401, "unauthorized", "No hay sesión activa.")
    user, access, expires_in, raw = service.rotate(db, edumaster_refresh)
    _set_refresh_cookie(response, raw)
    return TokenOut(access_token=access, expires_in=expires_in, user=service.me_out(user))


@router.post("/logout", status_code=204)
def logout(response: Response, db: DB, edumaster_refresh: str | None = Cookie(default=None)) -> Response:
    if edumaster_refresh:
        token = service.family_of(db, edumaster_refresh)
        if token is not None:
            service.revoke_family(db, token.family_id)
            user = db.get(User, token.user_id)
            record(db, action="auth.logout", resource="session", actor_id=token.user_id,
                   organization_id=user.organization_id if user else None)
            db.commit()
    response.status_code = 204
    response.delete_cookie(REFRESH_COOKIE, path=_COOKIE_PATH)
    return response


@router.get("/me", response_model=MeOut)
def me(principal: CurrentPrincipal) -> MeOut:
    return service.me_out(principal.user)
