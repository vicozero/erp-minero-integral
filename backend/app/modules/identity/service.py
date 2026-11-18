from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.context import current_request_id
from app.core.security import verify_password
from app.modules.audit.service import AuditService, hash_ip
from app.modules.identity.models import AppUser, LoginAudit, Permission, Role, RolePermission, UserRole


class IdentityService:
    @staticmethod
    def authenticate(
        db: Session,
        username: str,
        password: str,
        *,
        ip: str | None = None,
    ) -> AppUser | None:
        user = db.execute(select(AppUser).where(AppUser.username == username)).scalar_one_or_none()
        if user is None or user.status != "ACTIVE" or not verify_password(password, user.password_hash):
            db.add(
                LoginAudit(
                    user_id=user.id if user else None,
                    success=False,
                    reason="CREDENCIALES_INVALIDAS",
                    ip_hash=hash_ip(ip),
                    request_id=current_request_id(),
                )
            )
            db.flush()
            return None

        user.last_login_at = datetime.now(timezone.utc)
        db.add(
            LoginAudit(
                user_id=user.id,
                success=True,
                ip_hash=hash_ip(ip),
                request_id=current_request_id(),
            )
        )
        AuditService.record(
            db,
            action="LOGIN",
            entity_type="AppUser",
            entity_id=user.id,
            actor_id=user.id,
            actor_username=user.username,
            detail="Inicio de sesión exitoso.",
            ip_hash=hash_ip(ip),
        )
        db.flush()
        return user

    @staticmethod
    def has_permission(db: Session, user_id: uuid.UUID, permission_code: str) -> bool:
        stmt = (
            select(Permission.id)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(UserRole, UserRole.role_id == RolePermission.role_id)
            .where(
                UserRole.user_id == user_id,
                Permission.code == permission_code,
                UserRole.valid_from <= datetime.now(timezone.utc),
            )
        )
        first = db.execute(stmt.limit(1)).scalar_one_or_none()
        if first is not None:
            return True
        # El rol ADMIN se considera explícitamente en la semilla con todos los permisos.
        admin_role = db.execute(select(Role.id).where(Role.code == "ADMIN")).scalar_one_or_none()
        if admin_role is None:
            return False
        return (
            db.execute(
                select(UserRole.id)
                .where(
                    UserRole.user_id == user_id,
                    UserRole.role_id == admin_role,
                )
                .limit(1)
            ).scalar_one_or_none()
            is not None
        )

    @staticmethod
    def role_codes(db: Session, user_id: uuid.UUID) -> list[str]:
        rows = db.execute(
            select(Role.code).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user_id)
        ).scalars()
        return list(rows)
