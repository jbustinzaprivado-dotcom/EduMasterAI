"""Reglas de negocio de identidad: sesiones, usuarios y sincronización del catálogo."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import (
    create_access_token,
    dummy_verify,
    fingerprint,
    new_refresh_token,
    verify_password,
)
from app.modules.audit.service import record
from app.modules.identity.catalog import PERMISSIONS, ROLES
from app.modules.identity.models import Organization, Permission, RefreshToken, Role, User
from app.modules.identity.schemas import MeOut, OrganizationOut, UserOut


def normalize_email(email: str) -> str:
    return email.strip().lower()


# ---------- catálogo ----------

def sync_catalog(db: Session) -> None:
    """Crea o actualiza roles y permisos según catalog.py. Es idempotente."""
    perms = {p.code: p for p in db.scalars(select(Permission))}
    for code, description in PERMISSIONS.items():
        if code not in perms:
            perms[code] = Permission(code=code, description=description)
            db.add(perms[code])
        else:
            perms[code].description = description

    roles = {r.code: r for r in db.scalars(select(Role))}
    for code, (name, description, perm_codes) in ROLES.items():
        role = roles.get(code) or Role(code=code, name=name, description=description)
        role.name, role.description = name, description
        role.permissions = [perms[c] for c in perm_codes]
        db.add(role)
    db.commit()


def roles_by_code(db: Session, codes: list[str]) -> list[Role]:
    found = list(db.scalars(select(Role).where(Role.code.in_(codes))))
    missing = set(codes) - {r.code for r in found}
    if missing:
        raise AppError(422, "validation_error", "Roles inexistentes.", sorted(missing))
    return found


# ---------- sesiones ----------

def authenticate(db: Session, org_code: str, email: str, password: str) -> User | None:
    user = db.scalar(
        select(User)
        .join(Organization)
        .where(Organization.code == org_code, User.email == normalize_email(email))
    )
    if user is None:
        dummy_verify(password)  # mismo tiempo de respuesta exista o no el correo
        return None
    if not verify_password(password, user.password_hash):
        return None
    if user.status != "active" or user.organization.status != "active":
        return None
    return user


def issue_session(db: Session, user: User, family_id: uuid.UUID | None = None) -> tuple[str, int, str]:
    access, expires_in = create_access_token(user.id, user.organization_id, user.role_codes)
    raw = new_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            family_id=family_id or uuid.uuid4(),
            token_hash=fingerprint(raw),
            expires_at=datetime.now(UTC) + timedelta(days=get_settings().refresh_token_days),
        )
    )
    return access, expires_in, raw


def revoke_family(db: Session, family_id: uuid.UUID) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def rotate(db: Session, raw: str) -> tuple[User, str, int, str]:
    """Cambia un token de renovación por uno nuevo. Si alguien reutiliza uno ya usado, se asume
    robo y se revoca toda la familia (la persona deberá iniciar sesión otra vez)."""
    invalid = AppError(401, "unauthorized", "La sesión expiró. Inicia sesión otra vez.")
    token = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == fingerprint(raw)))
    if token is None:
        raise invalid
    user = db.get(User, token.user_id)
    if token.revoked_at is not None:
        revoke_family(db, token.family_id)
        record(db, action="auth.refresh_reuse", resource="session", resource_id=token.family_id,
               actor_id=token.user_id, organization_id=user.organization_id if user else None)
        db.commit()
        raise invalid
    if _aware(token.expires_at) <= datetime.now(UTC) or user is None or user.status != "active":
        raise invalid

    token.revoked_at = datetime.now(UTC)
    access, expires_in, new_raw = issue_session(db, user, family_id=token.family_id)
    db.commit()
    return user, access, expires_in, new_raw


def family_of(db: Session, raw: str) -> RefreshToken | None:
    return db.scalar(select(RefreshToken).where(RefreshToken.token_hash == fingerprint(raw)))


# ---------- serialización ----------

def me_out(user: User) -> MeOut:
    return MeOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        roles=user.role_codes,
        permissions=sorted(user.permission_codes),
        organization=OrganizationOut.model_validate(user.organization),
        must_change_password=user.must_change_password,
    )


def user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        organization_id=user.organization_id,
        organization_code=user.organization.code,
        email=user.email,
        full_name=user.full_name,
        status=user.status,
        roles=user.role_codes,
        last_login_at=user.last_login_at,
        region=user.region,
        created_at=user.created_at,
    )
