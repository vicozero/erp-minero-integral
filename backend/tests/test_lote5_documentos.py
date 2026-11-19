"""Pruebas del Lote 5: firmas nominales, tablero SLA y cadena documental.

Todas se ejecutan sobre PostgreSQL real y dentro de transacciones revertibles.
Ninguna descarga o consulta debe generar movimientos de inventario.
"""

from __future__ import annotations

import io
from decimal import Decimal

import fitz
from openpyxl import load_workbook

from tests.conftest import auth_header
from tests.test_documentation import _draft_payload, _kardex_count
from tests.test_inventory import approved_requisition
from tests.test_requisitions import catalogs


def test_firmas_nominales_se_imprimen_sin_falsificar_grafia(client) -> None:
    almacenista = auth_header(client, "demo.almacenista")
    catalog = catalogs(client, almacenista)
    created = client.post(
        "/api/v1/documents/vouchers",
        headers=almacenista,
        json=_draft_payload(catalog, "lote5-firmas-001"),
    )
    assert created.status_code == 201, created.text
    voucher_id = created.json()["id"]
    before = _kardex_count(client, almacenista, catalog["items"][0])

    original_pdf = client.get(f"/api/v1/documents/vouchers/{voucher_id}/pdf", headers=almacenista)
    assert original_pdf.status_code == 200

    signed = client.post(
        f"/api/v1/documents/vouchers/{voucher_id}/signatures",
        headers=almacenista,
        json={
            "received_by_name": "RECEPCION SINTETICA",
            "authorized_by_name": "AUTORIZACION SINTETICA",
            "dispatched_by_name": "DESPACHO SINTETICO",
        },
    )
    assert signed.status_code == 200, signed.text
    body = signed.json()
    assert body["received_by_name"] == "RECEPCION SINTETICA"
    assert body["authorized_by_name"] == "AUTORIZACION SINTETICA"
    assert body["dispatched_by_name"] == "DESPACHO SINTETICO"
    assert body["signatures_recorded_at"] is not None

    fresh_pdf = client.get(f"/api/v1/documents/vouchers/{voucher_id}/pdf", headers=almacenista)
    assert fresh_pdf.status_code == 200
    assert fresh_pdf.content != original_pdf.content
    doc = fitz.open(stream=fresh_pdf.content, filetype="pdf")
    try:
        text = doc[0].get_text()
        assert "RECEPCION SINTETICA" in text
        assert "AUTORIZACION SINTETICA" in text
        assert "DESPACHO SINTETICO" in text
    finally:
        doc.close()

    xlsx = client.get(f"/api/v1/documents/vouchers/{voucher_id}/xlsx", headers=almacenista)
    assert xlsx.status_code == 200
    wb = load_workbook(io.BytesIO(xlsx.content))
    try:
        ws = wb["VA 1"]
        assert ws["A23"].value == "RECEPCION SINTETICA"
        assert ws["D23"].value == "AUTORIZACION SINTETICA"
        assert ws["G23"].value == "DESPACHO SINTETICO"
    finally:
        wb.close()

    # La reimpresión conserva bytes de la última versión original: no reescribe
    # constancias ni fabrica una nueva firma.
    reprint = client.get(
        f"/api/v1/documents/vouchers/{voucher_id}/pdf",
        headers=almacenista,
        params={"reprint": "true"},
    )
    assert reprint.status_code == 200
    assert reprint.content == fresh_pdf.content
    assert _kardex_count(client, almacenista, catalog["items"][0]) == before


def test_firmas_rechazan_payload_vacio_y_rol_sin_permiso(client) -> None:
    almacenista = auth_header(client, "demo.almacenista")
    catalog = catalogs(client, almacenista)
    created = client.post(
        "/api/v1/documents/vouchers",
        headers=almacenista,
        json=_draft_payload(catalog, "lote5-firmas-002"),
    )
    assert created.status_code == 201, created.text
    voucher_id = created.json()["id"]

    empty = client.post(
        f"/api/v1/documents/vouchers/{voucher_id}/signatures",
        headers=almacenista,
        json={},
    )
    assert empty.status_code == 422

    solicitante = auth_header(client, "demo.solicitante")
    denied = client.post(
        f"/api/v1/documents/vouchers/{voucher_id}/signatures",
        headers=solicitante,
        json={"received_by_name": "INTENTO SIN PERMISO"},
    )
    assert denied.status_code == 403

    unchanged = client.get(f"/api/v1/documents/vouchers/{voucher_id}", headers=almacenista)
    assert unchanged.json()["received_by_name"] is None


def test_tablero_sla_expone_campos_y_filtros(client) -> None:
    admin = auth_header(client, "demo.admin")
    req, catalog = approved_requisition(client)

    response = client.get("/api/v1/sla/requisitions", headers=admin)
    assert response.status_code == 200, response.text
    rows = response.json()
    assert any(row["id"] == req["id"] for row in rows)
    row = next(item for item in rows if item["id"] == req["id"])
    for field in (
        "department_name",
        "department_code",
        "equipment",
        "responsible",
        "administrative_status",
        "pending_days",
        "fulfillment_percent",
    ):
        assert field in row, field
    assert row["administrative_status"] == req["status"]
    assert row["responsible"]
    assert Decimal(row["fulfillment_percent"]) >= 0

    filtered = client.get(
        "/api/v1/sla/requisitions",
        headers=admin,
        params={"department_id": catalog["department"], "status": req["status"]},
    )
    assert filtered.status_code == 200, filtered.text
    assert all(item["department_id"] == catalog["department"] for item in filtered.json())

    by_requester = client.get(
        "/api/v1/sla/requisitions",
        headers=admin,
        params={"date_from": req["created_at"], "date_to": req["created_at"]},
    )
    assert by_requester.status_code == 200, by_requester.text
    assert req["id"] in {item["id"] for item in by_requester.json()}


def test_trazabilidad_relaciona_toda_la_cadena_sin_mover_stock(client) -> None:
    req, catalog = approved_requisition(client)
    almacenista = auth_header(client, "demo.almacenista")
    line_id = req["lines"][0]["id"]

    reservation = client.post(
        "/api/v1/inventory/reservations",
        headers=almacenista,
        json={
            "requisition_line_id": line_id,
            "quantity": "4",
            "idempotency_key": "lote5-traza-reserva-001",
        },
    )
    assert reservation.status_code == 201, reservation.text
    delivery = client.post(
        "/api/v1/inventory/issues",
        headers=almacenista,
        json={
            "requisition_line_id": line_id,
            "quantity": "4",
            "reservation_id": reservation.json()["id"],
            "idempotency_key": "lote5-traza-entrega-001",
        },
    )
    assert delivery.status_code == 201, delivery.text
    voucher = client.post(
        "/api/v1/documents/vouchers",
        headers=almacenista,
        json={
            "department_id": catalog["department"],
            "warehouse_id": catalog["warehouse"],
            "requisition_id": req["id"],
            "mode": "DELIVERY",
            "issue_date": "2026-11-19",
            "idempotency_key": "lote5-traza-vale-001",
        },
    )
    assert voucher.status_code == 201, voucher.text
    before = _kardex_count(client, almacenista, catalog["items"][0])

    admin = auth_header(client, "demo.admin")
    trace = client.get(f"/api/v1/requisitions/{req['id']}/trace", headers=admin)
    assert trace.status_code == 200, trace.text
    body = trace.json()
    assert body["document_no"] == req["document_no"]
    stages = {item["stage"]: item for item in body["stages"]}
    assert list(stages) == [
        "REQUISICION",
        "AUTORIZACION",
        "RESERVA",
        "ENTREGA",
        "VALE",
        "SEGUIMIENTO",
    ]
    assert all(stage["completed"] for stage in stages.values())
    assert stages["VALE"]["document_no"] == voucher.json()["document_no"]
    assert any(item["id"] == delivery.json()["id"] for item in body["deliveries"])
    assert any(item["id"] == voucher.json()["id"] for item in body["vouchers"])
    assert body["approvals"]
    assert any(event["action"] == "VOUCHER_CREATE" for event in body["audit_events"])
    assert any(event["event_type"] == "VOUCHER_CREATED" for event in body["document_events"])
    assert Decimal(body["tracking"]["fulfillment_percent"]) > 0

    # Consultar la trazabilidad y descargar documentos no altera el inventario.
    client.get(f"/api/v1/requisitions/{req['id']}/pdf", headers=almacenista)
    client.get(f"/api/v1/documents/vouchers/{voucher.json()['id']}/pdf", headers=almacenista)
    second = client.get(f"/api/v1/requisitions/{req['id']}/trace", headers=admin)
    assert second.status_code == 200
    assert _kardex_count(client, almacenista, catalog["items"][0]) == before
