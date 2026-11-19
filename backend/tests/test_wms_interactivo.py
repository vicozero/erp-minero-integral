from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import delete, select

from app.modules.identity.models import AppUser, UserRole
from app.modules.inventory.models import StockBalance
from app.modules.master_data.models import StorageLocation
from app.modules.organization.models import MiningUnit, Warehouse
from tests.conftest import auth_header


def _warehouse_id(db) -> uuid.UUID:
    return db.execute(
        select(Warehouse.id).where(Warehouse.code == "ALM_PRINCIPAL_DEMO")
    ).scalar_one()


def _location_id(db, code: str) -> uuid.UUID:
    return db.execute(select(StorageLocation.id).where(StorageLocation.code == code)).scalar_one()


def test_inventario_de_ubicacion_usa_fuentes_reales_y_costo_es_restringido(client, db) -> None:
    """Lote 6: la ficha se construye desde saldos y el costo exige permiso."""
    admin = auth_header(client)
    solicitante = auth_header(client, "demo.solicitante")
    location_id = _location_id(db, "A-01-R1-1-01")

    response = client.get(f"/api/v1/wms/locations/{location_id}/inventory", headers=admin)
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["location_id"] == str(location_id)
    assert data["code"] == "A-01-R1-1-01"
    assert "A / 01 / R1 / 1 / 01" in data["hierarchy_path"]
    assert Decimal(data["occupied_qty"]) > Decimal("0")
    assert Decimal(data["occupancy_pct"]) > Decimal("0")
    assert data["items"], "La ubicación sembrada tiene existencias reales."
    assert data["can_view_cost"] is True
    item = data["items"][0]
    assert item["uom_code"]
    assert Decimal(item["available_qty"]) == Decimal(item["on_hand_qty"]) - Decimal(
        item["reserved_qty"]
    )
    assert item["unit_cost"] is not None

    limited = client.get(
        f"/api/v1/wms/locations/{location_id}/inventory", headers=solicitante
    )
    assert limited.status_code == 200, limited.text
    limited_data = limited.json()
    assert limited_data["can_view_cost"] is False
    assert all(row["unit_cost"] is None for row in limited_data["items"])


def test_ubicacion_sin_existencias_responde_estado_vacio(client, db) -> None:
    warehouse_id = _warehouse_id(db)
    created = client.post(
        "/api/v1/wms/locations",
        json={
            "warehouse_id": str(warehouse_id),
            "code": "QA-INTERACTIVA-VACIA",
            "zone": "Z",
            "location_type": "STANDARD",
            "capacity_qty": "10",
        },
        headers=auth_header(client),
    )
    assert created.status_code == 201, created.text
    location_id = created.json()["id"]

    response = client.get(f"/api/v1/wms/locations/{location_id}/inventory", headers=auth_header(client))
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["is_empty"] is True
    assert data["items"] == []
    assert data["last_movement"] is None
    assert Decimal(data["occupied_qty"]) == Decimal("0")
    assert data["occupancy_pct"] == "0" or Decimal(data["occupancy_pct"]) == Decimal("0")


def test_dashboard_separa_estado_ocupacion_y_stock_bajo_minimo(client, db) -> None:
    from app.modules.master_data.models import Item

    warehouse_id = _warehouse_id(db)
    headers = auth_header(client)
    item = db.execute(select(Item).where(Item.code == "DEMO-TORNILLO")).scalar_one()
    item.reorder_point = Decimal("9999")
    item.safety_stock = Decimal("9999")
    db.flush()

    response = client.get(
        "/api/v1/wms/dashboard", params={"warehouse_id": str(warehouse_id)}, headers=headers
    )
    assert response.status_code == 200, response.text
    data = response.json()
    totals = data["totals"]
    assert totals["location_count"] >= 6
    assert totals["occupied"] >= 3
    assert totals["empty"] >= 1
    assert totals["capacity_defined_count"] >= 6
    assert Decimal(totals["capacity_used_pct"]) > Decimal("0")
    codes = {row["code"] for row in data["alerts"]["below_minimum"]}
    assert "DEMO-TORNILLO" in codes
    assert "DEMO-TORNILLO" in {row["code"] for row in data["alerts"]["critical"]}

    zone = client.get(
        "/api/v1/wms/dashboard",
        params={"warehouse_id": str(warehouse_id), "zone": "A"},
        headers=headers,
    )
    assert zone.status_code == 200, zone.text
    assert 0 < zone.json()["totals"]["location_count"] < totals["location_count"]


def test_busqueda_de_refacciones_devuelve_ubicaciones_para_resaltar(client, db) -> None:
    headers = auth_header(client)
    warehouse_id = _warehouse_id(db)
    expected_id = str(_location_id(db, "A-01-R1-1-01"))

    response = client.get(
        "/api/v1/wms/materials/search",
        params={"query": "TORNILLO", "warehouse_id": str(warehouse_id)},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["query"] == "TORNILLO"
    material = next(row for row in data["materials"] if row["code"] == "DEMO-TORNILLO")
    assert material["uom_code"]
    assert any(row["location_id"] == expected_id for row in material["locations"])
    assert expected_id in data["location_ids"]

    other = client.get(
        "/api/v1/wms/materials/search",
        params={"query": "TORNILLO", "zone": "Z"},
        headers=headers,
    )
    assert other.status_code == 200, other.text
    assert other.json()["location_ids"] == []


def test_endpoints_interactivos_respetan_rbac(client, db) -> None:
    user = db.execute(select(AppUser).where(AppUser.username == "demo.solicitante")).scalar_one()
    db.execute(delete(UserRole).where(UserRole.user_id == user.id))
    db.flush()
    headers = auth_header(client, "demo.solicitante")
    location_id = _location_id(db, "A-01-R1-1-01")

    for path in (
        f"/api/v1/wms/locations/{location_id}/inventory",
        "/api/v1/wms/dashboard",
        "/api/v1/wms/materials/search?query=TORNILLO",
    ):
        denied = client.get(path, headers=headers)
        assert denied.status_code == 403, (path, denied.text)


def test_dashboard_y_busqueda_son_independientes_por_almacen(client, db) -> None:
    admin = auth_header(client)
    company_id = db.execute(select(Warehouse.company_id).limit(1)).scalar_one()
    unit_id = db.execute(select(MiningUnit.id).limit(1)).scalar_one()

    other_warehouse = Warehouse(
        company_id=company_id,
        mining_unit_id=unit_id,
        code="ALM_AISLADO_QA",
        name="Almacén aislado de prueba",
        created_by=db.execute(select(AppUser.id).where(AppUser.username == "demo.admin")).scalar_one(),
    )
    db.add(other_warehouse)
    db.flush()
    db.add(
        StorageLocation(
            warehouse_id=other_warehouse.id,
            code="AISLADO-01",
            zone="Z",
            location_type="STANDARD",
            capacity_qty=Decimal("5"),
            qr_token="WMS:QA:AISLADO-01",
            created_by=db.execute(
                select(AppUser.id).where(AppUser.username == "demo.admin")
            ).scalar_one(),
        )
    )
    db.flush()

    dashboard = client.get(
        "/api/v1/wms/dashboard", params={"warehouse_id": str(other_warehouse.id)}, headers=admin
    )
    assert dashboard.status_code == 200, dashboard.text
    assert dashboard.json()["totals"]["location_count"] == 1

    principal = _warehouse_id(db)
    principal_dashboard = client.get(
        "/api/v1/wms/dashboard", params={"warehouse_id": str(principal)}, headers=admin
    )
    assert principal_dashboard.json()["totals"]["location_count"] >= 6
    isolated_alerts = (
        dashboard.json()["alerts"]["critical"]
        + dashboard.json()["alerts"]["below_minimum"]
    )
    assert all(Decimal(row["on_hand_qty"]) == Decimal("0") for row in isolated_alerts)

    isolated_search = client.get(
        "/api/v1/wms/materials/search",
        params={"query": "TORNILLO", "warehouse_id": str(other_warehouse.id)},
        headers=admin,
    )
    assert isolated_search.status_code == 200, isolated_search.text
    assert isolated_search.json()["location_ids"] == []

    # Ninguna consulta gráfica debe alterar saldos.
    from sqlalchemy import func

    count = db.execute(select(func.count()).select_from(StockBalance)).scalar_one()
    assert count >= 3
