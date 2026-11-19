from __future__ import annotations

import uuid
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.modules.audit.models import AuditLog
from app.modules.inventory.models import LocationMap, StockBalance
from app.modules.master_data.models import StorageLocation
from app.modules.organization.models import Warehouse
from tests.conftest import auth_header


def _warehouse_id(db) -> uuid.UUID:
    return db.execute(
        select(Warehouse.id).where(Warehouse.code == "ALM_PRINCIPAL_DEMO")
    ).scalar_one()


def _location_id(db, code: str) -> uuid.UUID:
    return db.execute(select(StorageLocation.id).where(StorageLocation.code == code)).scalar_one()


def test_mapa_virtual_es_proyeccion_referencial(client, db) -> None:
    """UB-010: el mapa se deriva de ubicaciones y nunca se dice exacto."""
    headers = auth_header(client)
    warehouse_id = _warehouse_id(db)

    response = client.get(f"/api/v1/wms/maps/{warehouse_id}", headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["is_exact"] is False
    assert "no es plano exacto" in data["label"]
    assert data["map_version"] >= 1
    assert Decimal(data["width"]) == Decimal("1000")
    assert len(data["nodes"]) >= 6

    node = next(item for item in data["nodes"] if item["code"] == "A-01-R1-1-01")
    assert Decimal(node["coord_x"]) == Decimal("260")
    assert Decimal(node["coord_y"]) == Decimal("180")
    assert "A / 01 / R1 / 1 / 01 / A-01-R1-1-01" in node["hierarchy_path"]


def test_coordenadas_se_actualizan_con_auditoria_sin_mover_stock(client, db) -> None:
    headers = auth_header(client)
    location_id = _location_id(db, "A-01-R1-2-01")
    before = db.execute(select(func.count()).select_from(StockBalance)).scalar_one()

    response = client.patch(
        f"/api/v1/wms/locations/{location_id}/coordinates",
        json={"coord_x": "300", "coord_y": "250"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    detail = client.get(f"/api/v1/wms/locations/{location_id}", headers=headers).json()
    assert Decimal(detail["coord_x"]) == Decimal("300")
    assert Decimal(detail["coord_y"]) == Decimal("250")

    audit = db.execute(
        select(AuditLog)
        .where(AuditLog.action == "WMS_LOCATION_COORDINATES_UPDATED")
        .order_by(AuditLog.occurred_at.desc())
    ).scalar_one_or_none()
    assert audit is not None

    outside = client.patch(
        f"/api/v1/wms/locations/{location_id}/coordinates",
        json={"coord_x": "2000", "coord_y": "250"},
        headers=headers,
    )
    assert outside.status_code == 422
    after = db.execute(select(func.count()).select_from(StockBalance)).scalar_one()
    assert after == before


def test_fondo_es_referencial_y_versiones_son_append_only(
    client, db, monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(settings, "ATTACHMENT_STORAGE_DIR", tmp_path / "attachments")
    headers = auth_header(client)
    warehouse_id = _warehouse_id(db)
    png = b"\x89PNG\r\n\x1a\n" + b"synthetic-background-content"

    uploaded = client.post(
        f"/api/v1/wms/maps/{warehouse_id}/background",
        files={"file": ("plano.png", png, "image/png")},
        data={"label": "Referencial · no es plano exacto", "width": "1000", "height": "600"},
        headers=headers,
    )
    assert uploaded.status_code == 201, uploaded.text
    version = uploaded.json()
    assert version["map_version"] == 2
    assert version["is_exact"] is False
    assert version["background_sha256"]

    served = client.get(version["background_url"], headers=headers)
    assert served.status_code == 200
    assert served.headers["content-type"].startswith("image/png")
    assert served.content == png

    versions = client.get(f"/api/v1/wms/maps/{warehouse_id}/versions", headers=headers)
    assert versions.status_code == 200, versions.text
    assert [item["map_version"] for item in versions.json()] == [2, 1]
    assert all(item["is_exact"] is False for item in versions.json())

    missing = client.get(f"/api/v1/wms/maps/{warehouse_id}/background?version=1", headers=headers)
    assert missing.status_code == 404


def test_qr_opaco_resuelve_y_respeta_permisos(client, db) -> None:
    admin = auth_header(client)
    almacen = auth_header(client, "demo.almacenista")
    solicitante = auth_header(client, "demo.solicitante")
    warehouse_id = _warehouse_id(db)
    parent_id = _location_id(db, "A-01-R1-1-01")

    created = client.post(
        "/api/v1/wms/locations",
        json={
            "warehouse_id": str(warehouse_id),
            "code": "QA-VIRT-01",
            "parent_id": str(parent_id),
            "zone": "A",
            "aisle": "01",
            "rack": "R1",
            "level": "3",
            "position": "01",
            "coord_x": "500",
            "coord_y": "400",
            "location_type": "STANDARD",
            "capacity_qty": "10",
        },
        headers=admin,
    )
    assert created.status_code == 201, created.text
    location = created.json()
    token = location["qr_token"]
    assert token.startswith("WMS-") and "QA-VIRT-01" not in token

    qr = client.get(f"/api/v1/wms/locations/{location['id']}/qr", headers=almacen)
    assert qr.status_code == 200, qr.text
    svg = client.get(qr.json()["svg_url"], headers=almacen)
    assert svg.status_code == 200
    assert svg.headers["content-type"].startswith("image/svg+xml")
    assert b"<svg" in svg.content

    lookup = client.get("/api/v1/wms/locations/lookup", params={"qr_token": token}, headers=almacen)
    assert lookup.status_code == 200, lookup.text
    assert lookup.json()["code"] == "QA-VIRT-01"
    assert lookup.json()["hierarchy_path"].endswith("QA-VIRT-01")

    denied = client.patch(
        f"/api/v1/wms/locations/{location['id']}/coordinates",
        json={"coord_x": "1", "coord_y": "1"},
        headers=solicitante,
    )
    assert denied.status_code == 403

    unknown = client.get(
        "/api/v1/wms/locations/lookup", params={"qr_token": "WMS-no-existe"}, headers=admin
    )
    assert unknown.status_code == 404


def test_base_rechaza_mapa_marcado_como_exacto(db) -> None:
    warehouse_id = _warehouse_id(db)
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            db.add(
                LocationMap(
                    warehouse_id=warehouse_id,
                    map_version=99,
                    label="Plano exacto",
                    width=Decimal("1000"),
                    height=Decimal("600"),
                    is_exact=True,
                    is_active=False,
                )
            )
            db.flush()
