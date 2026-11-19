from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditLog
from app.modules.identity.models import AppUser, LoginAudit
from app.modules.identity.service import IdentityService
from app.modules.organization.models import Department
from tests.conftest import auth_header, clear_session, login_with_cookie

NEW_PASSWORD = "SeguroFase3_2026!"


def _catalog(client, headers):
    response = client.get("/api/v1/catalogs", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _requisition_payload(catalog: dict, department_id: uuid.UUID) -> dict:
    uoms = {row["code"]: row["id"] for row in catalog["uoms"]}
    return {
        "department_id": str(department_id),
        "warehouse_id": catalog["warehouses"][0]["id"],
        "equipment_id": catalog["equipment"][0]["id"],
        "cost_center_id": catalog["cost_centers"][0]["id"],
        "requisition_type": "STOCK",
        "priority": "NORMAL",
        "justification": "Prueba sintética de Fase 3",
        "lines": [
            {
                "item_id": catalog["items"][0]["id"],
                "description": "Tornillo sintético",
                "uom_id": uoms["UND"],
                "requested_qty": "2",
            }
        ],
    }


def _create_requisition(client, headers, department_id: uuid.UUID) -> str:
    created = client.post(
        "/api/v1/requisitions",
        headers=headers,
        json=_requisition_payload(_catalog(client, headers), department_id),
    )
    assert created.status_code == 201, created.text
    return created.json()["id"]


# 1 ---------------------------------------------------------------------
def test_login_valido_devuelve_sesion_y_cookies(client, db: Session) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "demo.admin", "password": os.environ["DEMO_PASSWORD"]},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["user"]["username"] == "demo.admin"
    assert body["csrf_token"]
    assert body["must_change_password"] is False
    set_cookies = " ".join(response.headers.get_list("set-cookie"))
    assert "erp_session=" in set_cookies
    assert "HttpOnly" in set_cookies
    assert "SameSite=lax" in set_cookies
    assert db.execute(
        select(LoginAudit).where(LoginAudit.success.is_(True), LoginAudit.user_id == body["user"]["id"])
    ).first() is not None


# 2 ---------------------------------------------------------------------
def test_contrasena_incorrecta_no_registra_secreto(client, db: Session) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "demo.admin", "password": "NoEsLaContrasena123!"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Credenciales inválidas."
    failures = db.execute(
        select(LoginAudit).where(LoginAudit.success.is_(False)).order_by(LoginAudit.occurred_at.desc())
    ).scalars()
    latest = next(iter(failures))
    assert latest.reason == "CREDENCIALES_INVALIDAS"
    assert (latest.detail if hasattr(latest, "detail") else None) is None
    assert "NoEsLaContrasena123!" not in str(latest.reason)


# 3 ---------------------------------------------------------------------
def test_usuario_inactivo_no_puede_entrar(client, db: Session) -> None:
    user = db.execute(select(AppUser).where(AppUser.username == "demo.solicitante")).scalar_one()
    user.status = "INACTIVE"
    db.flush()
    clear_session(client)
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "demo.solicitante", "password": os.environ["DEMO_PASSWORD"]},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "La cuenta está inactiva."
    reason = db.execute(
        select(LoginAudit.reason).where(LoginAudit.user_id == user.id).order_by(LoginAudit.occurred_at.desc())
    ).scalar_one()
    assert reason == "USUARIO_INACTIVO"


# 4 ---------------------------------------------------------------------
def test_cambio_obligatorio_de_contrasena_inicial(client) -> None:
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "demo.temporal", "password": os.environ["DEMO_PASSWORD"]},
    )
    assert login.status_code == 200, login.text
    assert login.json()["must_change_password"] is True
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    blocked = client.get("/api/v1/catalogs", headers=headers)
    assert blocked.status_code == 403
    assert "contraseña temporal" in blocked.json()["detail"]

    changed = client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"current_password": os.environ["DEMO_PASSWORD"], "new_password": NEW_PASSWORD},
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["must_change_password"] is False
    new_headers = {"Authorization": f"Bearer {changed.json()['access_token']}"}
    assert client.get("/api/v1/catalogs", headers=new_headers).status_code == 200


# 5 ---------------------------------------------------------------------
def test_sesion_revocada_deja_de_ser_valida(client) -> None:
    csrf = login_with_cookie(client)
    sessions = client.get("/api/v1/auth/sessions", headers=csrf)
    assert sessions.status_code == 200, sessions.text
    session_id = sessions.json()[0]["id"]
    revoked = client.post(f"/api/v1/auth/sessions/{session_id}/revoke", headers=csrf)
    assert revoked.status_code == 204, revoked.text
    assert client.get("/api/v1/auth/me").status_code == 401


# 6 ---------------------------------------------------------------------
def test_acceso_sin_sesion_es_rechazado(client) -> None:
    clear_session(client)
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/catalogs").status_code == 401
    assert client.get("/api/v1/audit").status_code == 401


# 7 ---------------------------------------------------------------------
def test_permisos_insuficientes_para_administrar(client) -> None:
    solicitante = auth_header(client, "demo.solicitante")
    response = client.post(
        "/api/v1/admin/users",
        headers=solicitante,
        json={
            "username": "qa.sin.permiso",
            "email": "qa.sin.permiso@example.invalid",
            "full_name": "Intento sin permiso",
            "roles": ["SOLICITANTE"],
        },
    )
    assert response.status_code == 403
    assert "usuarios.administrar" in response.json()["detail"]


# 8 ---------------------------------------------------------------------
def test_acceso_entre_departamentos_no_autorizados(client, db: Session) -> None:
    admin = auth_header(client, "demo.admin")
    other = db.execute(select(Department).where(Department.code == "DEMO-OTRA")).scalar_one()
    req_id = _create_requisition(client, admin, other.id)
    client.post(f"/api/v1/requisitions/{req_id}/submit", headers=admin)

    solicitante = auth_header(client, "demo.solicitante")
    detail = client.get(f"/api/v1/requisitions/{req_id}", headers=solicitante)
    assert detail.status_code == 403
    listing = client.get("/api/v1/requisitions", headers=solicitante).json()
    assert req_id not in [row["id"] for row in listing]


# 9 ---------------------------------------------------------------------
def test_usuario_con_varios_roles_acumula_permisos(client, db: Session) -> None:
    admin = auth_header(client, "demo.admin")
    user = db.execute(select(AppUser).where(AppUser.username == "demo.solicitante")).scalar_one()
    assigned = client.post(
        f"/api/v1/admin/users/{user.id}/roles",
        headers=admin,
        json={"role_code": "AUDITOR", "scope_type": "GLOBAL"},
    )
    assert assigned.status_code == 200, assigned.text
    assert {"SOLICITANTE", "AUDITOR"} <= set(assigned.json()["roles"])
    assert "auditoria.consultar" in assigned.json()["permissions"]
    assert client.get("/api/v1/audit", headers=admin).status_code == 200


# 10 ---------------------------------------------------------------------
def test_impide_autoautorizacion_de_requisicion(client, db: Session) -> None:
    admin = auth_header(client, "demo.admin")
    department = db.execute(select(Department).where(Department.code == "DEMO-MINA")).scalar_one()
    req_id = _create_requisition(client, admin, department.id)
    client.post(f"/api/v1/requisitions/{req_id}/submit", headers=admin)
    response = client.post(
        f"/api/v1/requisitions/{req_id}/decide",
        headers=admin,
        json={"decisions": [], "reason": "Intento de autoautorización"},
    )
    assert response.status_code == 403
    assert "propia requisición" in response.json()["detail"]


# 11 ---------------------------------------------------------------------
def test_impide_escalada_de_privilegios(client, db: Session) -> None:
    user = db.execute(select(AppUser).where(AppUser.username == "demo.solicitante")).scalar_one()
    solicitante = auth_header(client, "demo.solicitante")
    response = client.post(
        f"/api/v1/admin/users/{user.id}/roles",
        headers=solicitante,
        json={"role_code": "ADMIN", "scope_type": "GLOBAL"},
    )
    assert response.status_code == 403
    roles = IdentityService.role_codes(db, user.id)
    assert "ADMIN" not in roles


# 12 ---------------------------------------------------------------------
def test_modificacion_de_roles_sin_autorizacion(client, db: Session) -> None:
    user = db.execute(select(AppUser).where(AppUser.username == "demo.aprobador")).scalar_one()
    solicitante = auth_header(client, "demo.solicitante")
    response = client.delete(
        f"/api/v1/admin/users/{user.id}/roles/APROBADOR",
        headers=solicitante,
    )
    assert response.status_code == 403
    assert "APROBADOR" in IdentityService.role_codes(db, user.id)


# 13 ---------------------------------------------------------------------
def test_cambios_sensibles_quedan_en_auditoria(client, db: Session) -> None:
    admin = auth_header(client, "demo.admin")
    response = client.post(
        "/api/v1/admin/users",
        headers=admin,
        json={
            "username": "qa.auditado",
            "email": "qa.auditado@example.invalid",
            "full_name": "Usuario sintético auditado",
            "roles": ["SOLICITANTE"],
        },
    )
    assert response.status_code == 201, response.text
    entry = db.execute(
        select(AuditLog).where(AuditLog.action == "USER_CREATED").order_by(AuditLog.occurred_at.desc())
    ).scalar_one()
    assert entry.actor_username == "demo.admin"
    assert entry.entity_id == uuid.UUID(response.json()["id"])
    assert entry.before_json is None
    with pytest.raises(Exception):
        with db.begin_nested():
            db.execute(select(AuditLog).where(AuditLog.id == entry.id))
            db.execute(
                AuditLog.__table__.update()
                .where(AuditLog.id == entry.id)
                .values(detail="modificado")
            )


# 14 ---------------------------------------------------------------------
def test_restablecimiento_seguro_de_contrasena(client, db: Session) -> None:
    admin = auth_header(client, "demo.admin")
    user = db.execute(select(AppUser).where(AppUser.username == "demo.solicitante")).scalar_one()
    response = client.post(
        f"/api/v1/admin/users/{user.id}/reset-password",
        headers=admin,
        json={"reason": "Solicitud sintética de restablecimiento"},
    )
    assert response.status_code == 200, response.text
    temporary = response.json()["temporary_password"]
    assert temporary != os.environ["DEMO_PASSWORD"]

    clear_session(client)
    old = client.post(
        "/api/v1/auth/login",
        json={"username": "demo.solicitante", "password": os.environ["DEMO_PASSWORD"]},
    )
    assert old.status_code == 401
    fresh = client.post(
        "/api/v1/auth/login",
        json={"username": "demo.solicitante", "password": temporary},
    )
    assert fresh.status_code == 200, fresh.text
    assert fresh.json()["must_change_password"] is True
    audit = db.execute(
        select(AuditLog).where(AuditLog.action == "PASSWORD_RESET").order_by(AuditLog.occurred_at.desc())
    ).scalar_one()
    assert temporary not in str(audit.after_json)
    assert temporary not in str(audit.detail)


# 15 ---------------------------------------------------------------------
def test_proteccion_csrf_en_operaciones_con_cookies(client) -> None:
    csrf = login_with_cookie(client)
    without_token = client.post("/api/v1/auth/logout")
    assert without_token.status_code == 403
    assert "CSRF" in without_token.json()["detail"]
    with_token = client.post("/api/v1/auth/logout", headers=csrf)
    assert with_token.status_code == 204, with_token.text
    assert client.get("/api/v1/auth/me").status_code == 401


# 16 ---------------------------------------------------------------------
def test_no_acceso_a_registro_ajeno_por_identificador(client, db: Session) -> None:
    admin = auth_header(client, "demo.admin")
    other = db.execute(select(Department).where(Department.code == "DEMO-OTRA")).scalar_one()
    req_id = _create_requisition(client, admin, other.id)
    solicitante = auth_header(client, "demo.solicitante")
    response = client.get(f"/api/v1/requisitions/{req_id}", headers=solicitante)
    assert response.status_code == 403
    assert response.json()["detail"] == "No tiene acceso a registros de ese departamento."
