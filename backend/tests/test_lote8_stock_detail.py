from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.modules.identity.models import AppUser
from app.modules.inventory.models import NULL_UUID, StockBalance, StockBalanceDetail, StockReservation
from app.modules.inventory.service import InventoryService
from app.modules.organization.models import Warehouse
from tests.conftest import auth_header
from tests.test_inventory import approved_requisition, availability
from tests.test_requisitions import catalogs


def _reconciliation(db: Session, warehouse_id: uuid.UUID, item_id: uuid.UUID) -> dict:
    row = db.execute(
        text(
            """
            SELECT legacy_on_hand_qty, detail_on_hand_qty,
                   legacy_reserved_qty, detail_reserved_qty,
                   diferencia_on_hand, diferencia_reserved, estado
            FROM inv.v_stock_balance_reconciliation
            WHERE warehouse_id = :warehouse_id AND item_id = :item_id
            """
        ),
        {"warehouse_id": warehouse_id, "item_id": item_id},
    ).mappings().one()
    return dict(row)


def _assert_ok(db: Session, warehouse_id: uuid.UUID, item_id: uuid.UUID, on_hand: str, reserved: str) -> None:
    row = _reconciliation(db, warehouse_id, item_id)
    assert row["estado"] == "OK", row
    assert Decimal(str(row["diferencia_on_hand"])) == Decimal("0")
    assert Decimal(str(row["diferencia_reserved"])) == Decimal("0")
    assert Decimal(str(row["legacy_on_hand_qty"])) == Decimal(on_hand)
    assert Decimal(str(row["detail_on_hand_qty"])) == Decimal(on_hand)
    assert Decimal(str(row["legacy_reserved_qty"])) == Decimal(reserved)
    assert Decimal(str(row["detail_reserved_qty"])) == Decimal(reserved)


def test_reserva_entrega_y_vencimiento_mantienen_detalle_conciliado(client: TestClient, db: Session) -> None:
    req, catalog = approved_requisition(client)
    almacenista = auth_header(client, "demo.almacenista")
    warehouse_id = uuid.UUID(catalog["warehouse"])
    item_id = uuid.UUID(catalog["items"][0])
    line_id = req["lines"][0]["id"]

    before = _reconciliation(db, warehouse_id, item_id)
    assert before["estado"] == "SIN_DETALLE"

    reserve = client.post(
        "/api/v1/inventory/reservations",
        headers=almacenista,
        json={
            "requisition_line_id": line_id,
            "quantity": "6",
            "idempotency_key": "lote8-detalle-reserva",
        },
    )
    assert reserve.status_code == 201, reserve.text
    _assert_ok(db, warehouse_id, item_id, "120", "6")

    issue = client.post(
        "/api/v1/inventory/issues",
        headers=almacenista,
        json={
            "requisition_line_id": line_id,
            "quantity": "4",
            "reservation_id": reserve.json()["id"],
            "idempotency_key": "lote8-detalle-entrega",
        },
    )
    assert issue.status_code == 201, issue.text
    _assert_ok(db, warehouse_id, item_id, "116", "2")

    for reservation in db.execute(
        select(StockReservation).where(StockReservation.id == uuid.UUID(reserve.json()["id"]))
    ).scalars():
        reservation.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    db.flush()

    expired = client.post("/api/v1/inventory/reservations/expire", headers=auth_header(client))
    assert expired.status_code == 200, expired.text
    assert expired.json()["released"] >= 1
    _assert_ok(db, warehouse_id, item_id, "116", "0")
    db.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))


def test_recepcion_actualiza_proyeccion_detallada(client: TestClient, db: Session) -> None:
    catalog = catalogs(client, auth_header(client))
    warehouse_id = uuid.UUID(catalog["warehouse"])
    item_id = uuid.UUID(catalog["items"][0])
    warehouse = db.get(Warehouse, warehouse_id)
    admin = db.execute(select(AppUser).where(AppUser.username == "demo.admin")).scalar_one()

    movement = InventoryService.receive_stock(
        db,
        actor_id=admin.id,
        company_id=warehouse.company_id,
        mining_unit_id=warehouse.mining_unit_id,
        warehouse_id=warehouse_id,
        item_id=item_id,
        quantity=Decimal("5"),
        idempotency_key="lote8-detalle-recepcion",
        source_document_type="MANUAL_TEST",
        source_document_id=uuid.uuid4(),
    )
    db.flush()
    assert movement.movement_type == "RECEIPT"
    _assert_ok(db, warehouse_id, item_id, "125", "0")
    db.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))

    stock = availability(client, auth_header(client, "demo.almacenista"), catalog)
    assert Decimal(stock["on_hand_qty"]) == Decimal("125")


def test_detalle_backfilleado_con_varios_saldos_no_se_duplica(client: TestClient, db: Session) -> None:
    """El detalle agregado por el backfill sigue siendo válido al escribir."""
    catalog = catalogs(client, auth_header(client))
    warehouse_id = uuid.UUID(catalog["warehouse"])
    item_id = uuid.UUID(catalog["items"][0])
    warehouse = db.get(Warehouse, warehouse_id)
    admin = db.execute(select(AppUser).where(AppUser.username == "demo.admin")).scalar_one()

    extra_balance = StockBalance(
        warehouse_id=warehouse_id,
        item_id=item_id,
        lot_id=uuid.uuid4(),
        location_id=NULL_UUID,
        on_hand_qty=Decimal("5"),
        reserved_qty=Decimal("0"),
        created_by=admin.id,
    )
    db.add(extra_balance)
    db.flush()
    legacy_balance = db.execute(
        select(StockBalance).where(
            StockBalance.warehouse_id == warehouse_id,
            StockBalance.item_id == item_id,
            StockBalance.lot_id == NULL_UUID,
            StockBalance.location_id == NULL_UUID,
        )
    ).scalar_one()
    db.add(
        StockBalanceDetail(
            stock_balance_id=min(legacy_balance.id, extra_balance.id),
            warehouse_id=warehouse_id,
            item_id=item_id,
            lot_ref_id=None,
            serial_id=None,
            stock_state="AVAILABLE",
            location_ref_id=None,
            on_hand_qty=Decimal("125"),
            reserved_qty=Decimal("0"),
            created_by=admin.id,
        )
    )
    db.flush()
    backfill_detail_id = db.execute(
        select(StockBalanceDetail.id).where(
            StockBalanceDetail.warehouse_id == warehouse_id,
            StockBalanceDetail.item_id == item_id,
        )
    ).scalar_one()
    backfilled = _reconciliation(db, warehouse_id, item_id)
    assert backfilled["estado"] == "OK"
    assert Decimal(str(backfilled["legacy_on_hand_qty"])) == Decimal("125")

    InventoryService.receive_stock(
        db,
        actor_id=admin.id,
        company_id=warehouse.company_id,
        mining_unit_id=warehouse.mining_unit_id,
        warehouse_id=warehouse_id,
        item_id=item_id,
        quantity=Decimal("1"),
        idempotency_key="lote8-detalle-backfill-recepcion",
        source_document_type="MANUAL_TEST",
        source_document_id=uuid.uuid4(),
    )
    db.flush()
    _assert_ok(db, warehouse_id, item_id, "126", "0")
    details = db.execute(
        select(StockBalanceDetail).where(
            StockBalanceDetail.warehouse_id == warehouse_id,
            StockBalanceDetail.item_id == item_id,
        )
    ).scalars().all()
    scopes = [(row.lot_ref_id, row.serial_id, row.stock_state, row.location_ref_id) for row in details]
    assert len(scopes) == len(set(scopes)), "No debe duplicarse un ámbito canónico"
    assert backfill_detail_id in {row.id for row in details}, "El detalle del backfill debe conservarse"
    db.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
