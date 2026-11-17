"""Contraseñas y tokens (§10.1, §11, decisión D08).

- Contraseñas: PBKDF2-SHA256 de la librería estándar, con sal aleatoria por usuario.
- Token de acceso: JWT firmado (HS256) de vida corta; viaja en la cabecera Authorization.
- Token de renovación: cadena aleatoria; en la base solo se guarda su huella SHA-256.
"""

import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt

from app.core.config import get_settings

_ALGORITHM = "HS256"


def hash_password(password: str, iterations: int | None = None) -> str:
    iterations = iterations or get_settings().password_iterations
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt_hex, digest_hex = stored.split("$")
    except ValueError:
        return False
    if algo != "pbkdf2_sha256":
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations))
    return hmac.compare_digest(digest.hex(), digest_hex)


# Se usa para igualar el tiempo de respuesta cuando el usuario no existe (evita enumerar correos).
_DUMMY_HASH: str | None = None


def dummy_verify(password: str) -> None:
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = hash_password("contraseña-ficticia")
    verify_password(password, _DUMMY_HASH)


def create_access_token(user_id: uuid.UUID, organization_id: uuid.UUID, roles: list[str]) -> tuple[str, int]:
    settings = get_settings()
    now = datetime.now(UTC)
    expires = timedelta(minutes=settings.access_token_minutes)
    payload = {
        "sub": str(user_id),
        "org": str(organization_id),
        "roles": roles,
        "type": "access",
        "iat": now,
        "exp": now + expires,
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=_ALGORITHM), int(expires.total_seconds())


def decode_access_token(token: str) -> dict:
    """Lanza jwt.PyJWTError si la firma, el tipo o la expiración no son válidos."""
    payload = jwt.decode(token, get_settings().jwt_secret, algorithms=[_ALGORITHM])
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("tipo de token incorrecto")
    return payload


def new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
