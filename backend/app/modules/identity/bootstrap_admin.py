from __future__ import annotations

import argparse
import getpass
import sys
from datetime import datetime, timezone
from urllib.parse import unquote, urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.modules.audit.service import AuditService
from app.modules.identity.models import AppUser, Permission, Role, RolePermission, UserRole
from app.modules.identity.service import IdentityService
from app.shared.constants import PERMISSIONS, ROLE_LABELS, ROLE_PERMISSIONS, SUPERADMIN_ROLE_CODE

DEVELOPMENT_DATABASE = "erp_minero_dev"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_or_create_role(db: Session, code: str) -> Role:
    role = db.execute(select(Role).where(Role.code == code)).scalar_one_or_none()
    if role is None:
        role = Role(code=code, name=ROLE_LABELS.get(code, code), description="Rol del catálogo RBAC.")
        db.add(role)
        db.flush()
    return role


def sync_rbac_catalog(db: Session) -> dict[str, Role]:
    """Sincroniza roles y permisos del catálogo sin borrar asignaciones previas."""
    roles = {code: _get_or_create_role(db, code) for code in ROLE_PERMISSIONS}
    codes = sorted(set(PERMISSIONS).union(*(set(items) for items in ROLE_PERMISSIONS.values())))

    permissions: dict[str, Permission] = {}
    for code in codes:
        permission = db.execute(select(Permission).where(Permission.code == code)).scalar_one_or_none()
        if permission is None:
            permission = Permission(code=code, description=code)
            db.add(permission)
            db.flush()
        permissions[code] = permission

    for role_code, role_codes in ROLE_PERMISSIONS.items():
        role = roles[role_code]
        for code in dict.fromkeys(role_codes):
            exists = db.execute(
                select(RolePermission.role_id).where(
                    RolePermission.role_id == role.id,
                    RolePermission.permission_id == permissions[code].id,
                )
            ).scalar_one_or_none()
            if exists is None:
                db.add(RolePermission(role_id=role.id, permission_id=permissions[code].id))
    db.flush()
    return roles


def ensure_superadmin(
    db: Session,
    username: str,
    password: str,
    *,
    email: str | None = None,
    full_name: str | None = None,
) -> tuple[AppUser, bool]:
    """Crea el superadministrador maestro de forma idempotente.

    La contraseña se recibe ya capturada por el llamador; nunca se registra ni
    se devuelve. La cuenta creada siempre exige cambio en el primer acceso.
    """
    if len(password) < 8:
        raise ValueError("La contraseña inicial debe tener al menos 8 caracteres.")

    roles = sync_rbac_catalog(db)
    existing = db.execute(select(AppUser).where(AppUser.username == username)).scalar_one_or_none()
    if existing is not None:
        if (
            existing.status == "ACTIVE"
            and SUPERADMIN_ROLE_CODE in IdentityService.role_codes(db, existing.id)
        ):
            return existing, False
        raise RuntimeError(
            "El usuario indicado ya existe sin el rol SUPERADMIN activo; "
            "revise la cuenta manualmente en lugar de escalarla de forma automática."
        )

    effective_email = email or f"{username}@erp.local.invalid"
    duplicate_email = db.execute(
        select(AppUser.id).where(AppUser.email == effective_email)
    ).scalar_one_or_none()
    if duplicate_email is not None:
        raise RuntimeError("El correo indicado ya está en uso por otra cuenta.")

    now = _now()
    user = AppUser(
        username=username,
        email=effective_email,
        full_name=full_name or "Superadministrador del ERP",
        password_hash=hash_password(password),
        status="ACTIVE",
        must_change_password=True,
        password_changed_at=now,
    )
    db.add(user)
    db.flush()
    db.add(
        UserRole(
            user_id=user.id,
            role_id=roles[SUPERADMIN_ROLE_CODE].id,
            scope_type="GLOBAL",
            valid_from=now,
        )
    )
    AuditService.record(
        db,
        action="SUPERADMIN_BOOTSTRAPPED",
        entity_type="AppUser",
        entity_id=user.id,
        actor_username="system",
        after={"username": username, "must_change_password": True},
        detail="Alta maestra de desarrollo; contraseña inicial sujeta a cambio obligatorio.",
    )
    db.flush()
    return user, True


def _database_name() -> str:
    parsed = urlparse(settings.DATABASE_URL)
    return unquote(parsed.path).lstrip("/")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Alta maestra del superadministrador local.")
    parser.add_argument("--username", default="admin", help="Nombre de usuario inicial.")
    parser.add_argument(
        "--password-stdin",
        action="store_true",
        help="Lee la contraseña y su confirmación desde stdin, sin argumentos visibles.",
    )
    args = parser.parse_args(argv)

    database = _database_name()
    if database != DEVELOPMENT_DATABASE:
        print(
            f"ERROR: este comando solo puede ejecutarse sobre {DEVELOPMENT_DATABASE}. "
            f"Perfil activo: {database}."
        )
        return 2

    print(f"Base de destino: {database}")
    print("La contraseña inicial debe tener al menos 8 caracteres y será de un solo uso.")
    if args.password_stdin:
        password = sys.stdin.readline().rstrip("\r\n")
        confirmation = sys.stdin.readline().rstrip("\r\n")
    else:
        password = getpass.getpass("Contraseña inicial de desarrollo: ")
        confirmation = getpass.getpass("Confirme la contraseña inicial: ")
    if password != confirmation:
        print("ERROR: las contraseñas no coinciden.")
        return 1

    try:
        with SessionLocal() as db:
            user, created = ensure_superadmin(db, args.username, password)
            db.commit()
    except (RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 1

    action = "creado" if created else "ya existía"
    print(f"Superadministrador {action}: {user.username}")
    print("Debe cambiar la contraseña en el primer inicio de sesión.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
