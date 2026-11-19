from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.modules.requisitions.models import Requisition
from app.modules.sla.models import RequisitionSlaEvent, SlaPolicy
from tests.conftest import auth_header


def _catalog_raw(client, headers) -> dict:
    response = client.get("/api/v1/catalogs", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _create_submitted(
    client,
    *,
    priority: str = "HIGH",
    requisition_type: str = "STOCK",
    department_code: str | None = None,
) -> tuple[dict, dict]:
    """Crea y envía una requisición sintética; devuelve (requisición, catálogo)."""
    admin = auth_header(client, "demo.admin")
    catalog = _catalog_raw(client, admin)
    department_id = catalog["departments"][0]["id"]
    if department_code is not None:
        department_id = next(
            dept["id"] for dept in catalog["departments"] if dept["code"] == department_code
        )
    created = client.post(
        "/api/v1/requisitions",
        headers=admin,
        json={
            "department_id": department_id,
            "warehouse_id": catalog["warehouses"][0]["id"] if requisition_type == "STOCK" else None,
            "equipment_id": catalog["equipment"][0]["id"],
            "cost_center_id": catalog["cost_centers"][0]["id"],
            "requisition_type": requisition_type,
            "priority": priority,
            "justification": "Prueba sintética del semáforo SLA",
            "observations": "Sin datos reales",
            "needed_at": "2026-12-01T12:00:00Z",
            "lines": [
                {
                    "item_id": catalog["items"][0]["id"],
                    "description": "Artículo sintético SLA",
                    "uom_id": catalog["uoms"][0]["id"],
                    "requested_qty": "2",
                }
            ],
        },
    )
    assert created.status_code == 201, created.text
    submitted = client.post(
        f"/api/v1/requisitions/{created.json()['id']}/submit", headers=admin
    )
    assert submitted.status_code == 200, submitted.text
    return submitted.json(), catalog


def _set_submitted_hours_ago(db, requisition_id: str, hours: float) -> None:
    db.execute(
        update(Requisition)
        .where(Requisition.id == uuid.UUID(requisition_id))
        .values(submitted_at=datetime.now(timezone.utc) - timedelta(hours=hours))
    )
    db.flush()


def _policy_by_priority(client, headers, priority: str) -> dict:
    response = client.get("/api/v1/sla/policies", headers=headers)
    assert response.status_code == 200, response.text
    return next(policy for policy in response.json() if policy["priority"] == priority and policy["scope"] == "GLOBAL")


def test_politicas_iniciales_umbrales_aprobados_y_emergencia_desactivada(client) -> None:
    admin = auth_header(client, "demo.admin")
    response = client.get("/api/v1/sla/policies", headers=admin)
    assert response.status_code == 200, response.text
    policies = response.json()
    expected = {("LOW", 72, 96), ("NORMAL", 48, 72), ("HIGH", 24, 48), ("URGENT", 8, 16)}
    assert {
        (policy["priority"], policy["green_hours"], policy["yellow_hours"])
        for policy in policies
        if policy["scope"] == "GLOBAL"
    } == expected
    for policy in policies:
        assert policy["emergency_enabled"] is False
        assert policy["emergency_approved_by"] is None
        assert policy["emergency_approved_at"] is None
        assert policy["emergency_green_hours"] == 4
        assert policy["emergency_yellow_hours"] == 8


def test_color_calculado_en_backend_no_sustituye_estado_administrativo(client, db) -> None:
    req, _catalog = _create_submitted(client, priority="HIGH")
    admin = auth_header(client, "demo.admin")

    for hours, expected in ((2, "GREEN"), (30, "YELLOW"), (60, "RED")):
        _set_submitted_hours_ago(db, req["id"], hours)
        response = client.get(f"/api/v1/sla/requisitions/{req['id']}", headers=admin)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["sla"]["color"] == expected
        assert body["sla"]["measured"] is True
        assert body["sla"]["administrative_status"] == "SUBMITTED"
        assert body["status"] == "SUBMITTED"

        original = client.get(f"/api/v1/requisitions/{req['id']}", headers=admin)
        assert original.status_code == 200, original.text
        assert original.json()["status"] == "SUBMITTED"
        assert original.json()["sla"]["color"] == expected


def test_historial_inmutable_y_filtro_por_color(client, db) -> None:
    req, _catalog = _create_submitted(client, priority="HIGH")
    admin = auth_header(client, "demo.admin")

    initial = client.get(f"/api/v1/sla/requisitions/{req['id']}/history", headers=admin)
    assert initial.status_code == 200, initial.text
    assert len(initial.json()) == 1
    assert initial.json()[0]["trigger"] == "ON_SUBMIT"
    assert initial.json()[0]["color"] == "GREEN"

    _set_submitted_hours_ago(db, req["id"], 60)
    evaluated = client.post("/api/v1/sla/evaluate", headers=admin)
    assert evaluated.status_code == 200, evaluated.text

    history = client.get(f"/api/v1/sla/requisitions/{req['id']}/history", headers=admin).json()
    assert len(history) == 2
    assert [event["color"] for event in history] == ["GREEN", "RED"]
    assert history[0]["id"] != history[1]["id"]

    reds = client.get("/api/v1/sla/requisitions", headers=admin, params={"sla_color": "RED"})
    assert reds.status_code == 200, reds.text
    assert req["id"] in {item["id"] for item in reds.json()}

    greens = client.get("/api/v1/sla/requisitions", headers=admin, params={"sla_color": "GREEN"})
    assert req["id"] not in {item["id"] for item in greens.json()}

    # El listado operativo usa el mismo color calculado, sin recalcularlo en el cliente.
    operational = client.get(
        "/api/v1/requisitions", headers=admin, params={"sla_color": "RED"}
    )
    assert operational.status_code == 200, operational.text
    assert req["id"] in {item["id"] for item in operational.json()}
    assert all(item["sla"]["color"] == "RED" for item in operational.json())


def test_politica_especifica_gana_a_la_global(client, db) -> None:
    req, catalog = _create_submitted(client, priority="HIGH")
    admin = auth_header(client, "demo.admin")
    department_id = req["department_id"]

    created = client.post(
        "/api/v1/sla/policies",
        headers=admin,
        json={
            "priority": "HIGH",
            "department_id": department_id,
            "requisition_type": "ALL",
            "green_hours": 1,
            "yellow_hours": 2,
            "evidence": "Regla departamental de prueba sintética",
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["scope"] == "DEPARTMENT"

    _set_submitted_hours_ago(db, req["id"], 3)
    response = client.get(f"/api/v1/sla/requisitions/{req['id']}", headers=admin)
    assert response.status_code == 200, response.text
    assert response.json()["sla"]["color"] == "RED"
    assert response.json()["sla"]["policy_id"] == created.json()["id"]
    assert response.json()["sla"]["policy_scope"] == "DEPARTMENT"


def test_emergencia_requiere_aprobacion_y_permiso(client, db) -> None:
    solicitante = auth_header(client, "demo.solicitante")
    admin = auth_header(client, "demo.admin")
    policy = _policy_by_priority(client, admin, "URGENT")

    denied = client.post(
        f"/api/v1/sla/policies/{policy['id']}/emergency",
        headers=solicitante,
        json={"enabled": True, "reason": "Emergencia sintética sin permiso"},
    )
    assert denied.status_code == 403

    approved = client.post(
        f"/api/v1/sla/policies/{policy['id']}/emergency",
        headers=admin,
        json={"enabled": True, "reason": "Aprobación sintética de emergencia"},
    )
    assert approved.status_code == 200, approved.text
    body = approved.json()
    assert body["emergency_enabled"] is True
    assert body["emergency_approved_by"] is not None
    assert body["emergency_approved_at"] is not None

    # Con emergencia 4/8 h, 6 h ya es amarillo; sin emergencia sería verde (8/16 h).
    req, _catalog = _create_submitted(client, priority="URGENT")
    _set_submitted_hours_ago(db, req["id"], 6)
    response = client.get(f"/api/v1/sla/requisitions/{req['id']}", headers=admin)
    assert response.status_code == 200, response.text
    assert response.json()["sla"]["color"] == "YELLOW"
    assert response.json()["sla"]["emergency_active"] is True

    disabled = client.post(
        f"/api/v1/sla/policies/{policy['id']}/emergency",
        headers=admin,
        json={"enabled": False, "reason": "Se retira la emergencia sintética"},
    )
    assert disabled.status_code == 200, disabled.text
    assert disabled.json()["emergency_enabled"] is False
    assert disabled.json()["emergency_approved_at"] is None


def test_emergencia_no_se_puede_activar_en_base_sin_aprobacion(db) -> None:
    """La propia base impide activar emergencia sin aprobador, aunque se escriba directo."""
    policy = db.execute(
        select(SlaPolicy).where(SlaPolicy.priority == "URGENT", SlaPolicy.scope == "GLOBAL")
    ).scalar_one()
    policy.emergency_enabled = True
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_borrador_y_documento_cancelado_sin_medicion(client) -> None:
    admin = auth_header(client, "demo.admin")
    catalog = _catalog_raw(client, admin)
    created = client.post(
        "/api/v1/requisitions",
        headers=admin,
        json={
            "department_id": catalog["departments"][0]["id"],
            "warehouse_id": catalog["warehouses"][0]["id"],
            "equipment_id": catalog["equipment"][0]["id"],
            "cost_center_id": catalog["cost_centers"][0]["id"],
            "requisition_type": "STOCK",
            "priority": "URGENT",
            "justification": "Borrador sintético sin medición",
            "lines": [
                {
                    "item_id": catalog["items"][0]["id"],
                    "description": "Artículo sintético borrador",
                    "uom_id": catalog["uoms"][0]["id"],
                    "requested_qty": "1",
                }
            ],
        },
    )
    assert created.status_code == 201, created.text
    draft = client.get(f"/api/v1/sla/requisitions/{created.json()['id']}", headers=admin)
    assert draft.status_code == 200, draft.text
    assert draft.json()["sla"]["color"] == "NONE"
    assert draft.json()["sla"]["measured"] is False

    cancelled = client.post(
        f"/api/v1/requisitions/{created.json()['id']}/cancel",
        headers=admin,
        json={"reason": "Cancelación sintética de prueba"},
    )
    assert cancelled.status_code == 200, cancelled.text
    after = client.get(f"/api/v1/sla/requisitions/{created.json()['id']}", headers=admin)
    assert after.json()["sla"]["color"] == "NONE"
    assert after.json()["status"] == "CANCELLED"


def test_alcance_por_departamento_bloquea_sla_ajeno(client) -> None:
    req, _catalog = _create_submitted(client, priority="HIGH", department_code="DEMO-OTRA")
    solicitante = auth_header(client, "demo.solicitante")

    denied = client.get(f"/api/v1/sla/requisitions/{req['id']}", headers=solicitante)
    assert denied.status_code == 403
    denied_history = client.get(
        f"/api/v1/sla/requisitions/{req['id']}/history", headers=solicitante
    )
    assert denied_history.status_code == 403

    visible = client.get("/api/v1/sla/requisitions", headers=solicitante)
    assert visible.status_code == 200, visible.text
    assert req["id"] not in {item["id"] for item in visible.json()}


def test_evaluacion_no_modifica_inventario(client, db) -> None:
    req, catalog = _create_submitted(client, priority="NORMAL")
    admin = auth_header(client, "demo.admin")

    from tests.test_documentation import _kardex_count

    before = _kardex_count(client, admin, catalog["items"][0]["id"])
    response = client.post("/api/v1/sla/evaluate", headers=admin)
    assert response.status_code == 200, response.text
    assert _kardex_count(client, admin, catalog["items"][0]["id"]) == before

    events = db.execute(
        select(RequisitionSlaEvent).where(RequisitionSlaEvent.requisition_id == uuid.UUID(req["id"]))
    ).scalars()
    assert any(event.trigger == "MANUAL" for event in events)
