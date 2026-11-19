from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.deps import require_permission
from app.db.session import get_db
from app.modules.identity.models import AppUser, Permission, Role, UserSession
from app.modules.identity.schemas import (
    DepartmentOut,
    PasswordResetIn,
    PasswordResetOut,
    PermissionOut,
    RoleAssignIn,
    RoleOut,
    SessionOut,
    UserAdminOut,
    UserCreateIn,
    UserCreatedOut,
    UserUpdateIn,
)
from app.modules.identity.service import IdentityService
from app.modules.organization.models import Department

router = APIRouter(prefix="/admin", tags=["Administración"])

_ADMIN = require_permission("usuarios.administrar")


@router.get("/users", response_model=list[UserAdminOut])
def list_users(
    _actor: AppUser = Depends(_ADMIN),
    db: Session = Depends(get_db),
) -> list[dict]:
    users = db.execute(select(AppUser).order_by(AppUser.username)).scalars()
    return [IdentityService.user_admin_out(db, user) for user in users]


@router.post("/users", response_model=UserCreatedOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreateIn,
    actor: AppUser = Depends(_ADMIN),
    db: Session = Depends(get_db),
) -> dict:
    user, temporary = IdentityService.create_user(db, payload, actor.id)
    db.commit()
    result = IdentityService.user_admin_out(db, user)
    result["temporary_password"] = temporary
    return result


@router.get("/users/{user_id}", response_model=UserAdminOut)
def get_user(
    user_id: uuid.UUID,
    _actor: AppUser = Depends(_ADMIN),
    db: Session = Depends(get_db),
) -> dict:
    user = db.get(AppUser, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario inexistente.")
    return IdentityService.user_admin_out(db, user)


@router.patch("/users/{user_id}", response_model=UserAdminOut)
def update_user(
    user_id: uuid.UUID,
    payload: UserUpdateIn,
    actor: AppUser = Depends(_ADMIN),
    db: Session = Depends(get_db),
) -> dict:
    user = IdentityService.update_user(db, user_id, payload, actor.id)
    db.commit()
    return IdentityService.user_admin_out(db, user)


@router.delete("/users/{user_id}", response_model=UserAdminOut)
def deactivate_user(
    user_id: uuid.UUID,
    actor: AppUser = Depends(_ADMIN),
    db: Session = Depends(get_db),
) -> dict:
    """Baja lógica. Nunca se elimina físicamente a un usuario con historial."""
    user = IdentityService.deactivate_user(db, user_id, actor.id)
    db.commit()
    return IdentityService.user_admin_out(db, user)


@router.post("/users/{user_id}/roles", response_model=UserAdminOut)
def assign_role(
    user_id: uuid.UUID,
    payload: RoleAssignIn,
    actor: AppUser = Depends(require_permission("roles.asignar")),
    db: Session = Depends(get_db),
) -> dict:
    user = db.get(AppUser, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario inexistente.")
    IdentityService.assign_role(db, user_id, payload, actor.id)
    db.commit()
    return IdentityService.user_admin_out(db, user)


@router.delete("/users/{user_id}/roles/{role_code}", response_model=UserAdminOut)
def remove_role(
    user_id: uuid.UUID,
    role_code: str,
    actor: AppUser = Depends(require_permission("roles.asignar")),
    db: Session = Depends(get_db),
) -> dict:
    IdentityService.remove_role(db, user_id, role_code, actor.id)
    db.commit()
    user = db.get(AppUser, user_id)
    assert user is not None
    return IdentityService.user_admin_out(db, user)


@router.put("/users/{user_id}/departments", response_model=UserAdminOut)
def set_departments(
    user_id: uuid.UUID,
    department_ids: list[uuid.UUID],
    actor: AppUser = Depends(_ADMIN),
    db: Session = Depends(get_db),
) -> dict:
    user = db.get(AppUser, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario inexistente.")
    IdentityService.set_departments(db, user_id, department_ids, actor.id)
    db.commit()
    return IdentityService.user_admin_out(db, user)


@router.post("/users/{user_id}/reset-password", response_model=PasswordResetOut)
def reset_password(
    user_id: uuid.UUID,
    payload: PasswordResetIn,
    actor: AppUser = Depends(_ADMIN),
    db: Session = Depends(get_db),
) -> PasswordResetOut:
    temporary = IdentityService.reset_password(db, user_id, actor.id, payload.reason)
    user = db.get(AppUser, user_id)
    assert user is not None
    db.commit()
    return PasswordResetOut(username=user.username, temporary_password=temporary)


@router.get("/roles", response_model=list[RoleOut])
def list_roles(
    _actor: AppUser = Depends(require_permission("roles.asignar")),
    db: Session = Depends(get_db),
) -> list[dict]:
    rows = db.execute(select(Role).order_by(Role.code)).scalars()
    return [
        {"code": row.code, "name": row.name, "description": row.description}
        for row in rows
    ]


@router.get("/permissions", response_model=list[PermissionOut])
def list_permissions(
    _actor: AppUser = Depends(_ADMIN),
    db: Session = Depends(get_db),
) -> list[dict]:
    rows = db.execute(select(Permission).order_by(Permission.code)).scalars()
    return [{"code": row.code, "description": row.description} for row in rows]


@router.get("/departments", response_model=list[DepartmentOut])
def list_departments(
    actor: AppUser = Depends(require_permission("departamentos.consultar")),
    db: Session = Depends(get_db),
) -> list[dict]:
    stmt = select(Department).order_by(Department.code)
    if not IdentityService.is_admin(db, actor.id):
        allowed = IdentityService.department_ids(db, actor.id)
        stmt = stmt.where(Department.id.in_(allowed))
    rows = db.execute(stmt).scalars()
    return [
        {
            "id": str(row.id),
            "code": row.code,
            "name": row.name,
            "mining_unit_id": str(row.mining_unit_id) if row.mining_unit_id else None,
        }
        for row in rows
    ]


@router.get("/sessions", response_model=list[SessionOut])
def list_all_sessions(
    _actor: AppUser = Depends(require_permission("sesiones.consultar")),
    db: Session = Depends(get_db),
) -> list[dict]:
    rows = db.execute(
        select(UserSession).where(UserSession.revoked_at.is_(None)).order_by(UserSession.created_at.desc())
    ).scalars()
    return [
        {
            "id": str(row.id),
            "user_id": str(row.user_id),
            "created_at": row.created_at,
            "expires_at": row.expires_at,
            "last_seen_at": row.last_seen_at,
            "revoked_at": row.revoked_at,
        }
        for row in rows
    ]
