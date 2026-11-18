from __future__ import annotations

from decimal import Decimal

from tests.conftest import auth_header
from tests.test_inventory import approved_requisition, availability
from tests.test_requisitions import catalogs, create_requisition


def create_po(client, headers, catalog, requisition_id, notes="Compra de prueba"):
    return client.post(
        "/api/v1/purchases/from-shortages",
        headers=headers,
        json={
            "requisition_id": requisition_id,
            "supplier_id": catalog["supplier"],
            "warehouse_id": catalog["warehouse"],
            "notes": notes,
        },
    )


def test_no_genera_oc_sin_requisicion_autorizada(client):
    solicitante = auth_header(client, "demo.solicitante")
    catalog = catalogs(client, solicitante)
    created = create_requisition(client, solicitante, catalog)
    assert created.status_code == 201, created.text

    comprador = auth_header(client, "demo.comprador")
    response = create_po(client, comprador, catalog, created.json()["id"])
    assert response.status_code == 409


def test_oc_por_faltantes_aprobacion_y_recepciones_parciales(client):
    req, catalog = approved_requisition(client)
    comprador = auth_header(client, "demo.comprador")

    created = create_po(client, comprador, catalog, req["id"])
    assert created.status_code == 201, created.text
    po = created.json()
    assert po["status"] == "DRAFT"
    assert len(po["lines"]) == 2
    assert Decimal(po["lines"][0]["ordered_qty"]) == Decimal("10")
    assert Decimal(po["lines"][1]["ordered_qty"]) == Decimal("3")

    approved = client.post(
        f"/api/v1/purchases/{po['id']}/approve", headers=comprador
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "APPROVED"

    repeated = client.post(
        f"/api/v1/purchases/{po['id']}/approve", headers=comprador
    )
    assert repeated.status_code == 409

    first_line = po["lines"][0]["id"]
    partial = client.post(
        f"/api/v1/purchases/{po['id']}/receive",
        headers=comprador,
        json={
            "lines": [{"purchase_order_line_id": first_line, "quantity": "4"}],
            "idempotency_key": "grn-parcial-001",
        },
    )
    assert partial.status_code == 201, partial.text
    assert Decimal(availability(client, comprador, catalog)["on_hand_qty"]) == Decimal("124")

    po_after_partial = client.get(
        f"/api/v1/purchases/{po['id']}", headers=comprador
    ).json()
    assert po_after_partial["status"] == "PARTIALLY_RECEIVED"
    assert Decimal(po_after_partial["lines"][0]["received_qty"]) == Decimal("4")

    second_line = po["lines"][1]["id"]
    final = client.post(
        f"/api/v1/purchases/{po['id']}/receive",
        headers=comprador,
        json={
            "lines": [
                {"purchase_order_line_id": first_line, "quantity": "6"},
                {"purchase_order_line_id": second_line, "quantity": "3"},
            ],
            "idempotency_key": "grn-final-001",
        },
    )
    assert final.status_code == 201, final.text
    assert Decimal(availability(client, comprador, catalog)["on_hand_qty"]) == Decimal("130")

    po_final = client.get(f"/api/v1/purchases/{po['id']}", headers=comprador).json()
    assert po_final["status"] == "RECEIVED"
    assert Decimal(po_final["lines"][0]["received_qty"]) == Decimal("10")
    assert Decimal(po_final["lines"][1]["received_qty"]) == Decimal("3")

    detail = client.get(
        f"/api/v1/requisitions/{req['id']}", headers=comprador
    ).json()
    assert Decimal(detail["lines"][0]["purchased_qty"]) == Decimal("10")
    assert Decimal(detail["lines"][0]["received_qty"]) == Decimal("10")


def test_recepcion_duplicada_no_genera_nuevo_kardex(client):
    req, catalog = approved_requisition(client)
    comprador = auth_header(client, "demo.comprador")
    po = create_po(client, comprador, catalog, req["id"]).json()
    client.post(f"/api/v1/purchases/{po['id']}/approve", headers=comprador)

    payload = {
        "lines": [
            {
                "purchase_order_line_id": po["lines"][0]["id"],
                "quantity": "5",
            }
        ],
        "idempotency_key": "grn-duplicado-001",
    }
    first = client.post(
        f"/api/v1/purchases/{po['id']}/receive", headers=comprador, json=payload
    )
    second = client.post(
        f"/api/v1/purchases/{po['id']}/receive", headers=comprador, json=payload
    )
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["id"] == second.json()["id"]

    assert Decimal(availability(client, comprador, catalog)["on_hand_qty"]) == Decimal("125")
    po_after = client.get(f"/api/v1/purchases/{po['id']}", headers=comprador).json()
    assert Decimal(po_after["lines"][0]["received_qty"]) == Decimal("5")


def test_sobre_recepcion_y_cantidad_negativa_bloqueadas(client):
    req, catalog = approved_requisition(client)
    comprador = auth_header(client, "demo.comprador")
    po = create_po(client, comprador, catalog, req["id"]).json()
    client.post(f"/api/v1/purchases/{po['id']}/approve", headers=comprador)
    line_id = po["lines"][0]["id"]

    over = client.post(
        f"/api/v1/purchases/{po['id']}/receive",
        headers=comprador,
        json={
            "lines": [{"purchase_order_line_id": line_id, "quantity": "11"}],
            "idempotency_key": "grn-sobre-001",
        },
    )
    assert over.status_code == 409

    negative = client.post(
        f"/api/v1/purchases/{po['id']}/receive",
        headers=comprador,
        json={
            "lines": [{"purchase_order_line_id": line_id, "quantity": "-1"}],
            "idempotency_key": "grn-negativo-001",
        },
    )
    assert negative.status_code == 422
    assert Decimal(availability(client, comprador, catalog)["on_hand_qty"]) == Decimal("120")


def test_recepcion_permitecompletar_entrega_pendiente(client):
    solicitante = auth_header(client, "demo.solicitante")
    catalog = catalogs(client, solicitante)
    created = create_requisition(
        client,
        solicitante,
        catalog,
        quantities=(Decimal("150"), Decimal("1")),
    )
    req_id = created.json()["id"]
    client.post(f"/api/v1/requisitions/{req_id}/submit", headers=solicitante)

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
                for line in created.json()["lines"]
            ]
        },
    )
    assert decision.status_code == 200, decision.text
    req = decision.json()

    almacenista = auth_header(client, "demo.almacenista")
    sin_stock = client.post(
        "/api/v1/inventory/reservations",
        headers=almacenista,
        json={
            "requisition_line_id": req["lines"][0]["id"],
            "quantity": "150",
            "idempotency_key": "reserva-sin-stock",
        },
    )
    assert sin_stock.status_code == 409

    comprador = auth_header(client, "demo.comprador")
    po = create_po(client, comprador, catalog, req_id).json()
    client.post(f"/api/v1/purchases/{po['id']}/approve", headers=comprador)
    receipt = client.post(
        f"/api/v1/purchases/{po['id']}/receive",
        headers=comprador,
        json={
            "lines": [
                {
                    "purchase_order_line_id": po["lines"][0]["id"],
                    "quantity": "150",
                }
            ],
            "idempotency_key": "grn-habilita-entrega",
        },
    )
    assert receipt.status_code == 201, receipt.text

    reserve = client.post(
        "/api/v1/inventory/reservations",
        headers=almacenista,
        json={
            "requisition_line_id": req["lines"][0]["id"],
            "quantity": "150",
            "idempotency_key": "reserva-con-stock",
        },
    )
    assert reserve.status_code == 201, reserve.text
    issue = client.post(
        "/api/v1/inventory/issues",
        headers=almacenista,
        json={
            "requisition_line_id": req["lines"][0]["id"],
            "quantity": "150",
            "reservation_id": reserve.json()["id"],
            "idempotency_key": "entrega-final",
        },
    )
    assert issue.status_code == 201, issue.text
    assert Decimal(availability(client, almacenista, catalog)["on_hand_qty"]) == Decimal("120")
