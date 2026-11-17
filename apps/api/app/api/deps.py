"""Autenticación y autorización en el backend (§3: RBAC + aislamiento por institución)."""

import uuid
from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import AppError, forbidden
from app.core.security import decode_access_token
from app.modules.identity.models import User

DB = Annotated[Session, Depends(get_db)]
_bearer = HTTPBearer(auto_error=False)


@dataclass
class Principal:
    """Quién hace la petición y qué puede hacer."""

    user: User
    permissions: set[str]

    @property
    def is_global(self) -> bool:
        return "platform.global" in self.permissions

    @property
    def organization_id(self) -> uuid.UUID:
        return self.user.organization_id

    def can(self, permission: str) -> bool:
        return permission in self.permissions

    def can_see_org(self, organization_id: uuid.UUID | None) -> bool:
        return self.is_global or organization_id == self.organization_id


def _unauthorized(message: str = "Sesión no válida o expirada.") -> AppError:
    return AppError(401, "unauthorized", message)


def get_principal(
    db: DB, creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]
) -> Principal:
    if creds is None:
        raise _unauthorized("Falta el token de acceso.")
    try:
        payload = decode_access_token(creds.credentials)
        user_id = uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise _unauthorized() from None

    # Se vuelve a leer el usuario en cada petición: un usuario desactivado pierde acceso al instante.
    user = db.get(User, user_id)
    if user is None or user.status != "active" or user.organization.status != "active":
        raise _unauthorized()
    return Principal(user=user, permissions=user.permission_codes)


CurrentPrincipal = Annotated[Principal, Depends(get_principal)]


def require(*permissions: str):
    """Dependencia que exige todos los permisos indicados."""

    def checker(principal: CurrentPrincipal) -> Principal:
        if not all(principal.can(p) for p in permissions):
            raise forbidden()
        return principal

    return Depends(checker)
