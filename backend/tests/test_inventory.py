from __future__ import annotations

from decimal import Decimal

from tests.conftest import auth_header
from tests.test_requisitions import catalogs, create_requisition


def approved_requisition(client, quantities=(Decimal("10"), Decimal("3"))) -> tuple[dict, dict]:
    solicitante = auth_header(client, "demo.solicitante")
    catalog = catalogs(client, solicitante)
    created = create_requisition(client, solicitante, catalog, quantities)
    assert created.status_code == 201, created.text
    req_id = created.json()["id"]
    submitted = client.post(f"/api/v1/requisitions/{req_id}/submit", headers=solicitante)
    assert submitted.status_code == 200, submitted.text

    aprobador = auth_header(client, "demo.aprobador")
    decision = client.post(
        f"/api/v1/requisitions/{req_id}/decide",
        headers=aprobador,
        json={
            "decisions": [
                {
                    "requisition_line_id": line["id"],
                    "decision": "APPROVE",
                    "approved_qty": line["requested_qty"],
                }
                for line in submitted.json()["lines"]
            ]
        },
    )
    assert decision.status_code == 200, decision.text
    return decision.json(), catalog


def availability(client, headers, catalog):
    response = client.get(
        "/api/v1/inventory/availability",
        headers=headers,
        params={"item_id": catalog["items"][0], "warehouse_id": catalog["warehouse"]},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_reserva_no_descuenta_existencia(client):
    req, catalog = approved_requisition(client)
    almacenista = auth_header(client, "demo.almacenista")
    line_id = req["lines"][0]["id"]

    before = availability(client, almacenista, catalog)
    assert Decimal(before["on_hand_qty"]) == Decimal("120")
    assert Decimal(before["reserved_qty"]) == Decimal("0")

    response = client.post(
        "/api/v1/inventory/reservations",
        headers=almacenista,
        json={
            "requisition_line_id": line_id,
            "quantity": "6",
            "idempotency_key": "prueba-reserva-001",
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "ACTIVE"

    after = availability(client, almacenista, catalog)
    assert Decimal(after["on_hand_qty"]) == Decimal("120")
    assert Decimal(after["reserved_qty"]) == Decimal("6")
    assert Decimal(after["available_qty"]) == Decimal("114")


def test_entrega_parcial_descuenta_solo_al_confirmar(client):
    req, catalog = approved_requisition(client)
    almacenista = auth_header(client, "demo.almacenista")
    line_id = req["lines"][0]["id"]

    reserve = client.post(
        "/api/v1/inventory/reservations",
        headers=almacenista,
        json={
            "requisition_line_id": line_id,
            "quantity": "6",
            "idempotency_key": "prueba-reserva-002",
        },
    )
    assert reserve.status_code == 201, reserve.text
    assert Decimal(availability(client, almacenista, catalog)["on_hand_qty"]) == Decimal("120")

    issue_payload = {
        "requisition_line_id": line_id,
        "quantity": "4",
        "reservation_id": reserve.json()["id"],
        "idempotency_key": "prueba-entrega-002",
    }
    issue = client.post("/api/v1/inventory/issues", headers=almacenista, json=issue_payload)
    assert issue.status_code == 201, issue.text
    assert issue.json()["movement_type"] == "ISSUE"
    assert issue.json()["direction"] == "OUT"
    assert Decimal(issue.json()["balance_after_qty"]) == Decimal("116")

    after = availability(client, almacenista, catalog)
    assert Decimal(after["on_hand_qty"]) == Decimal("116")
    assert Decimal(after["reserved_qty"]) == Decimal("2")

    detail = client.get(
        f"/api/v1/requisitions/{req['id']}", headers=almacenista
    ).json()
    assert Decimal(detail["lines"][0]["delivered_qty"]) == Decimal("4")
    assert Decimal(detail["lines"][0]["pending_qty"]) == Decimal("6")


def test_sobreentrega_bloqueada(client):
    req, catalog = approved_requisition(client)
    almacenista = auth_header(client, "demo.almacenista")
    line_id = req["lines"][0]["id"]

    reserve = client.post(
        "/api/v1/inventory/reservations",
        headers=almacenista,
        json={
            "requisition_line_id": line_id,
            "quantity": "5",
            "idempotency_key": "prueba-reserva-003",
        },
    )
    assert reserve.status_code == 201, reserve.text

    over_issue = client.post(
        "/api/v1/inventory/issues",
        headers=almacenista,
        json={
            "requisition_line_id": line_id,
            "quantity": "6",
            "reservation_id": reserve.json()["id"],
            "idempotency_key": "prueba-entrega-003",
        },
    )
    assert over_issue.status_code == 409
    assert Decimal(availability(client, almacenista, catalog)["on_hand_qty"]) == Decimal("120")


def test_idempotencia_evita_movimiento_duplicado(client):
    req, catalog = approved_requisition(client)
    almacenista = auth_header(client, "demo.almacenista")
    line_id = req["lines"][0]["id"]

    reserve = client.post(
        "/api/v1/inventory/reservations",
        headers=almacenista,
        json={
            "requisition_line_id": line_id,
            "quantity": "4",
            "idempotency_key": "prueba-reserva-004",
        },
    )
    payload = {
        "requisition_line_id": line_id,
        "quantity": "4",
        "reservation_id": reserve.json()["id"],
        "idempotency_key": "prueba-entrega-004",
    }
    first = client.post("/api/v1/inventory/issues", headers=almacenista, json=payload)
    second = client.post("/api/v1/inventory/issues", headers=almacenista, json=payload)
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["id"] == second.json()["id"]

    movements = client.get(
        "/api/v1/inventory/kardex",
        headers=almacenista,
        params={"item_id": catalog["items"][0]},
    ).json()
    # El esquema público no expone idempotency_key; se valida que solo exista un ISSUE.
    issue_movs = [mov for mov in movements if mov["movement_type"] == "ISSUE"]
    assert len(issue_movs) == 1


def test_cantidad_negativa_rechazada(client):
    req, catalog = approved_requisition(client)
    almacenista = auth_header(client, "demo.almacenista")

    response = client.post(
        "/api/v1/inventory/reservations",
        headers=almacenista,
        json={
            "requisition_line_id": req["lines"][0]["id"],
            "quantity": "-1",
            "idempotency_key": "prueba-negativa",
        },
    )
    assert response.status_code == 422
    assert Decimal(availability(client, almacenista, catalog)["reserved_qty"]) == Decimal("0")


def test_kardex_registra_entrada_inicial_y_salida(client):
    req, catalog = approved_requisition(client)
    almacenista = auth_header(client, "demo.almacenista")
    line_id = req["lines"][0]["id"]

    reserve = client.post(
        "/api/v1/inventory/reservations",
        headers=almacenista,
        json={
            "requisition_line_id": line_id,
            "quantity": "3",
            "idempotency_key": "prueba-reserva-005",
        },
    )
    assert reserve.status_code == 201, reserve.text
    client.post(
        "/api/v1/inventory/issues",
        headers=almacenista,
        json={
            "requisition_line_id": line_id,
            "quantity": "3",
            "reservation_id": reserve.json()["id"],
            "idempotency_key": "prueba-entrega-005",
        },
    )

    kardex = client.get(
        "/api/v1/inventory/kardex",
        headers=almacenista,
        params={"item_id": catalog["items"][0]},
    )
    assert kardex.status_code == 200, kardex.text
    types = [mov["movement_type"] for mov in kardex.json()]
    assert "INITIAL" in types
    assert "ISSUE" in types
