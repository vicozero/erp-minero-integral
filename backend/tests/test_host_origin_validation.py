from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import clear_session, login_with_cookie


def test_host_no_permitido_se_rechaza(client: TestClient) -> None:
    response = client.get("/health", headers={"host": "evil.example.invalid"})
    assert response.status_code == 400
    assert response.json()["detail"] == "Host no permitido"


def test_origen_no_permitido_se_rechaza_en_escritura(client: TestClient) -> None:
    csrf = login_with_cookie(client)
    try:
        response = client.post(
            "/api/v1/auth/logout",
            headers={**csrf, "origin": "https://evil.example.invalid"},
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "Origen no permitido"
    finally:
        clear_session(client)


def test_host_y_origen_locales_son_aceptados(client: TestClient) -> None:
    response = client.get(
        "/health",
        headers={"host": "127.0.0.1:8080", "origin": "http://127.0.0.1:8080"},
    )
    assert response.status_code == 200
