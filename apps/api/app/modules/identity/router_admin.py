"""Administración de instituciones, usuarios y roles (§3, §4.13).

Regla de aislamiento: salvo el superadministrador, todo se filtra por la institución del usuario.
Un registro de otra institución responde 404, igual que uno inexistente.
"""

import uuid

from fastapi import APIRouter, Query
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import DB, Principal, require
from app.core.errors import AppError, forbidden, not_found
from app.core.security import hash_password
from app.modules.audit.service import record
from app.modules.identity import service
from app.modules.identity.catalog import GLOBAL_ROLES, ROLES
from app.modules.identity.models import Organization, RefreshToken, Role, User
from app.modules.identity.schemas import (
    OrganizationIn,
    OrganizationOut,
    Page,
    RoleOut,
    UserCreate,
    UserOut,
    UserUpdate,
)

router = APIRouter(tags=["administración"])


# ---------- instituciones ----------

@router.get("/organizations", response_model=list[OrganizationOut])
def list_organizations(db: DB, principal: Principal = require("org.read")) -> list[Organization]:
    query = select(Organization).order_by(Organization.is_platform.desc(), Organization.name)
    if not principal.is_global:
        query = query.where(Organization.id == principal.organization_id)
    return list(db.scalars(query))


@router.post("/organizations", response_model=OrganizationOut, status_code=201)
def create_organization(body: OrganizationIn, db: DB, principal: Principal = require("org.manage")) -> Organization:
    if db.scalar(select(Organization).where(Organization.code == body.code)):
        raise AppError(409, "conflict", "Ya existe una institución con ese código.")
    org = Organization(code=body.code, name=body.name, timezone=body.timezone)
    db.add(org)
    db.flush()
    record(db, action="org.created", resource="organization", resource_id=org.id,
           actor_id=principal.user.id, organization_id=org.id, details={"code": org.code})
    db.commit()
    return org


# ---------- roles ----------

@router.get("/roles", response_model=list[RoleOut])
def list_roles(db: DB, principal: Principal = require("role.read")) -> list[RoleOut]:
    order = list(ROLES)
    roles = sorted(db.scalars(select(Role)), key=lambda r: order.index(r.code) if r.code in order else 99)
    return [
        RoleOut(code=r.code, name=r.name, description=r.description,
                permissions=sorted(p.code for p in r.permissions))
        for r in roles
        if principal.is_global or r.code not in GLOBAL_ROLES
    ]


# ---------- usuarios ----------

def _get_visible_user(db: DB, principal: Principal, user_id: uuid.UUID) -> User:
    user = db.get(User, user_id)
    if user is None or not principal.can_see_org(user.organization_id):
        raise not_found("Usuario")
    return user


def _check_assignable(principal: Principal, roles: list[str]) -> None:
    if not principal.is_global and set(roles) & GLOBAL_ROLES:
        raise forbidden()


@router.get("/users", response_model=Page[UserOut])
def list_users(
    db: DB,
    principal: Principal = require("user.read"),
    q: str | None = Query(default=None, max_length=100),
    role: str | None = None,
    status: str | None = None,
    organization_id: uuid.UUID | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> Page[UserOut]:
    query = select(User)
    if principal.is_global:
        if organization_id:
            query = query.where(User.organization_id == organization_id)
    else:
        query = query.where(User.organization_id == principal.organization_id)
    if q:
        like = f"%{q.lower()}%"
        query = query.where(or_(func.lower(User.full_name).like(like), User.email.like(like)))
    if role:
        query = query.where(User.roles.any(Role.code == role))
    if status:
        query = query.where(User.status == status)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(query.order_by(User.full_name).offset((page - 1) * page_size).limit(page_size))
    return Page[UserOut](items=[service.user_out(u) for u in rows], total=total, page=page, page_size=page_size)


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(body: UserCreate, db: DB, principal: Principal = require("user.manage")) -> UserOut:
    org_id = body.organization_id or principal.organization_id
    if not principal.can_see_org(org_id):
        raise not_found("Institución")
    if db.get(Organization, org_id) is None:
        raise not_found("Institución")
    _check_assignable(principal, body.roles)

    user = User(
        organization_id=org_id,
        email=service.normalize_email(body.email),
        full_name=body.full_name.strip(),
        password_hash=hash_password(body.password),
        roles=service.roles_by_code(db, body.roles),
        region=body.region,
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise AppError(409, "conflict", "Ya existe un usuario con ese correo en la institución.") from None
    record(db, action="user.created", resource="user", resource_id=user.id, actor_id=principal.user.id,
           organization_id=org_id, details={"email": user.email, "roles": sorted(body.roles)})
    db.commit()
    db.refresh(user)
    return service.user_out(user)


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: uuid.UUID, body: UserUpdate, db: DB, principal: Principal = require("user.manage")) -> UserOut:
    user = _get_visible_user(db, principal, user_id)
    changes: dict = {}

    if body.full_name is not None and body.full_name.strip() != user.full_name:
        changes["full_name"] = [user.full_name, body.full_name.strip()]
        user.full_name = body.full_name.strip()

    if "region" in body.model_fields_set and body.region != user.region:
        changes["region"] = [user.region, body.region]
        user.region = body.region

    if body.status is not None and body.status != user.status:
        if user.id == principal.user.id:
            raise AppError(422, "validation_error", "No puedes desactivar tu propia cuenta.")
        changes["status"] = [user.status, body.status]
        user.status = body.status
        if body.status == "disabled":
            # Cierra sus sesiones abiertas: la desactivación es inmediata.
            for family in set(db.scalars(select(RefreshToken.family_id).where(RefreshToken.user_id == user.id))):
                service.revoke_family(db, family)

    if body.roles is not None and set(body.roles) != set(user.role_codes):
        _check_assignable(principal, body.roles)
        if not principal.is_global and set(user.role_codes) & GLOBAL_ROLES:
            raise forbidden()
        if user.id == principal.user.id and "user.manage" not in {
            p.code for r in service.roles_by_code(db, body.roles) for p in r.permissions
        }:
            raise AppError(422, "validation_error", "No puedes quitarte el permiso de administrar usuarios.")
        changes["roles"] = [user.role_codes, sorted(body.roles)]
        user.roles = service.roles_by_code(db, body.roles)

    if changes:
        action = "user.roles_changed" if set(changes) == {"roles"} else "user.updated"
        record(db, action=action, resource="user", resource_id=user.id, actor_id=principal.user.id,
               organization_id=user.organization_id, details=changes)
        db.commit()
        db.refresh(user)
    return service.user_out(user)
