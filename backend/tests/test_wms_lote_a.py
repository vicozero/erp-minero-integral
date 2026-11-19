from __future__ import annotations

import uuid
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, select

from app.core.config import settings
from app.modules.inventory.models import StockBalance
from app.modules.master_data.models import Item
from app.modules.organization.models import Warehouse
from tests.conftest import auth_header


def _item_id(db, code: str) -> uuid.UUID:
    return db.execute(select(Item.id).where(Item.code == code)).scalar_one()


def test_busqueda_avanzada_devuelve_catalogo_y_existencia_sintetica(client, db) -> None:
    headers = auth_header(client)

    response = client.get("/api/v1/wms/items/search?query=TORNILLO", headers=headers)
    assert response.status_code == 200, response.text
    rows = response.json()
    row = next(item for item in rows if item["code"] == "DEMO-TORNILLO")

    assert row["description"]
    assert row["uom_code"] == "UND"
    assert row["family_name"]
    assert row["manufacturer_part_no"] == "FF-M8-30"
    assert Decimal(row["on_hand_qty"]) > 0
    assert Decimal(row["reserved_qty"]) >= 0
    assert Decimal(row["available_qty"]) == Decimal(row["on_hand_qty"]) - Decimal(row["reserved_qty"])
    assert row["location_count"] >= 1


def test_ficha_de_material_incluye_ubicaciones_lotes_y_documentos(client, db) -> None:
    headers = auth_header(client)
    item_id = _item_id(db, "DEMO-TORNILLO")

    response = client.get(f"/api/v1/wms/items/{item_id}", headers=headers)
    assert response.status_code == 200, response.text
    detail = response.json()

    assert detail["code"] == "DEMO-TORNILLO"
    assert detail["uom_code"] == "UND"
    assert detail["standard_cost"] is not None
    assert detail["locations"]
    assert detail["locations"][0]["location_code"].startswith("A-01")
    assert any(lot["lot_number"] == "LOT-DEMO-001" for lot in detail["lots"])
    assert detail["suppliers"]
    assert isinstance(detail["movements"], list)
    assert isinstance(detail["related_documents"], list)


def test_altas_de_ubicaciones_respetan_permisos(client, db) -> None:
    warehouse_id = db.execute(
        select(Warehouse.id).where(Warehouse.code == "ALM_PRINCIPAL_DEMO")
    ).scalar_one()
    admin = auth_header(client)
    almacen = auth_header(client, "demo.almacenista")
    solicitante = auth_header(client, "demo.solicitante")

    listing = client.get("/api/v1/wms/locations", headers=admin)
    assert listing.status_code == 200, listing.text
    assert len(listing.json()) >= 6

    base_payload = {
        "warehouse_id": str(warehouse_id),
        "code": "QA-A-99-01",
        "zone": "A",
        "aisle": "99",
        "location_type": "STANDARD",
        "capacity_qty": "50",
    }
    created = client.post("/api/v1/wms/locations", json=base_payload, headers=admin)
    assert created.status_code == 201, created.text
    assert created.json()["qr_token"].startswith("WMS:ALM_PRINCIPAL_DEMO:QA-A-99-01")

    second = {**base_payload, "code": "QA-A-99-02"}
    allowed = client.post("/api/v1/wms/locations", json=second, headers=almacen)
    assert allowed.status_code == 201, allowed.text

    denied = client.post("/api/v1/wms/locations", json={**base_payload, "code": "QA-A-99-03"}, headers=solicitante)
    assert denied.status_code == 403


def test_fotografia_valida_formato_tamano_y_hash(client, db, monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "ATTACHMENT_STORAGE_DIR", tmp_path / "attachments")
    headers = auth_header(client)
    item_id = _item_id(db, "DEMO-FILTRO")
    png = b"\x89PNG\r\n\x1a\n" + b"synthetic-image-content"

    uploaded = client.post(
        f"/api/v1/wms/items/{item_id}/photo",
        files={"file": ("foto.png", png, "image/png")},
        headers=headers,
    )
    assert uploaded.status_code == 201, uploaded.text
    assert uploaded.json()["image_sha256"]

    served = client.get(f"/api/v1/wms/items/{item_id}/photo", headers=headers)
    assert served.status_code == 200
    assert served.headers["content-type"].startswith("image/png")

    rejected = client.post(
        f"/api/v1/wms/items/{item_id}/photo",
        files={"file": ("foto.txt", b"texto", "text/plain")},
        headers=headers,
    )
    assert rejected.status_code == 422


def test_consultas_wms_no_modifican_saldos(client, db) -> None:
    headers = auth_header(client)
    before = db.execute(select(func.count()).select_from(StockBalance)).scalar_one()

    assert client.get("/api/v1/wms/items/search", headers=headers).status_code == 200
    assert client.get("/api/v1/wms/locations", headers=headers).status_code == 200
    assert client.get(f"/api/v1/wms/items/{_item_id(db, 'DEMO-ACEITE')}", headers=headers).status_code == 200

    after = db.execute(select(func.count()).select_from(StockBalance)).scalar_one()
    assert after == before
