from __future__ import annotations

import secrets
import string
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import NoReturn

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.context import current_request_id
from app.core.security import (
    generate_csrf_token,
    generate_session_token,
    hash_password,
    hash_token,
    needs_password_upgrade,
    verify_password,
)
from app.modules.audit.service import AuditService, hash_ip
from app.modules.identity.models import (
    AppUser,
    LoginAudit,
    Permission,
    Role,
    RolePermission,
    UserDepartment,
    UserRole,
    UserSession,
)
from app.modules.organization.models import Department
from app.shared.constants import (
    ADMIN_ROLE_CODES,
    PERMISSIONS,
    ROLE_LABELS,
    SUPERADMIN_ROLE_CODE,
    canonical_permission,
)

MAX_FAILED_ATTEMPTS = 5
LOCK_MINUTES = 15


class AuthenticationError(Exception):
    """Motivo de fallo de acceso, sin exponer contraseñas."""

    def __init__(self, reason: str, detail: str) -> None:
        super().__init__(detail)
        self.reason = reason
        self.detail = detail


@dataclass(frozen=True)
class LoginResult:
    user: AppUser
    session_token: str
    csrf_token: str
    expires_at: datetime


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash_user_agent(user_agent: str | None) -> str | None:
    if not user_agent:
        return None
    import hashlib

    return hashlib.sha256(user_agent.encode("utf-8")).hexdigest()


def generate_temporary_password() -> str:
    """Contraseña temporal que cumple la política y se entrega una sola vez."""
    alphabet = string.ascii_letters + string.digits
    random_part = "".join(secrets.choice(alphabet) for _ in range(14))
    return f"Tmp-{random_part}!"


def _fail(detail: str, code: int = status.HTTP_400_BAD_REQUEST) -> NoReturn:
    raise HTTPException(status_code=code, detail=detail)


class IdentityService:
    # ------------------------------------------------------------------
    # Autenticación y sesiones
    # ------------------------------------------------------------------
    @staticmethod
    def authenticate(
        db: Session,
        username: str,
        password: str,
        *,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> LoginResult:
        user = db.execute(select(AppUser).where(AppUser.username == username)).scalar_one_or_none()
        ua_hash = _hash_user_agent(user_agent)

        def register_failure(reason: str, target: AppUser | None = user) -> None:
            db.add(
                LoginAudit(
                    user_id=target.id if target else None,
                    success=False,
                    reason=reason,
                    ip_hash=hash_ip(ip),
                    user_agent_hash=ua_hash,
                    request_id=current_request_id(),
                )
            )
            db.flush()

        if user is None:
            register_failure("CREDENCIALES_INVALIDAS", None)
            raise AuthenticationError("CREDENCIALES_INVALIDAS", "Credenciales inválidas.")

        if user.status == "INACTIVE":
            register_failure("USUARIO_INACTIVO")
            raise AuthenticationError("USUARIO_INACTIVO", "La cuenta está inactiva.")

        now = _now()
        if user.status == "LOCKED":
            if user.locked_until is None or user.locked_until > now:
                register_failure("CUENTA_BLOQUEADA")
                raise AuthenticationError("CUENTA_BLOQUEADA", "La cuenta está bloqueada temporalmente.")
            # El bloqueo temporal expiró: se rehabilita de forma controlada.
            user.status = "ACTIVE"
            user.failed_login_attempts = 0
            user.locked_until = None

        if not verify_password(password, user.password_hash):
            user.failed_login_attempts += 1
            reason = "CREDENCIALES_INVALIDAS"
            if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
                user.status = "LOCKED"
                user.locked_until = now + timedelta(minutes=LOCK_MINUTES)
                reason = "CUENTA_BLOQUEADA"
            register_failure(reason)
            AuditService.record(
                db,
                action="LOGIN_FAILED",
                entity_type="AppUser",
                entity_id=user.id,
                actor_id=user.id,
                actor_username=user.username,
                detail=f"Intento fallido #{user.failed_login_attempts}. Motivo: {reason}.",
                ip_hash=hash_ip(ip),
            )
            db.flush()
            if reason == "CUENTA_BLOQUEADA":
                raise AuthenticationError(reason, "Cuenta bloqueada tras intentos fallidos. Intente más tarde.")
            raise AuthenticationError(reason, "Credenciales inválidas.")

        # Acceso correcto: se reinician contadores y se migra el hash heredado.
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login_at = now
        if needs_password_upgrade(user.password_hash):
            user.password_hash = hash_password(password)
            user.password_changed_at = now

        session_token = generate_session_token()
        csrf_token = generate_csrf_token()
        expires_at = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        db.add(
            UserSession(
                user_id=user.id,
                token_hash=hash_token(session_token),
                csrf_hash=hash_token(csrf_token),
                created_at=now,
                expires_at=expires_at,
                last_seen_at=now,
                ip_hash=hash_ip(ip),
                user_agent_hash=ua_hash,
            )
        )
        db.add(
            LoginAudit(
                user_id=user.id,
                success=True,
                ip_hash=hash_ip(ip),
                user_agent_hash=ua_hash,
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
        return LoginResult(user, session_token, csrf_token, expires_at)

    @staticmethod
    def session_by_token(db: Session, token: str) -> UserSession | None:
        return db.execute(
            select(UserSession).where(UserSession.token_hash == hash_token(token))
        ).scalar_one_or_none()

    @staticmethod
    def is_session_valid(session: UserSession) -> bool:
        now = _now()
        expires_at = session.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return session.revoked_at is None and expires_at > now

    @staticmethod
    def revoke_session(db: Session, session: UserSession, actor_id: uuid.UUID | None = None) -> None:
        if session.revoked_at is not None:
            return
        session.revoked_at = _now()
        session.revoked_by = actor_id
        db.flush()

    @staticmethod
    def revoke_all_sessions(db: Session, user_id: uuid.UUID, actor_id: uuid.UUID | None = None) -> None:
        sessions = db.execute(
            select(UserSession).where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
        ).scalars()
        for session in sessions:
            IdentityService.revoke_session(db, session, actor_id)

    # ------------------------------------------------------------------
    # RBAC
    # ------------------------------------------------------------------
    @staticmethod
    def role_codes(db: Session, user_id: uuid.UUID) -> list[str]:
        now = _now()
        rows = db.execute(
            select(Role.code)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(
                UserRole.user_id == user_id,
                UserRole.valid_from <= now,
                (UserRole.valid_to.is_(None)) | (UserRole.valid_to > now),
            )
            .order_by(Role.code)
        ).scalars()
        return list(rows)

    @staticmethod
    def is_admin(db: Session, user_id: uuid.UUID) -> bool:
        return bool(set(IdentityService.role_codes(db, user_id)) & ADMIN_ROLE_CODES)

    @staticmethod
    def has_permission(db: Session, user_id: uuid.UUID, permission_code: str) -> bool:
        canonical = canonical_permission(permission_code)
        now = _now()
        first = db.execute(
            select(Permission.id)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(UserRole, UserRole.role_id == RolePermission.role_id)
            .where(
                UserRole.user_id == user_id,
                Permission.code.in_((canonical, permission_code)),
                UserRole.valid_from <= now,
                (UserRole.valid_to.is_(None)) | (UserRole.valid_to > now),
            )
            .limit(1)
        ).scalar_one_or_none()
        return first is not None or IdentityService.is_admin(db, user_id)

    @staticmethod
    def permission_codes(db: Session, user_id: uuid.UUID) -> list[str]:
        if IdentityService.is_admin(db, user_id):
            return sorted(PERMISSIONS)
        now = _now()
        rows = db.execute(
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(UserRole, UserRole.role_id == RolePermission.role_id)
            .where(
                UserRole.user_id == user_id,
                UserRole.valid_from <= now,
                (UserRole.valid_to.is_(None)) | (UserRole.valid_to > now),
            )
        ).scalars()
        return sorted(set(rows))

    @staticmethod
    def department_ids(db: Session, user_id: uuid.UUID) -> list[uuid.UUID]:
        return list(
            db.execute(
                select(UserDepartment.department_id).where(
                    UserDepartment.user_id == user_id,
                    UserDepartment.revoked_at.is_(None),
                )
            ).scalars()
        )

    @staticmethod
    def mining_unit_ids(db: Session, user_id: uuid.UUID) -> list[uuid.UUID]:
        return [
            unit_id
            for unit_id in db.execute(
                select(Department.mining_unit_id)
                .join(UserDepartment, UserDepartment.department_id == Department.id)
                .where(
                    UserDepartment.user_id == user_id,
                    UserDepartment.revoked_at.is_(None),
                    Department.mining_unit_id.is_not(None),
                )
            ).scalars()
            if unit_id is not None
        ]

    @staticmethod
    def can_access_department(db: Session, user_id: uuid.UUID, department_id: uuid.UUID) -> bool:
        if IdentityService.is_admin(db, user_id):
            return True
        return department_id in IdentityService.department_ids(db, user_id)

    @staticmethod
    def can_access_mining_unit(db: Session, user_id: uuid.UUID, mining_unit_id: uuid.UUID) -> bool:
        if IdentityService.is_admin(db, user_id):
            return True
        return mining_unit_id in IdentityService.mining_unit_ids(db, user_id)

    @staticmethod
    def assert_department_access(db: Session, user_id: uuid.UUID, department_id: uuid.UUID) -> None:
        if not IdentityService.can_access_department(db, user_id, department_id):
            _fail("No tiene acceso a registros de ese departamento.", status.HTTP_403_FORBIDDEN)

    # ------------------------------------------------------------------
    # Administración de usuarios
    # ------------------------------------------------------------------
    @staticmethod
    def _role_by_code(db: Session, code: str) -> Role:
        role = db.execute(select(Role).where(Role.code == code)).scalar_one_or_none()
        if role is None:
            _fail("Rol desconocido.", status.HTTP_422_UNPROCESSABLE_ENTITY)
        return role

    @staticmethod
    def _validate_admin_escalation(
        db: Session, actor_id: uuid.UUID, target_id: uuid.UUID | None, role_code: str
    ) -> None:
        if role_code not in ADMIN_ROLE_CODES:
            return
        if target_id is not None and actor_id == target_id:
            _fail("No puede concederse permisos administrativos a sí mismo.", status.HTTP_403_FORBIDDEN)
        if role_code == SUPERADMIN_ROLE_CODE:
            if SUPERADMIN_ROLE_CODE not in IdentityService.role_codes(db, actor_id):
                _fail("Solo un superadministrador puede asignar ese rol.", status.HTTP_403_FORBIDDEN)
            return
        if not IdentityService.is_admin(db, actor_id):
            _fail("Solo un administrador puede asignar el rol Administrador.", status.HTTP_403_FORBIDDEN)

    @staticmethod
    def active_superadmin_ids(db: Session) -> list[uuid.UUID]:
        now = _now()
        return list(
            db.execute(
                select(AppUser.id)
                .join(UserRole, UserRole.user_id == AppUser.id)
                .join(Role, Role.id == UserRole.role_id)
                .where(
                    AppUser.status == "ACTIVE",
                    Role.code == SUPERADMIN_ROLE_CODE,
                    UserRole.valid_from <= now,
                    (UserRole.valid_to.is_(None)) | (UserRole.valid_to > now),
                )
            ).scalars()
        )

    @staticmethod
    def is_last_active_superadmin(db: Session, user_id: uuid.UUID) -> bool:
        active = IdentityService.active_superadmin_ids(db)
        return user_id in active and len(active) == 1

    @staticmethod
    def create_user(db: Session, payload, actor_id: uuid.UUID) -> tuple[AppUser, str | None]:
        for code in payload.roles:
            IdentityService._validate_admin_escalation(db, actor_id, None, code)

        exists = db.execute(
            select(AppUser.id).where((AppUser.username == payload.username) | (AppUser.email == payload.email))
        ).scalar_one_or_none()
        if exists is not None:
            _fail("El usuario o correo ya existe.", status.HTTP_409_CONFLICT)

        generated = not bool(payload.password)
        temporary = generate_temporary_password() if generated else None
        password = payload.password or temporary or ""
        user = AppUser(
            username=payload.username,
            email=payload.email,
            full_name=payload.full_name,
            password_hash=hash_password(password),
            status="ACTIVE",
            must_change_password=True,
            password_changed_at=_now(),
            password_changed_by=actor_id,
            created_by=actor_id,
        )
        db.add(user)
        db.flush()

        for code in payload.roles:
            IdentityService.assign_role(
                db,
                user.id,
                SimpleNamespace(role_code=code, scope_type="GLOBAL", scope_id=None),
                actor_id,
                audit=False,
            )
        IdentityService.set_departments(db, user.id, payload.department_ids, actor_id, audit=False)

        AuditService.record(
            db,
            action="USER_CREATED",
            entity_type="AppUser",
            entity_id=user.id,
            actor_id=actor_id,
            after={"username": user.username, "roles": payload.roles, "must_change_password": True},
        )
        db.flush()
        return user, temporary

    @staticmethod
    def update_user(db: Session, user_id: uuid.UUID, payload, actor_id: uuid.UUID) -> AppUser:
        user = db.get(AppUser, user_id)
        if user is None:
            _fail("Usuario inexistente.", status.HTTP_404_NOT_FOUND)
        before = {
            "email": user.email,
            "full_name": user.full_name,
            "status": user.status,
        }
        if payload.email is not None:
            duplicate = db.execute(
                select(AppUser.id).where(AppUser.email == payload.email, AppUser.id != user_id)
            ).scalar_one_or_none()
            if duplicate is not None:
                _fail("El correo ya está en uso.", status.HTTP_409_CONFLICT)
            user.email = payload.email
        if payload.full_name is not None:
            user.full_name = payload.full_name
        if payload.status is not None:
            if payload.status == "INACTIVE" and actor_id == user_id:
                _fail("No puede desactivar su propia cuenta.", status.HTTP_400_BAD_REQUEST)
            if payload.status == "INACTIVE" and IdentityService.is_last_active_superadmin(db, user_id):
                _fail(
                    "No puede desactivar el último superadministrador activo.",
                    status.HTTP_400_BAD_REQUEST,
                )
            user.status = payload.status
            if payload.status == "INACTIVE":
                user.deactivated_at = _now()
                user.deactivated_by = actor_id
                IdentityService.revoke_all_sessions(db, user_id, actor_id)
            else:
                user.deactivated_at = None
                user.deactivated_by = None
        if payload.department_ids is not None:
            IdentityService.set_departments(db, user_id, payload.department_ids, actor_id, audit=False)
        user.updated_at = _now()
        user.updated_by = actor_id
        AuditService.record(
            db,
            action="USER_UPDATED",
            entity_type="AppUser",
            entity_id=user.id,
            actor_id=actor_id,
            before=before,
            after={
                "email": user.email,
                "full_name": user.full_name,
                "status": user.status,
                "department_ids": [str(item) for item in payload.department_ids]
                if payload.department_ids is not None
                else None,
            },
        )
        db.flush()
        return user

    @staticmethod
    def deactivate_user(db: Session, user_id: uuid.UUID, actor_id: uuid.UUID) -> AppUser:
        user = db.get(AppUser, user_id)
        if user is None:
            _fail("Usuario inexistente.", status.HTTP_404_NOT_FOUND)
        if actor_id == user_id:
            _fail("No puede dar de baja su propia cuenta.", status.HTTP_400_BAD_REQUEST)
        if user.status == "INACTIVE":
            return user
        if IdentityService.is_last_active_superadmin(db, user_id):
            _fail(
                "No puede dar de baja el último superadministrador activo.",
                status.HTTP_400_BAD_REQUEST,
            )
        user.status = "INACTIVE"
        user.deactivated_at = _now()
        user.deactivated_by = actor_id
        IdentityService.revoke_all_sessions(db, user_id, actor_id)
        AuditService.record(
            db,
            action="USER_DEACTIVATED",
            entity_type="AppUser",
            entity_id=user.id,
            actor_id=actor_id,
            before={"status": "ACTIVE"},
            after={"status": "INACTIVE", "deleted_physically": False},
        )
        db.flush()
        return user

    @staticmethod
    def set_departments(
        db: Session,
        user_id: uuid.UUID,
        department_ids: list[uuid.UUID],
        actor_id: uuid.UUID,
        *,
        audit: bool = True,
    ) -> None:
        wanted = set(department_ids)
        if wanted:
            found = set(
                db.execute(select(Department.id).where(Department.id.in_(wanted))).scalars()
            )
            if found != wanted:
                _fail("Uno o más departamentos no existen.", status.HTTP_422_UNPROCESSABLE_ENTITY)
        existing = db.execute(
            select(UserDepartment).where(
                UserDepartment.user_id == user_id,
                UserDepartment.revoked_at.is_(None),
            )
        ).scalars()
        now = _now()
        for assignment in existing:
            if assignment.department_id not in wanted:
                assignment.revoked_at = now
                assignment.revoked_by = actor_id
        db.flush()
        active = {
            assignment.department_id
            for assignment in db.execute(
                select(UserDepartment).where(
                    UserDepartment.user_id == user_id,
                    UserDepartment.revoked_at.is_(None),
                )
            ).scalars()
        }
        for department_id in wanted - active:
            db.add(
                UserDepartment(
                    user_id=user_id,
                    department_id=department_id,
                    created_by=actor_id,
                )
            )
        if audit:
            AuditService.record(
                db,
                action="USER_DEPARTMENTS_CHANGED",
                entity_type="AppUser",
                entity_id=user_id,
                actor_id=actor_id,
                after={"department_ids": sorted(str(item) for item in wanted)},
            )
        db.flush()

    @staticmethod
    def assign_role(
        db: Session,
        user_id: uuid.UUID,
        payload,
        actor_id: uuid.UUID,
        *,
        audit: bool = True,
    ) -> UserRole:
        code = payload.role_code
        IdentityService._validate_admin_escalation(db, actor_id, user_id, code)
        role = IdentityService._role_by_code(db, code)
        scope_type = payload.scope_type
        scope_id = payload.scope_id
        if scope_type in {"DEPARTMENT", "MINING_UNIT"} and scope_id is None:
            _fail("El alcance requiere un identificador.", status.HTTP_422_UNPROCESSABLE_ENTITY)
        if scope_type == "DEPARTMENT" and scope_id is not None:
            if not IdentityService.can_access_department(db, actor_id, scope_id):
                _fail("No puede asignar roles en ese departamento.", status.HTTP_403_FORBIDDEN)
        existing = db.execute(
            select(UserRole).where(
                UserRole.user_id == user_id,
                UserRole.role_id == role.id,
                UserRole.scope_type == scope_type,
                UserRole.scope_id == scope_id,
            )
        ).scalar_one_or_none()
        if existing is not None:
            _fail("El usuario ya tiene ese rol en el alcance indicado.", status.HTTP_409_CONFLICT)
        assignment = UserRole(
            user_id=user_id,
            role_id=role.id,
            scope_type=scope_type,
            scope_id=scope_id,
            valid_from=_now(),
            created_by=actor_id,
        )
        db.add(assignment)
        if audit:
            AuditService.record(
                db,
                action="ROLE_ASSIGNED",
                entity_type="AppUser",
                entity_id=user_id,
                actor_id=actor_id,
                after={"role": code, "scope_type": scope_type, "scope_id": str(scope_id) if scope_id else None},
            )
        db.flush()
        return assignment

    @staticmethod
    def remove_role(db: Session, user_id: uuid.UUID, role_code: str, actor_id: uuid.UUID) -> None:
        IdentityService._validate_admin_escalation(db, actor_id, user_id, role_code)
        role = IdentityService._role_by_code(db, role_code)
        assignment = db.execute(
            select(UserRole).where(UserRole.user_id == user_id, UserRole.role_id == role.id)
        ).scalar_one_or_none()
        if assignment is None:
            _fail("El usuario no tiene ese rol.", status.HTTP_404_NOT_FOUND)
        if role_code == SUPERADMIN_ROLE_CODE and IdentityService.is_last_active_superadmin(db, user_id):
            _fail(
                "No puede retirar el rol al último superadministrador activo.",
                status.HTTP_400_BAD_REQUEST,
            )
        if role_code in ADMIN_ROLE_CODES and len(IdentityService.role_codes(db, user_id)) == 1:
            _fail("No puede retirar el último rol administrativo.", status.HTTP_400_BAD_REQUEST)
        # Se cierra la vigencia en lugar de borrar la fila histórica.
        assignment.valid_to = _now()
        AuditService.record(
            db,
            action="ROLE_REMOVED",
            entity_type="AppUser",
            entity_id=user_id,
            actor_id=actor_id,
            before={"role": role_code},
        )
        db.flush()

    @staticmethod
    def change_username(
        db: Session,
        user_id: uuid.UUID,
        payload,
        actor_id: uuid.UUID,
        *,
        keep_session_id: uuid.UUID | None = None,
    ) -> AppUser:
        user = db.get(AppUser, user_id)
        if user is None:
            _fail("Usuario inexistente.", status.HTTP_404_NOT_FOUND)
        if not verify_password(payload.current_password, user.password_hash):
            _fail("La contraseña actual no es correcta.", status.HTTP_403_FORBIDDEN)
        if payload.username == user.username:
            _fail("El nombre de usuario ya es el mismo.", status.HTTP_422_UNPROCESSABLE_ENTITY)
        duplicate = db.execute(
            select(AppUser.id).where(AppUser.username == payload.username, AppUser.id != user_id)
        ).scalar_one_or_none()
        if duplicate is not None:
            _fail("El nombre de usuario ya está en uso.", status.HTTP_409_CONFLICT)

        before = {"username": user.username}
        user.username = payload.username
        user.updated_at = _now()
        user.updated_by = actor_id

        sessions = db.execute(
            select(UserSession).where(
                UserSession.user_id == user_id,
                UserSession.revoked_at.is_(None),
            )
        ).scalars()
        for session in sessions:
            if session.id != keep_session_id:
                IdentityService.revoke_session(db, session, actor_id)

        AuditService.record(
            db,
            action="USERNAME_CHANGED",
            entity_type="AppUser",
            entity_id=user.id,
            actor_id=actor_id,
            before=before,
            after={"username": user.username, "other_sessions_revoked": True},
        )
        db.flush()
        return user

    @staticmethod
    def change_password(db: Session, user_id: uuid.UUID, current: str, new: str, actor_id: uuid.UUID) -> None:
        user = db.get(AppUser, user_id)
        if user is None:
            _fail("Usuario inexistente.", status.HTTP_404_NOT_FOUND)
        if not verify_password(current, user.password_hash):
            _fail("La contraseña actual no es correcta.", status.HTTP_403_FORBIDDEN)
        if current == new:
            _fail("La contraseña nueva debe ser diferente.", status.HTTP_422_UNPROCESSABLE_ENTITY)
        user.password_hash = hash_password(new)
        user.password_changed_at = _now()
        user.password_changed_by = actor_id
        user.must_change_password = False
        user.failed_login_attempts = 0
        user.locked_until = None
        if user.status == "LOCKED":
            user.status = "ACTIVE"
        IdentityService.revoke_all_sessions(db, user_id, actor_id)
        AuditService.record(
            db,
            action="PASSWORD_CHANGED",
            entity_type="AppUser",
            entity_id=user.id,
            actor_id=actor_id,
            before=None,
            after={"password_changed": True, "must_change_password": False},
        )
        db.flush()

    @staticmethod
    def reset_password(db: Session, user_id: uuid.UUID, actor_id: uuid.UUID, reason: str | None) -> str:
        user = db.get(AppUser, user_id)
        if user is None:
            _fail("Usuario inexistente.", status.HTTP_404_NOT_FOUND)
        if user.status == "INACTIVE":
            _fail("La cuenta está inactiva; reactívela antes de restablecer.", status.HTTP_400_BAD_REQUEST)
        temporary = generate_temporary_password()
        user.password_hash = hash_password(temporary)
        user.password_changed_at = _now()
        user.password_changed_by = actor_id
        user.must_change_password = True
        user.failed_login_attempts = 0
        user.locked_until = None
        user.status = "ACTIVE"
        IdentityService.revoke_all_sessions(db, user_id, actor_id)
        AuditService.record(
            db,
            action="PASSWORD_RESET",
            entity_type="AppUser",
            entity_id=user.id,
            actor_id=actor_id,
            after={"must_change_password": True},
            detail=reason,
        )
        db.flush()
        return temporary

    # ------------------------------------------------------------------
    # Proyecciones para API
    # ------------------------------------------------------------------
    @staticmethod
    def user_out(db: Session, user: AppUser) -> dict:
        return {
            "id": str(user.id),
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "status": user.status,
            "roles": IdentityService.role_codes(db, user.id),
            "permissions": IdentityService.permission_codes(db, user.id),
            "department_ids": [str(item) for item in IdentityService.department_ids(db, user.id)],
            "must_change_password": bool(user.must_change_password),
        }

    @staticmethod
    def user_admin_out(db: Session, user: AppUser) -> dict:
        data = IdentityService.user_out(db, user)
        data.update(
            {
                "failed_login_attempts": user.failed_login_attempts,
                "locked_until": user.locked_until,
                "last_login_at": user.last_login_at,
                "created_at": user.created_at,
            }
        )
        return data

    @staticmethod
    def role_label(code: str) -> str:
        return ROLE_LABELS.get(code, code)
