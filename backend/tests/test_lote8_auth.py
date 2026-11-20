from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.identity.models import AppUser
from tests.conftest import clear_session, login_with_cookie

_ALGORITHM = "HS256"
_NEW_PASSWORD = "Lote8Nueva_2026!"


def _login_token(client: TestClient, username: str = "demo.admin") -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": os.environ["DEMO_PASSWORD"]},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _claims(token: str) -> dict:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[_ALGORITHM], options={"verify_exp": False})


def _resign(payload: dict) -> str:
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=_ALGORITHM)


def test_logout_revoca_el_bearer_de_la_misma_sesion(client: TestClient) -> None:
    token = _login_token(client)
    headers = _bearer(token)
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200

    logout = client.post("/api/v1/auth/logout", headers=headers)
    assert logout.status_code == 204, logout.text

    denied = client.get("/api/v1/auth/me", headers=headers)
    assert denied.status_code == 401
    assert "Sesión revocada" in denied.json()["detail"]


def test_cambio_de_contrasena_revoca_el_bearer_anterior(client: TestClient) -> None:
    old_token = _login_token(client)
    old_headers = _bearer(old_token)

    changed = client.post(
        "/api/v1/auth/change-password",
        headers=old_headers,
        json={"current_password": os.environ["DEMO_PASSWORD"], "new_password": _NEW_PASSWORD},
    )
    assert changed.status_code == 200, changed.text
    assert client.get("/api/v1/auth/me", headers=old_headers).status_code == 401

    new_headers = _bearer(changed.json()["access_token"])
    assert client.get("/api/v1/auth/me", headers=new_headers).status_code == 200


def test_token_vencido_es_rechazado(client: TestClient) -> None:
    payload = _claims(_login_token(client))
    payload["exp"] = int(time.time()) - 10
    response = client.get("/api/v1/auth/me", headers=_bearer(_resign(payload)))
    assert response.status_code == 401
    assert "expirado" in response.json()["detail"]


def test_token_con_sesion_ajena_es_rechazado(client: TestClient) -> None:
    admin_claims = _claims(_login_token(client, "demo.admin"))
    other_claims = _claims(_login_token(client, "demo.solicitante"))
    forged = dict(admin_claims)
    forged["sid"] = other_claims["sid"]
    forged["cred"] = other_claims["cred"]

    response = client.get("/api/v1/auth/me", headers=_bearer(_resign(forged)))
    assert response.status_code == 401


def test_token_con_credencial_modificada_es_rechazado(client: TestClient) -> None:
    payload = _claims(_login_token(client))
    payload["cred"] = payload["cred"] + 1
    response = client.get("/api/v1/auth/me", headers=_bearer(_resign(payload)))
    assert response.status_code == 401


def test_token_sin_sesion_no_es_aceptado(client: TestClient) -> None:
    payload = _claims(_login_token(client))
    payload.pop("sid")
    response = client.get("/api/v1/auth/me", headers=_bearer(_resign(payload)))
    assert response.status_code == 401


def test_escalada_de_privilegios_con_bearer_es_rechazada(client: TestClient) -> None:
    headers = _bearer(_login_token(client, "demo.solicitante"))
    response = client.post(
        "/api/v1/admin/users",
        headers=headers,
        json={
            "username": "lote8.sin.permiso",
            "email": "lote8.sin.permiso@example.invalid",
            "full_name": "Escalada denegada",
            "roles": ["ADMIN"],
        },
    )
    assert response.status_code == 403


def test_host_con_puerto_no_autorizado_se_rechaza(client: TestClient) -> None:
    response = client.get("/health", headers={"host": "127.0.0.1:9999"})
    assert response.status_code == 400
    assert response.json()["detail"] == "Host no permitido"


def test_origen_mismo_host_con_otro_puerto_se_rechaza(client: TestClient) -> None:
    response = client.get(
        "/health",
        headers={"host": "127.0.0.1:8080", "origin": "http://127.0.0.1:9999"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Origen no permitido"


def test_origen_https_sobre_http_se_rechaza(client: TestClient) -> None:
    response = client.get(
        "/health",
        headers={"host": "127.0.0.1:8080", "origin": "https://127.0.0.1:8080"},
    )
    assert response.status_code == 403


def test_proxy_local_reenvia_host_y_origen_del_portal(client: TestClient) -> None:
    """El portal en :8080 usa Host interno :8000 y reenvía el origen real."""
    proxy_headers = {
        "host": "127.0.0.1:8000",
        "x-forwarded-host": "127.0.0.1:8080",
        "x-forwarded-proto": "http",
        "origin": "http://127.0.0.1:8080",
    }
    assert client.get("/health", headers=proxy_headers).status_code == 200

    csrf = login_with_cookie(client, headers=proxy_headers)
    try:
        response = client.post("/api/v1/auth/logout", headers=csrf)
        assert response.status_code == 204, response.text
    finally:
        clear_session(client)


def test_forwarded_host_no_autorizado_se_rechaza(client: TestClient) -> None:
    response = client.get(
        "/health",
        headers={
            "host": "127.0.0.1:8000",
            "x-forwarded-host": "127.0.0.1:9999",
            "x-forwarded-proto": "http",
            "origin": "http://127.0.0.1:9999",
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Host no permitido"


def test_origen_distinto_al_forwarded_host_se_rechaza(client: TestClient) -> None:
    response = client.get(
        "/health",
        headers={
            "host": "127.0.0.1:8000",
            "x-forwarded-host": "127.0.0.1:8080",
            "x-forwarded-proto": "http",
            "origin": "http://127.0.0.1:9999",
        },
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Origen no permitido"


def test_origen_mismo_origen_y_cookie_valida(client: TestClient) -> None:
    csrf = login_with_cookie(client)
    try:
        response = client.post(
            "/api/v1/auth/logout",
            headers={**csrf, "origin": "http://testserver"},
        )
        assert response.status_code == 204, response.text
    finally:
        clear_session(client)


def test_cookie_con_credencial_modificada_es_rechazado(client: TestClient, db: Session) -> None:
    """Una cookie creada antes de un cambio de credencial no debe autorizar."""
    login_with_cookie(client)
    try:
        assert client.get("/api/v1/auth/me").status_code == 200
        user = db.execute(select(AppUser).where(AppUser.username == "demo.admin")).scalar_one()
        user.password_changed_at = datetime.now(timezone.utc) + timedelta(seconds=5)
        db.flush()
        denied = client.get("/api/v1/auth/me")
        assert denied.status_code == 401
        assert "credencial" in denied.json()["detail"]
    finally:
        clear_session(client)


def test_host_proxy_confiable_es_configurable(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(
        settings,
        "ALLOWED_HOSTS",
        "127.0.0.1,localhost,testserver,127.0.0.1:9000,127.0.0.1:8080",
    )
    monkeypatch.setattr(settings, "TRUSTED_PROXY_HOSTS", "127.0.0.1:9000")
    response = client.get(
        "/health",
        headers={
            "host": "127.0.0.1:9000",
            "x-forwarded-host": "127.0.0.1:8080",
            "x-forwarded-proto": "http",
            "origin": "http://127.0.0.1:8080",
        },
    )
    assert response.status_code == 200, response.text


def test_preflight_cors_permite_authorization(client: TestClient) -> None:
    response = client.options(
        "/api/v1/auth/me",
        headers={
            "host": "127.0.0.1:5173",
            "origin": "http://127.0.0.1:5173",
            "access-control-request-method": "GET",
            "access-control-request-headers": "authorization",
        },
    )
    assert response.status_code == 200, response.text
    assert "authorization" in response.headers.get("access-control-allow-headers", "").lower()
