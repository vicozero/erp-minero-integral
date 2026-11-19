"""Consultas conectadas del almacén virtual interactivo (Lote 6).

Todas las cifras se derivan de ``inv.stock_balance``, ``inv.stock_movement`` y
``mdm.storage_location``. Este servicio es de sólo lectura: nunca modifica
saldos, ubicaciones ni documentos.
"""

from __future__ import annotations

import uuid
from decimal import Decimal, ROUND_HALF_UP

from fastapi import status
from sqlalchemy import and_, false, func, select
from sqlalchemy.orm import Session

from app.modules.inventory.models import StockBalance, StockMovement
from app.modules.inventory.wms_service import (
    _dec,
    _fail,
    _warehouse_condition,
    build_location_path,
)
from app.modules.master_data.models import (
    Item,
    ItemCrossReference,
    ItemFamily,
    ItemSupplier,
    LocationRestriction,
    Lot,
    Serial,
    StorageLocation,
    Uom,
)
from app.modules.organization.models import MiningUnit, Warehouse

_ZERO = Decimal("0")
_HUNDRED = Decimal("100")
_PCT_QUANT = Decimal("0.01")


def _pct(part: Decimal, total: Decimal) -> Decimal | None:
    if total <= _ZERO:
        return None
    return (part * _HUNDRED / total).quantize(_PCT_QUANT, rounding=ROUND_HALF_UP)


def _movement_out(movement) -> dict:
    return {
        "id": movement.id,
        "movement_no": movement.movement_no,
        "movement_type": movement.movement_type,
        "direction": movement.direction,
        "quantity": _dec(movement.quantity),
        "balance_after_qty": _dec(movement.balance_after_qty),
        "posted_at": movement.posted_at,
        "source_document_type": movement.source_document_type,
    }


class WmsDashboardService:
    """Proyecciones de inventario real para la vista interactiva."""

    @staticmethod
    def location_inventory(
        db: Session,
        location_id: uuid.UUID,
        warehouse_ids: list[uuid.UUID] | None,
        *,
        can_view_cost: bool,
    ) -> dict:
        base = next(
            (
                row
                for row in _locations_with_occupancy(db, warehouse_ids, location_id=location_id)
                if row["id"] == location_id
            ),
            None,
        )
        if base is None:
            _fail("Ubicación inexistente o fuera de su alcance.", status.HTTP_404_NOT_FOUND)

        internal_codes = {
            item_id: code
            for item_id, code in db.execute(
                select(ItemCrossReference.item_id, ItemCrossReference.reference_code).where(
                    ItemCrossReference.reference_type == "INTERNAL"
                )
            )
        }
        supplier_costs = {
            item_id: cost
            for item_id, cost in db.execute(
                select(ItemSupplier.item_id, ItemSupplier.last_unit_cost).where(
                    ItemSupplier.status == "ACTIVE", ItemSupplier.preferred.is_(True)
                )
            )
        }
        serials: dict[uuid.UUID, list[str]] = {}
        for item_id, serial_number in db.execute(
            select(Serial.item_id, Serial.serial_number).where(
                Serial.current_location_id == location_id
            )
        ):
            serials.setdefault(item_id, []).append(serial_number)

        stock_rows = db.execute(
            select(
                StockBalance,
                Item,
                Uom.code.label("uom_code"),
                Lot.lot_number,
            )
            .join(Item, Item.id == StockBalance.item_id)
            .outerjoin(Uom, Uom.id == Item.uom_id)
            .outerjoin(Lot, Lot.id == StockBalance.lot_ref_id)
            .where(StockBalance.location_ref_id == location_id)
            .order_by(Item.code, Lot.lot_number)
        )
        items: list[dict] = []
        for balance, item, uom_code, lot_number in stock_rows:
            on_hand = _dec(balance.on_hand_qty)
            reserved = _dec(balance.reserved_qty)
            unit_cost = None
            if can_view_cost:
                unit_cost = supplier_costs.get(item.id) or _dec(item.standard_cost)
            items.append(
                {
                    "item_id": item.id,
                    "code": item.code,
                    "description": item.description,
                    "manufacturer_part_no": item.manufacturer_part_no,
                    "internal_code": internal_codes.get(item.id),
                    "lot_number": lot_number,
                    "serial_number": ", ".join(serials.get(item.id, [])) or None,
                    "on_hand_qty": on_hand,
                    "reserved_qty": reserved,
                    "available_qty": on_hand - reserved,
                    "uom_code": uom_code or "UN",
                    "unit_cost": unit_cost,
                    "last_movement": None,
                }
            )

        movements = db.execute(
            select(StockMovement)
            .where(StockMovement.location_ref_id == location_id)
            .order_by(StockMovement.posted_at.desc(), StockMovement.movement_no.desc())
            .limit(500)
        ).scalars()
        by_item: dict[uuid.UUID, dict] = {}
        for movement in movements:
            if movement.item_id not in by_item:
                by_item[movement.item_id] = _movement_out(movement)
        for item in items:
            item["last_movement"] = by_item.get(item["item_id"])
        last_movement = next(iter(by_item.values()), None)

        restrictions = [
            {
                "item_family_id": row.item_family_id,
                "item_family_name": family_name,
                "item_id": row.item_id,
                "item_code": item_code,
                "max_qty": row.max_qty,
                "temperature_min": row.temperature_min,
                "temperature_max": row.temperature_max,
                "allows_lot_mix": row.allows_lot_mix,
                "allows_serial_mix": row.allows_serial_mix,
            }
            for row, family_name, item_code in db.execute(
                select(
                    LocationRestriction,
                    ItemFamily.name,
                    Item.code,
                )
                .outerjoin(ItemFamily, ItemFamily.id == LocationRestriction.item_family_id)
                .outerjoin(Item, Item.id == LocationRestriction.item_id)
                .where(LocationRestriction.location_id == location_id)
                .order_by(ItemFamily.name, Item.code)
            )
        ]

        capacity = _dec(base["capacity_qty"])
        occupied = _dec(base["occupied_qty"])
        return {
            **{
                key: base[key]
                for key in (
                    "id",
                    "warehouse_id",
                    "warehouse_code",
                    "code",
                    "hierarchy_path",
                    "zone",
                    "aisle",
                    "rack",
                    "level",
                    "position",
                    "location_type",
                    "status",
                    "is_pickable",
                    "is_receivable",
                    "coord_x",
                    "coord_y",
                    "item_count",
                )
            },
            "location_id": base["id"],
            "capacity_qty": capacity,
            "occupied_qty": occupied,
            "occupancy_pct": _pct(occupied, capacity),
            "items": items,
            "last_movement": last_movement,
            "restrictions": restrictions,
            "can_view_cost": can_view_cost,
            "is_empty": not items,
        }

    @staticmethod
    def dashboard(
        db: Session,
        warehouse_ids: list[uuid.UUID] | None,
        *,
        warehouse_id: uuid.UUID | None = None,
        zone: str | None = None,
        family_id: uuid.UUID | None = None,
    ) -> dict:
        locations = _locations_with_occupancy(
            db, warehouse_ids, warehouse_id=warehouse_id, zone=zone
        )
        occupied = [row for row in locations if _dec(row["occupied_qty"]) > _ZERO]
        blocked = [row for row in locations if row["status"] == "BLOCKED"]
        inactive = [row for row in locations if row["status"] == "INACTIVE"]
        with_capacity = [row for row in locations if _dec(row["capacity_qty"]) > _ZERO]
        capacity_qty = sum((_dec(row["capacity_qty"]) for row in with_capacity), _ZERO)
        occupied_in_capacity = sum((_dec(row["occupied_qty"]) for row in with_capacity), _ZERO)

        empty = [
            row
            for row in locations
            if _dec(row["occupied_qty"]) == _ZERO and row["status"] == "ACTIVE"
        ]
        totals = {
            "location_count": len(locations),
            "occupied": len(occupied),
            "empty": len(empty),
            "blocked": len(blocked),
            "inactive": len(inactive),
            "capacity_defined_count": len(with_capacity),
            "capacity_qty": capacity_qty,
            "occupied_in_capacity_qty": occupied_in_capacity,
            "capacity_used_pct": _pct(occupied_in_capacity, capacity_qty) if with_capacity else None,
        }
        return {
            "warehouse_id": warehouse_id,
            "zone": zone,
            "family_id": family_id,
            "totals": totals,
            "alerts": _alerts(
                db, warehouse_ids, warehouse_id=warehouse_id, family_id=family_id
            ),
        }

    @staticmethod
    def material_search(
        db: Session,
        warehouse_ids: list[uuid.UUID] | None,
        *,
        query: str,
        warehouse_id: uuid.UUID | None = None,
        zone: str | None = None,
        family_id: uuid.UUID | None = None,
        limit: int = 50,
    ) -> dict:
        from app.modules.inventory.wms_service import WmsCatalogService

        matches = WmsCatalogService.search_items(
            db,
            warehouse_ids=warehouse_ids,
            query=query,
            family_id=family_id,
            warehouse_id=warehouse_id,
            active_only=True,
            limit=min(max(limit, 1), 100),
            offset=0,
        )
        item_ids = [row["id"] for row in matches]
        internal_codes = {
            item_id: code
            for item_id, code in db.execute(
                select(ItemCrossReference.item_id, ItemCrossReference.reference_code).where(
                    ItemCrossReference.reference_type == "INTERNAL",
                    ItemCrossReference.item_id.in_(item_ids) if item_ids else false(),
                )
            )
        }
        located: dict[uuid.UUID, list[dict]] = {item_id: [] for item_id in item_ids}
        location_ids: list[uuid.UUID] = []
        if item_ids:
            stmt = (
                select(
                    StockBalance.item_id,
                    StorageLocation,
                    Warehouse.code.label("warehouse_code"),
                    MiningUnit.code.label("unit_code"),
                    StockBalance.on_hand_qty,
                    StockBalance.reserved_qty,
                )
                .join(StorageLocation, StorageLocation.id == StockBalance.location_ref_id)
                .join(Warehouse, Warehouse.id == StockBalance.warehouse_id)
                .outerjoin(MiningUnit, MiningUnit.id == Warehouse.mining_unit_id)
                .where(StockBalance.item_id.in_(item_ids))
            )
            allowed = _warehouse_condition(warehouse_ids, StockBalance.warehouse_id)
            if allowed is not None:
                stmt = stmt.where(allowed)
            if warehouse_id is not None:
                stmt = stmt.where(StockBalance.warehouse_id == warehouse_id)
            if zone:
                stmt = stmt.where(func.upper(StorageLocation.zone) == zone.strip().upper())
            stmt = stmt.order_by(Warehouse.code, StorageLocation.code)
            for item_id, location, warehouse_code, unit_code, on_hand, reserved in db.execute(stmt):
                on_hand_dec = _dec(on_hand)
                reserved_dec = _dec(reserved)
                if location.id not in location_ids:
                    location_ids.append(location.id)
                located[item_id].append(
                    {
                        "location_id": location.id,
                        "location_code": location.code,
                        "hierarchy_path": build_location_path(unit_code, warehouse_code, location),
                        "zone": location.zone,
                        "aisle": location.aisle,
                        "rack": location.rack,
                        "level": location.level,
                        "position": location.position,
                        "coord_x": location.coord_x,
                        "coord_y": location.coord_y,
                        "status": location.status,
                        "on_hand_qty": on_hand_dec,
                        "reserved_qty": reserved_dec,
                        "available_qty": on_hand_dec - reserved_dec,
                    }
                )

        materials = [
            {
                "item_id": row["id"],
                "code": row["code"],
                "description": row["description"],
                "manufacturer_part_no": row["manufacturer_part_no"],
                "internal_code": internal_codes.get(row["id"]),
                "family_name": row["family_name"],
                "uom_code": row["uom_code"],
                "on_hand_qty": _dec(row["on_hand_qty"]),
                "available_qty": _dec(row["available_qty"]),
                "location_count": int(row["location_count"] or 0),
                "locations": located[row["id"]],
            }
            for row in matches
        ]
        return {"query": query, "materials": materials, "location_ids": location_ids}


def _locations_with_occupancy(
    db: Session,
    warehouse_ids: list[uuid.UUID] | None,
    *,
    warehouse_id: uuid.UUID | None = None,
    zone: str | None = None,
    location_id: uuid.UUID | None = None,
) -> list[dict]:
    if warehouse_ids is not None and not warehouse_ids:
        return []
    occupancy = (
        select(
            StockBalance.location_ref_id.label("location_id"),
            func.coalesce(func.sum(StockBalance.on_hand_qty), 0).label("occupied_qty"),
            func.count(func.distinct(StockBalance.item_id)).label("item_count"),
        )
        .where(StockBalance.location_ref_id.is_not(None))
        .group_by(StockBalance.location_ref_id)
        .subquery()
    )
    stmt = (
        select(
            StorageLocation,
            Warehouse.code.label("warehouse_code"),
            MiningUnit.code.label("unit_code"),
            func.coalesce(occupancy.c.occupied_qty, 0).label("occupied_qty"),
            func.coalesce(occupancy.c.item_count, 0).label("item_count"),
        )
        .join(Warehouse, Warehouse.id == StorageLocation.warehouse_id)
        .outerjoin(MiningUnit, MiningUnit.id == Warehouse.mining_unit_id)
        .outerjoin(occupancy, occupancy.c.location_id == StorageLocation.id)
    )
    allowed = _warehouse_condition(warehouse_ids, StorageLocation.warehouse_id)
    if allowed is not None:
        stmt = stmt.where(allowed)
    if warehouse_id is not None:
        stmt = stmt.where(StorageLocation.warehouse_id == warehouse_id)
    if zone:
        stmt = stmt.where(func.upper(StorageLocation.zone) == zone.strip().upper())
    if location_id is not None:
        stmt = stmt.where(StorageLocation.id == location_id)
    stmt = stmt.order_by(Warehouse.code, StorageLocation.code)
    return [
        {
            "id": location.id,
            "warehouse_id": location.warehouse_id,
            "warehouse_code": warehouse_code,
            "code": location.code,
            "hierarchy_path": build_location_path(unit_code, warehouse_code, location),
            "zone": location.zone,
            "aisle": location.aisle,
            "rack": location.rack,
            "level": location.level,
            "position": location.position,
            "location_type": location.location_type,
            "status": location.status,
            "is_pickable": location.is_pickable,
            "is_receivable": location.is_receivable,
            "coord_x": location.coord_x,
            "coord_y": location.coord_y,
            "capacity_qty": _dec(location.capacity_qty),
            "occupied_qty": _dec(occupied_qty),
            "item_count": int(item_count or 0),
        }
        for location, warehouse_code, unit_code, occupied_qty, item_count in db.execute(stmt)
    ]


def _alerts(
    db: Session,
    warehouse_ids: list[uuid.UUID] | None,
    *,
    warehouse_id: uuid.UUID | None,
    family_id: uuid.UUID | None,
) -> dict:
    empty: dict[str, list[dict]] = {"critical": [], "below_minimum": [], "unlocated": []}
    if warehouse_ids is not None and not warehouse_ids:
        return empty

    # El alcance se aplica dentro del JOIN: los artículos sin saldo en el
    # almacén permitido aparecen con existencia cero, nunca con saldos de un
    # almacén fuera del alcance del usuario.
    stock_conditions = [StockBalance.item_id == Item.id]
    allowed = _warehouse_condition(warehouse_ids, StockBalance.warehouse_id)
    if allowed is not None:
        stock_conditions.append(allowed)
    if warehouse_id is not None:
        stock_conditions.append(StockBalance.warehouse_id == warehouse_id)
    stmt = (
        select(
            Item,
            Uom.code.label("uom_code"),
            func.coalesce(func.sum(StockBalance.on_hand_qty), 0).label("on_hand_qty"),
            func.count(func.distinct(StockBalance.location_ref_id)).label("location_count"),
        )
        .outerjoin(Uom, Uom.id == Item.uom_id)
        .outerjoin(StockBalance, and_(*stock_conditions))
        .where(Item.is_active.is_(True))
    )
    if family_id is not None:
        stmt = stmt.where(Item.family_id == family_id)
    stmt = stmt.group_by(Item.id, Uom.code).order_by(Item.code)

    critical: list[dict] = []
    below_minimum: list[dict] = []
    for item, uom_code, on_hand_raw, location_count in db.execute(stmt):
        on_hand = _dec(on_hand_raw)
        reorder = _dec(item.reorder_point) if item.reorder_point is not None else None
        safety = _dec(item.safety_stock) if item.safety_stock is not None else None
        common = {
            "item_id": item.id,
            "code": item.code,
            "description": item.description,
            "uom_code": uom_code or "UN",
            "on_hand_qty": on_hand,
            "reorder_point": reorder,
            "safety_stock": safety,
            "location_count": int(location_count or 0),
        }
        if safety is not None and on_hand <= safety:
            critical.append({**common, "reason": "Existencia en o por debajo del stock de seguridad"})
        elif reorder is not None and reorder > _ZERO and on_hand <= _ZERO:
            critical.append({**common, "reason": "Sin existencias con punto de reordeno definido"})
        if reorder is not None and reorder > _ZERO and on_hand < reorder:
            below_minimum.append({**common, "reason": "Existencia por debajo del mínimo"})

    unlocated_stmt = (
        select(
            Item,
            Uom.code.label("uom_code"),
            func.sum(StockBalance.on_hand_qty).label("on_hand_qty"),
        )
        .join(StockBalance, StockBalance.item_id == Item.id)
        .outerjoin(Uom, Uom.id == Item.uom_id)
        .where(StockBalance.location_ref_id.is_(None), StockBalance.on_hand_qty > _ZERO)
    )
    allowed = _warehouse_condition(warehouse_ids, StockBalance.warehouse_id)
    if allowed is not None:
        unlocated_stmt = unlocated_stmt.where(allowed)
    if warehouse_id is not None:
        unlocated_stmt = unlocated_stmt.where(StockBalance.warehouse_id == warehouse_id)
    if family_id is not None:
        unlocated_stmt = unlocated_stmt.where(Item.family_id == family_id)
    unlocated_stmt = unlocated_stmt.group_by(Item.id, Uom.code).order_by(Item.code)
    unlocated = [
        {
            "item_id": item.id,
            "code": item.code,
            "description": item.description,
            "uom_code": uom_code or "UN",
            "on_hand_qty": _dec(on_hand),
        }
        for item, uom_code, on_hand in db.execute(unlocated_stmt)
    ]
    return {"critical": critical, "below_minimum": below_minimum, "unlocated": unlocated}
