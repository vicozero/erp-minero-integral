"""Lote 7: diseñador profesional de planos 2D/3D.

Todas las pruebas usan la base sintética de pruebas y se revierten. Verifican
persistencia, concurrencia, publicación append-only, permisos separados,
asistente de racks y aislamiento respecto de saldos de inventario.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditLog
from app.modules.inventory.models import FloorPlan, StockBalance
from app.modules.organization.models import Warehouse
from tests.conftest import auth_header


def _warehouse_id(db: Session) -> uuid.UUID:
    return db.execute(
        select(Warehouse.id).where(Warehouse.code == "ALM_PRINCIPAL_DEMO")
    ).scalar_one()


def _workspace(client: TestClient, headers: dict[str, str], warehouse_id: uuid.UUID) -> dict:
    response = client.get(
        f"/api/v1/wms/plans/workspace?warehouse_id={warehouse_id}", headers=headers
    )
    assert response.status_code == 200, response.text
    return response.json()


def _draft(client: TestClient, headers: dict[str, str], warehouse_id: uuid.UUID) -> dict:
    draft = _workspace(client, headers, warehouse_id)["draft"]
    if draft is not None:
        return draft
    created = client.post(
        f"/api/v1/wms/plans/draft?warehouse_id={warehouse_id}", headers=headers
    )
    assert created.status_code == 201, created.text
    return created.json()


def _element(element_id: str = "wall-1", **changes: object) -> dict:
    element = {
        "id": element_id,
        "type": "WALL",
        "name": "Pared norte",
        "x": 20,
        "y": 20,
        "width": 200,
        "height": 8,
        "rotation": 0,
        "color": "#475569",
        "visible": True,
        "locked": False,
        "layer": "estructura",
        "z_index": 0,
        "dimensions_verified": False,
        "properties": {},
    }
    element.update(changes)
    return element


def _payload(revision: int, elements: list[dict] | None = None) -> dict:
    return {
        "label": "Referencial · no es plano exacto",
        "width": 1000,
        "height": 600,
        "grid_size": 20,
        "scale_label": "Referencial",
        "dimensions_verified": False,
        "elements": elements if elements is not None else [_element()],
        "revision": revision,
        "notes": "Diseño de prueba sintética",
    }


def test_workspace_es_solo_lectura_y_borrador_es_unico(client: TestClient, db: Session) -> None:
    headers = auth_header(client)
    warehouse_id = _warehouse_id(db)

    initial = _workspace(client, headers, warehouse_id)
    assert initial["draft"] is None
    assert db.execute(select(func.count()).select_from(FloorPlan)).scalar_one() == 0

    created = client.post(
        f"/api/v1/wms/plans/draft?warehouse_id={warehouse_id}", headers=headers
    )
    assert created.status_code == 201, created.text
    draft = created.json()
    assert draft["status"] == "DRAFT"
    assert draft["revision"] == 1
    assert draft["dimensions_verified"] is False
    assert "no es plano exacto" in draft["label"]

    duplicate = client.post(
        f"/api/v1/wms/plans/draft?warehouse_id={warehouse_id}", headers=headers
    )
    assert duplicate.status_code == 201, duplicate.text
    assert duplicate.json()["id"] == draft["id"]

    data = _workspace(client, headers, warehouse_id)
    assert data["draft"]["id"] == draft["id"]
    assert data["active"] is None or data["active"]["status"] == "PUBLISHED"
    assert data["versions"] == [] or all(item["status"] == "PUBLISHED" for item in data["versions"])
    assert db.execute(select(func.count()).select_from(FloorPlan)).scalar_one() == 1


def test_guardar_recuperar_y_conflicto_de_concurrencia(client: TestClient, db: Session) -> None:
    headers = auth_header(client)
    warehouse_id = _warehouse_id(db)
    draft = _draft(client, headers, warehouse_id)

    saved = client.put(
        f"/api/v1/wms/plans/{draft['id']}?warehouse_id={warehouse_id}",
        json=_payload(draft["revision"], [_element(), _element("aisle-1", type="AISLE", name="Pasillo", y=60)]),
        headers=headers,
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["revision"] == 2
    assert len(saved.json()["elements"]) == 2

    reloaded = _workspace(client, headers, warehouse_id)["draft"]
    assert reloaded["revision"] == 2
    assert {item["id"] for item in reloaded["elements"]} == {"wall-1", "aisle-1"}

    stale = client.put(
        f"/api/v1/wms/plans/{draft['id']}?warehouse_id={warehouse_id}",
        json=_payload(1),
        headers=headers,
    )
    assert stale.status_code == 409

    audit = db.execute(
        select(AuditLog).where(AuditLog.action == "WMS_PLAN_DRAFT_SAVED")
    ).scalar_one_or_none()
    assert audit is not None


def test_publicar_es_append_only_y_no_toca_inventario(client: TestClient, db: Session) -> None:
    headers = auth_header(client)
    warehouse_id = _warehouse_id(db)
    draft = _draft(client, headers, warehouse_id)
    stock_before = db.execute(select(func.count()).select_from(StockBalance)).scalar_one()

    saved = client.put(
        f"/api/v1/wms/plans/{draft['id']}?warehouse_id={warehouse_id}",
        json=_payload(draft["revision"]),
        headers=headers,
    )
    assert saved.status_code == 200, saved.text

    published = client.post(
        f"/api/v1/wms/plans/{draft['id']}/publish?warehouse_id={warehouse_id}&revision=2",
        headers=headers,
    )
    assert published.status_code == 200, published.text
    data = published.json()
    assert data["active"]["status"] == "PUBLISHED"
    assert data["active"]["is_active"] is True
    assert data["draft"]["status"] == "DRAFT"
    assert data["draft"]["id"] != data["active"]["id"]
    assert [item["plan_version"] for item in data["versions"]] == [data["active"]["plan_version"]]

    rows = list(
        db.execute(
            select(FloorPlan).where(FloorPlan.warehouse_id == warehouse_id)
        ).scalars()
    )
    assert {row.status for row in rows} == {"DRAFT", "PUBLISHED", "ARCHIVED"}
    assert sum(1 for row in rows if row.is_active) == 1
    assert db.execute(select(func.count()).select_from(StockBalance)).scalar_one() == stock_before
    assert db.execute(
        select(func.count()).select_from(AuditLog).where(AuditLog.action == "WMS_PLAN_PUBLISHED")
    ).scalar_one() >= 1


def test_asistente_rack_crea_posiciones_wms_sin_modificar_saldos(client: TestClient, db: Session) -> None:
    headers = auth_header(client)
    warehouse_id = _warehouse_id(db)
    draft = _draft(client, headers, warehouse_id)
    stock_before = db.execute(select(func.count()).select_from(StockBalance)).scalar_one()

    blueprint = {
        "name": "Rack Lote 7",
        "code": "RACK-L7-01",
        "zone": "A",
        "aisle": "07",
        "rack": "01",
        "modules": 2,
        "levels": 2,
        "positions_per_level": 2,
        "width": 240,
        "depth": 60,
        "level_height": 20,
        "orientation": 0,
        "capacity_per_position": 10,
        "capacity_validated": True,
        "location_type": "STANDARD",
        "x": 100,
        "y": 100,
        "create_locations": True,
    }
    created = client.post(
        f"/api/v1/wms/plans/{draft['id']}/racks?warehouse_id={warehouse_id}",
        json=blueprint,
        headers=headers,
    )
    assert created.status_code == 201, created.text
    result = created.json()
    assert result["total_positions"] == 8
    assert result["created_count"] == 8
    assert "no constituye un plano exacto" in result["warning"]

    workspace = _workspace(client, headers, warehouse_id)
    elements = workspace["draft"]["elements"]
    assert len(elements) == 9
    positions = [item for item in elements if item["type"] == "POSITION"]
    assert len(positions) == 8
    assert all(item["wms_location_id"] for item in positions)

    duplicate = client.post(
        f"/api/v1/wms/plans/{workspace['draft']['id']}/racks?warehouse_id={warehouse_id}",
        json=blueprint,
        headers=headers,
    )
    assert duplicate.status_code == 422

    assert db.execute(select(func.count()).select_from(StockBalance)).scalar_one() == stock_before
    assert db.execute(
        select(func.count()).select_from(AuditLog).where(AuditLog.action == "WMS_PLAN_RACK_CREATED")
    ).scalar_one() >= 1


def test_geometria_invalida_y_referencia_wms_duplicada(client: TestClient, db: Session) -> None:
    headers = auth_header(client)
    warehouse_id = _warehouse_id(db)
    draft = _draft(client, headers, warehouse_id)

    outside = client.put(
        f"/api/v1/wms/plans/{draft['id']}?warehouse_id={warehouse_id}",
        json=_payload(1, [_element(x=2000)]),
        headers=headers,
    )
    assert outside.status_code == 422

    location_id = db.execute(
        select(Warehouse.id).where(Warehouse.code == "ALM_PRINCIPAL_DEMO")
    ).scalar_one()
    linked = [
        _element("pos-1", type="POSITION", wms_location_id=str(location_id)),
        _element("pos-2", type="POSITION", wms_location_id=str(location_id)),
    ]
    duplicated = client.put(
        f"/api/v1/wms/plans/{draft['id']}?warehouse_id={warehouse_id}",
        json=_payload(1, linked),
        headers=headers,
    )
    assert duplicated.status_code == 422


def test_permisos_separados_para_editar_y_publicar(client: TestClient, db: Session) -> None:
    warehouse_id = _warehouse_id(db)
    admin = auth_header(client)
    draft = _draft(client, admin, warehouse_id)

    solicitante = auth_header(client, "demo.solicitante")
    denied = client.put(
        f"/api/v1/wms/plans/{draft['id']}?warehouse_id={warehouse_id}",
        json=_payload(draft["revision"]),
        headers=solicitante,
    )
    assert denied.status_code == 403
    almacenista = auth_header(client, "demo.almacenista")
    saved = client.put(
        f"/api/v1/wms/plans/{draft['id']}?warehouse_id={warehouse_id}",
        json=_payload(1),
        headers=almacenista,
    )
    assert saved.status_code == 200
    no_publish = client.post(
        f"/api/v1/wms/plans/{draft['id']}/publish?warehouse_id={warehouse_id}&revision=2",
        headers=almacenista,
    )
    assert no_publish.status_code == 403
    admin_publish = client.post(
        f"/api/v1/wms/plans/{draft['id']}/publish?warehouse_id={warehouse_id}&revision=2",
        headers=admin,
    )
    assert admin_publish.status_code == 200, admin_publish.text


def test_aislamiento_entre_almacenes(client: TestClient, db: Session) -> None:
    headers = auth_header(client)
    warehouse_a = _warehouse_id(db)
    original = db.get(Warehouse, warehouse_a)
    assert original is not None
    warehouse_b = Warehouse(
        company_id=original.company_id,
        mining_unit_id=original.mining_unit_id,
        code="ALM_SEGUNDO_LOTE7",
        name="Almacén secundario prueba",
        warehouse_type="SURFACE",
        allows_negative=False,
    )
    db.add(warehouse_b)
    db.flush()

    draft_a = _draft(client, headers, warehouse_a)
    draft_b = _draft(client, headers, warehouse_b.id)
    assert draft_a["id"] != draft_b["id"]

    crossed = client.put(
        f"/api/v1/wms/plans/{draft_a['id']}?warehouse_id={warehouse_b.id}",
        json=_payload(1),
        headers=headers,
    )
    assert crossed.status_code == 404


def test_export_y_vista_previa_de_importacion(client: TestClient, db: Session) -> None:
    headers = auth_header(client)
    warehouse_id = _warehouse_id(db)
    draft = _draft(client, headers, warehouse_id)

    exported = client.get(
        f"/api/v1/wms/plans/{draft['id']}/export?warehouse_id={warehouse_id}", headers=headers
    )
    assert exported.status_code == 200, exported.text
    data = exported.json()
    assert data["schema"] == "erp-minero.floor-plan.v1"
    assert "unit_cost" not in str(data)
    assert "on_hand_qty" not in str(data)

    preview = client.post(
        "/api/v1/wms/plans/import-preview",
        json=_payload(1),
        headers=headers,
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["element_count"] == 1
    assert "no ejecuta scripts" in preview.json()["warning"]

    invalid = client.post(
        "/api/v1/wms/plans/import-preview",
        json={**_payload(1), "elements": [_element(width=-1)]},
        headers=headers,
    )
    assert invalid.status_code == 422

    assert Decimal(str(preview.json()["width"])) == Decimal("1000")
