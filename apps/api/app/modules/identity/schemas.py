"""Contratos de la API de identidad (DTO separados del ORM, §6.4)."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


def _check_region(v: str | None) -> str | None:
    from app.modules.identity.regions import REGIONS

    if v in (None, ""):
        return None
    if v not in REGIONS:
        raise ValueError("Región no válida.")
    return v


class LoginIn(BaseModel):
    organization_code: str = Field(min_length=2, max_length=32)
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)

    @field_validator("organization_code")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.strip().upper()


class OrganizationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    status: str
    timezone: str
    is_platform: bool


class OrganizationIn(BaseModel):
    code: str = Field(min_length=2, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=3, max_length=160)
    timezone: str = "America/Lima"

    @field_validator("code")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()


class MeOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    roles: list[str]
    permissions: list[str]
    organization: OrganizationOut
    must_change_password: bool = False


class TokenOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: MeOut


class UserOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    organization_code: str
    email: str
    full_name: str
    status: str
    roles: list[str]
    last_login_at: datetime | None
    region: str | None = None
    created_at: datetime


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=3, max_length=160)
    password: str = Field(min_length=10, max_length=200)
    roles: list[str] = Field(min_length=1)
    # Solo el superadministrador puede crear usuarios en otra institución.
    organization_id: uuid.UUID | None = None
    region: str | None = None

    @field_validator("region")
    @classmethod
    def _region(cls, v: str | None) -> str | None:
        return _check_region(v)


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=3, max_length=160)
    status: Literal["active", "disabled"] | None = None
    roles: list[str] | None = Field(default=None, min_length=1)
    region: str | None = None

    @field_validator("region")
    @classmethod
    def _region(cls, v: str | None) -> str | None:
        return _check_region(v)


class RoleOut(BaseModel):
    code: str
    name: str
    description: str
    permissions: list[str]


class Page[T](BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int
