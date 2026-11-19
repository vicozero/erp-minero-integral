from __future__ import annotations

import os
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.identity.bootstrap_admin import ensure_superadmin
from app.modules.identity.models import AppUser
from app.modules.identity.service import IdentityService
from app.modules.organization.models import Warehouse
from tests.conftest import auth_header, login_with_cookie

INITIAL_PASSWORD = "InicialLote4_2026"
DEMOTION_PASSWORD = "CambioLote4_2026!"


def _superadmin(db: Session, username: str = "qa.superadmin") -> AppUser:
    user, _ = ensure_superadmin(db, username, INITIAL_PASSWORD)
    # La cuenta recién creada exige cambio; se desactiva el flag solo dentro
    # de la transacción aislada de la prueba para poder usar endpoints RBAC.
    user.must_change_password = False
    db.flush()
    return user


def _superadmin_headers(client, db: Session, username: str = "qa.superadmin") -> dict[str, str]:
    _superadmin(db, username)
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": INITIAL_PASSWORD},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_alta_maestra_es_idempotente_y_exige_cambio(db: Session) -> None:
    user, created = ensure_superadmin(db, "qa.maestro", INITIAL_PASSWORD)
    assert created is True
    assert user.must_change_password is True
    assert user.password_hash.startswith("$argon2id$")
    assert "SUPERADMIN" in IdentityService.role_codes(db, user.id)

    permissions = IdentityService.permission_codes(db, user.id)
    for code in ("usuarios.administrar", "roles.asignar", "warehouse.map.view", "system.settings.manage"):
        assert code in permissions

    original_hash = user.password_hash
    again, created_again = ensure_superadmin(db, "qa.maestro", "OtraInicialLote4")
    assert created_again is False
    assert again.id == user.id
    assert again.password_hash == original_hash


def test_administrador_no_puede_crear_superadministrador(client, db: Session) -> None:
    admin = auth_header(client)
    created = client.post(
        "/api/v1/admin/users",
        headers=admin,
        json={
            "username": "qa.objetivo",
            "email": "qa.objetivo@example.invalid",
            "full_name": "Objetivo sintético",
            "roles": [],
        },
    )
    assert created.status_code == 201, created.text
    target_id = created.json()["id"]

    escalated = client.post(
        f"/api/v1/admin/users/{target_id}/roles",
        headers=admin,
        json={"role_code": "SUPERADMIN", "scope_type": "GLOBAL"},
    )
    assert escalated.status_code == 403
    assert "superadministrador" in escalated.json()["detail"]
    assert "SUPERADMIN" not in IdentityService.role_codes(db, uuid.UUID(target_id))


def test_superadministrador_si_puede_asignar_roles_administrativos(client, db: Session) -> None:
    headers = _superadmin_headers(client, db)
    target = db.execute(select(AppUser).where(AppUser.username == "demo.solicitante")).scalar_one()
    response = client.post(
        f"/api/v1/admin/users/{target.id}/roles",
        headers=headers,
        json={"role_code": "SUPERADMIN", "scope_type": "GLOBAL"},
    )
    assert response.status_code == 200, response.text
    assert "SUPERADMIN" in response.json()["roles"]


def test_cambio_de_usuario_revoca_otras_sesiones_y_conserva_la_actual(client) -> None:
    login_with_cookie(client)
    current_csrf = login_with_cookie(client)
    before = client.get("/api/v1/auth/sessions", headers=current_csrf).json()
    assert len(before) >= 2

    changed = client.patch(
        "/api/v1/auth/username",
        headers=current_csrf,
        json={
            "username": "demo.admin.renombrado",
            "current_password": os.environ["DEMO_PASSWORD"],
        },
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["username"] == "demo.admin.renombrado"
    assert client.get("/api/v1/auth/me").status_code == 200

    after = client.get("/api/v1/auth/sessions", headers=current_csrf).json()
    assert len(after) == 1


def test_cambio_de_usuario_rechaza_nombre_duplicado(client) -> None:
    admin = auth_header(client)
    created = client.post(
        "/api/v1/admin/users",
        headers=admin,
        json={
            "username": "qa.ocupado",
            "email": "qa.ocupado@example.invalid",
            "full_name": "Usuario ocupado",
            "roles": ["SOLICITANTE"],
        },
    )
    assert created.status_code == 201, created.text

    csrf = login_with_cookie(client)
    response = client.patch(
        "/api/v1/auth/username",
        headers=csrf,
        json={"username": "qa.ocupado", "current_password": os.environ["DEMO_PASSWORD"]},
    )
    assert response.status_code == 409
    assert "ya está en uso" in response.json()["detail"]


def test_cuentas_duplicadas_no_se_crean_por_administracion(client) -> None:
    admin = auth_header(client)
    payload = {
        "username": "qa.duplicado",
        "email": "qa.duplicado.uno@example.invalid",
        "full_name": "Usuario sintético",
        "roles": ["SOLICITANTE"],
    }
    first = client.post("/api/v1/admin/users", headers=admin, json=payload)
    assert first.status_code == 201, first.text

    payload["email"] = "qa.duplicado.dos@example.invalid"
    second = client.post("/api/v1/admin/users", headers=admin, json=payload)
    assert second.status_code == 409
    assert "ya existe" in second.json()["detail"]


def test_bloqueo_temporal_tras_intentos_fallidos(client, db: Session) -> None:
    for _ in range(5):
        failed = client.post(
            "/api/v1/auth/login",
            json={"username": "demo.solicitante", "password": "ClaveIncorrecta123!"},
        )
        assert failed.status_code == 401

    user = db.execute(
        select(AppUser).where(AppUser.username == "demo.solicitante")
    ).scalar_one()
    assert user.status == "LOCKED"
    assert user.locked_until is not None

    blocked = client.post(
        "/api/v1/auth/login",
        json={"username": "demo.solicitante", "password": os.environ["DEMO_PASSWORD"]},
    )
    assert blocked.status_code == 401
    assert "bloqueada" in blocked.json()["detail"]


def test_ultimo_superadmin_no_puede_darse_de_baja(client, db: Session) -> None:
    user = ensure_superadmin(db, "qa.ultimo.sa", INITIAL_PASSWORD)[0]
    assert IdentityService.is_last_active_superadmin(db, user.id) is True
    admin = auth_header(client)

    deleted = client.delete(f"/api/v1/admin/users/{user.id}", headers=admin)
    assert deleted.status_code == 400
    assert "último superadministrador" in deleted.json()["detail"]

    disabled = client.patch(
        f"/api/v1/admin/users/{user.id}",
        headers=admin,
        json={"status": "INACTIVE"},
    )
    assert disabled.status_code == 400
    assert "último superadministrador" in disabled.json()["detail"]


def test_superadmin_accede_al_mapa_virtual(client, db: Session) -> None:
    headers = _superadmin_headers(client, db)
    warehouse_id = db.execute(
        select(Warehouse.id).where(Warehouse.code == "ALM_PRINCIPAL_DEMO")
    ).scalar_one()

    response = client.get(f"/api/v1/wms/maps/{warehouse_id}", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["is_exact"] is False
