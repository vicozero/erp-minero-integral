from __future__ import annotations

from decimal import Decimal

from tests.conftest import auth_header


def catalogs(client, headers):
    response = client.get("/api/v1/catalogs", headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()
    return {
        "department": data["departments"][0]["id"],
        "warehouse": data["warehouses"][0]["id"],
        "items": [item["id"] for item in data["items"]],
        "uoms": {uom["code"]: uom["id"] for uom in data["uoms"]},
        "cost_center": data["cost_centers"][0]["id"],
        "equipment": data["equipment"][0]["id"],
        "supplier": data["suppliers"][0]["id"],
    }


def create_requisition(client, headers, catalog, quantities=(Decimal("10"), Decimal("3"))):
    payload = {
        "department_id": catalog["department"],
        "warehouse_id": catalog["warehouse"],
        "equipment_id": catalog["equipment"],
        "cost_center_id": catalog["cost_center"],
        "requisition_type": "STOCK",
        "priority": "HIGH",
        "justification": "Prueba sintética de mantenimiento",
        "observations": "Sin datos reales",
        "lines": [
            {
                "item_id": catalog["items"][0],
                "description": "Tornillo demo",
                "uom_id": catalog["uoms"]["UND"],
                "requested_qty": str(quantities[0]),
                "notes": "Partida 1",
            },
            {
                "item_id": catalog["items"][1],
                "description": "Aceite demo",
                "uom_id": catalog["uoms"]["LT"],
                "requested_qty": str(quantities[1]),
                "notes": "Partida 2",
            },
        ],
    }
    return client.post("/api/v1/requisitions", headers=headers, json=payload)


def test_crea_requisicion_con_varias_partidas_y_folio_unico(client):
    solicitante = auth_header(client, "demo.solicitante")
    catalog = catalogs(client, solicitante)

    first = create_requisition(client, solicitante, catalog)
    assert first.status_code == 201, first.text
    second = create_requisition(client, solicitante, catalog)
    assert second.status_code == 201, second.text

    assert len(first.json()["lines"]) == 2
    assert first.json()["status"] == "DRAFT"
    assert first.json()["document_no"] != second.json()["document_no"]
    assert first.json()["document_no"].startswith("REQ-LAG-")


def test_flujo_autorizacion_parcial(client):
    solicitante = auth_header(client, "demo.solicitante")
    catalog = catalogs(client, solicitante)
    created = create_requisition(client, solicitante, catalog)
    req_id = created.json()["id"]

    submitted = client.post(f"/api/v1/requisitions/{req_id}/submit", headers=solicitante)
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "SUBMITTED"

    aprobador = auth_header(client, "demo.aprobador")
    lines = submitted.json()["lines"]
    decision = client.post(
        f"/api/v1/requisitions/{req_id}/decide",
        headers=aprobador,
        json={
            "decisions": [
                {
                    "requisition_line_id": lines[0]["id"],
                    "decision": "APPROVE",
                    "approved_qty": "10",
                },
                {
                    "requisition_line_id": lines[1]["id"],
                    "decision": "APPROVE",
                    "approved_qty": "1",
                    "reason": "Autorización parcial por disponibilidad",
                },
            ],
            "reason": "Autorización parcial",
        },
    )
    assert decision.status_code == 200, decision.text
    body = decision.json()
    assert body["status"] == "PARTIALLY_APPROVED"
    assert Decimal(body["lines"][0]["authorised_qty"]) == Decimal("10")
    assert Decimal(body["lines"][1]["authorised_qty"]) == Decimal("1")


def test_rechazo_requiere_motivo(client):
    solicitante = auth_header(client, "demo.solicitante")
    catalog = catalogs(client, solicitante)
    created = create_requisition(client, solicitante, catalog)
    req_id = created.json()["id"]
    client.post(f"/api/v1/requisitions/{req_id}/submit", headers=solicitante)

    aprobador = auth_header(client, "demo.aprobador")
    lines = client.get(f"/api/v1/requisitions/{req_id}", headers=aprobador).json()["lines"]
    invalid = client.post(
        f"/api/v1/requisitions/{req_id}/decide",
        headers=aprobador,
        json={
            "decisions": [
                {"requisition_line_id": line["id"], "decision": "REJECT"} for line in lines
            ]
        },
    )
    assert invalid.status_code == 422

    valid = client.post(
        f"/api/v1/requisitions/{req_id}/decide",
        headers=aprobador,
        json={
            "decisions": [
                {"requisition_line_id": line["id"], "decision": "REJECT"} for line in lines
            ],
            "reason": "Presupuesto no autorizado",
        },
    )
    assert valid.status_code == 200, valid.text
    assert valid.json()["status"] == "REJECTED"
    assert valid.json()["rejection_reason"] == "Presupuesto no autorizado"


def test_no_permite_modificar_requisicion_autorizada(client):
    solicitante = auth_header(client, "demo.solicitante")
    catalog = catalogs(client, solicitante)
    created = create_requisition(client, solicitante, catalog)
    req_id = created.json()["id"]
    client.post(f"/api/v1/requisitions/{req_id}/submit", headers=solicitante)

    aprobador = auth_header(client, "demo.aprobador")
    lines = client.get(f"/api/v1/requisitions/{req_id}", headers=aprobador).json()["lines"]
    client.post(
        f"/api/v1/requisitions/{req_id}/decide",
        headers=aprobador,
        json={
            "decisions": [
                {
                    "requisition_line_id": line["id"],
                    "decision": "APPROVE",
                    "approved_qty": line["requested_qty"],
                }
                for line in lines
            ]
        },
    )

    update = client.patch(
        f"/api/v1/requisitions/{req_id}/draft",
        headers=solicitante,
        json={"priority": "URGENT", "justification": "Intento de cambio"},
    )
    assert update.status_code == 409


def test_rol_solicitante_no_puede_aprobar(client):
    solicitante = auth_header(client, "demo.solicitante")
    catalog = catalogs(client, solicitante)
    created = create_requisition(client, solicitante, catalog)
    req_id = created.json()["id"]
    client.post(f"/api/v1/requisitions/{req_id}/submit", headers=solicitante)

    attempt = client.post(
        f"/api/v1/requisitions/{req_id}/decide",
        headers=solicitante,
        json={
            "decisions": [
                {
                    "requisition_line_id": created.json()["lines"][0]["id"],
                    "decision": "APPROVE",
                    "approved_qty": "10",
                }
            ]
        },
    )
    assert attempt.status_code == 403


def test_seguimiento_por_partida_incluye_cantidades_controladas(client):
    solicitante = auth_header(client, "demo.solicitante")
    catalog = catalogs(client, solicitante)
    created = create_requisition(client, solicitante, catalog)
    detail = client.get(
        f"/api/v1/requisitions/{created.json()['id']}", headers=solicitante
    ).json()
    for key in (
        "requested_qty",
        "authorised_qty",
        "reserved_qty",
        "purchased_qty",
        "received_qty",
        "delivered_qty",
        "pending_qty",
    ):
        assert key in detail["lines"][0]
