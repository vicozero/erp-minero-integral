from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.shared.constants import ROLE_LABELS


def validate_password_policy(value: str) -> str:
    """Política mínima para contraseñas nuevas; no se aplica a la semilla demo."""
    if len(value) < 12:
        raise ValueError("La contraseña debe tener al menos 12 caracteres.")
    if not re.search(r"[a-z]", value):
        raise ValueError("La contraseña debe incluir una letra minúscula.")
    if not re.search(r"[A-Z]", value):
        raise ValueError("La contraseña debe incluir una letra mayúscula.")
    if not re.search(r"\d", value):
        raise ValueError("La contraseña debe incluir un número.")
    if not re.search(r"[^A-Za-z0-9]", value):
        raise ValueError("La contraseña debe incluir un carácter especial.")
    return value


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)


class TokenResponse(BaseModel):
    """Compatibilidad con clientes Bearer de la Fase 2."""

    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: str
    username: str
    email: str
    full_name: str
    status: str
    roles: list[str]
    permissions: list[str]
    department_ids: list[str]
    must_change_password: bool = False


class SessionResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    csrf_token: str
    expires_at: datetime
    must_change_password: bool
    user: UserOut


class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=12, max_length=200)

    @field_validator("new_password")
    @classmethod
    def _policy(cls, value: str) -> str:
        return validate_password_policy(value)


class UsernameIn(BaseModel):
    """Cambio controlado del nombre de usuario desde Mi cuenta."""

    username: str = Field(min_length=3, max_length=80, pattern=r"^[A-Za-z0-9._-]+$")
    current_password: str = Field(min_length=1, max_length=200)


class PasswordResetIn(BaseModel):
    """El administrador no envía contraseñas: el servidor genera una temporal."""

    reason: str | None = Field(default=None, max_length=250)


class PasswordResetOut(BaseModel):
    username: str
    temporary_password: str
    must_change_password: bool = True
    detail: str = "Contraseña temporal de uso único. Debe cambiarse en el primer acceso."


class UserCreateIn(BaseModel):
    username: str = Field(min_length=3, max_length=80, pattern=r"^[A-Za-z0-9._-]+$")
    email: str = Field(min_length=5, max_length=255)
    full_name: str = Field(min_length=2, max_length=160)
    password: str | None = Field(default=None, max_length=200)
    roles: list[str] = Field(default_factory=list)
    department_ids: list[uuid.UUID] = Field(default_factory=list)

    @field_validator("password")
    @classmethod
    def _policy(cls, value: str | None) -> str | None:
        return validate_password_policy(value) if value else None

    @field_validator("roles")
    @classmethod
    def _roles(cls, value: list[str]) -> list[str]:
        unknown = [code for code in value if code not in ROLE_LABELS]
        if unknown:
            raise ValueError(f"Roles desconocidos: {', '.join(unknown)}")
        return value


class UserUpdateIn(BaseModel):
    email: str | None = Field(default=None, min_length=5, max_length=255)
    full_name: str | None = Field(default=None, min_length=2, max_length=160)
    status: str | None = Field(default=None, pattern=r"^(ACTIVE|INACTIVE)$")
    department_ids: list[uuid.UUID] | None = None


class UserAdminOut(BaseModel):
    id: str
    username: str
    email: str
    full_name: str
    status: str
    roles: list[str]
    permissions: list[str]
    department_ids: list[str]
    must_change_password: bool
    failed_login_attempts: int
    locked_until: datetime | None
    last_login_at: datetime | None
    created_at: datetime


class UserCreatedOut(UserAdminOut):
    """La contraseña temporal se devuelve únicamente en la respuesta de alta."""

    temporary_password: str | None = None


class RoleAssignIn(BaseModel):
    role_code: str = Field(min_length=2, max_length=40)
    scope_type: str = Field(default="GLOBAL", pattern=r"^(GLOBAL|DEPARTMENT|MINING_UNIT)$")
    scope_id: uuid.UUID | None = None

    @field_validator("role_code")
    @classmethod
    def _known(cls, value: str) -> str:
        if value not in ROLE_LABELS:
            raise ValueError("Rol desconocido.")
        return value


class RoleOut(BaseModel):
    code: str
    name: str
    description: str | None


class PermissionOut(BaseModel):
    code: str
    description: str | None


class DepartmentOut(BaseModel):
    id: str
    code: str
    name: str
    mining_unit_id: str | None


class SessionOut(BaseModel):
    id: str
    user_id: str
    created_at: datetime
    expires_at: datetime
    last_seen_at: datetime | None
    revoked_at: datetime | None


class AuditEntryOut(BaseModel):
    id: str
    occurred_at: datetime
    actor_username: str | None
    action: str
    entity_type: str
    entity_id: str | None
    detail: str | None
    request_id: str
