"""Esquemas del almacén virtual interactivo (Lote 6).

Sólo exponen proyecciones de lectura construidas desde tablas transaccionales.
Ningún esquema aquí permite modificar saldos ni crear ubicaciones.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class WmsLastMovementOut(ORMModel):
    id: uuid.UUID
    movement_no: str
    movement_type: str
    direction: str
    quantity: Decimal
    balance_after_qty: Decimal
    posted_at: datetime
    source_document_type: str


class WmsLocationRestrictionOut(ORMModel):
    item_family_id: uuid.UUID | None
    item_family_name: str | None
    item_id: uuid.UUID | None
    item_code: str | None
    max_qty: Decimal | None
    temperature_min: Decimal | None
    temperature_max: Decimal | None
    allows_lot_mix: bool
    allows_serial_mix: bool


class LocationInventoryItemOut(ORMModel):
    item_id: uuid.UUID
    code: str
    description: str
    manufacturer_part_no: str | None
    internal_code: str | None
    lot_number: str | None
    serial_number: str | None
    on_hand_qty: Decimal
    reserved_qty: Decimal
    available_qty: Decimal
    uom_code: str
    unit_cost: Decimal | None
    last_movement: WmsLastMovementOut | None


class LocationInventoryOut(ORMModel):
    location_id: uuid.UUID
    warehouse_id: uuid.UUID
    warehouse_code: str
    code: str
    hierarchy_path: str
    zone: str | None
    aisle: str | None
    rack: str | None
    level: str | None
    position: str | None
    location_type: str
    status: str
    is_pickable: bool
    is_receivable: bool
    coord_x: Decimal | None
    coord_y: Decimal | None
    capacity_qty: Decimal
    occupied_qty: Decimal
    occupancy_pct: Decimal | None
    item_count: int
    items: list[LocationInventoryItemOut]
    last_movement: WmsLastMovementOut | None
    restrictions: list[WmsLocationRestrictionOut]
    can_view_cost: bool
    is_empty: bool


class DashboardTotalsOut(ORMModel):
    location_count: int
    occupied: int
    empty: int
    blocked: int
    inactive: int
    capacity_defined_count: int
    capacity_qty: Decimal
    occupied_in_capacity_qty: Decimal
    capacity_used_pct: Decimal | None


class StockAlertOut(ORMModel):
    item_id: uuid.UUID
    code: str
    description: str
    uom_code: str
    on_hand_qty: Decimal
    reorder_point: Decimal | None
    safety_stock: Decimal | None
    location_count: int
    reason: str


class UnlocatedMaterialOut(ORMModel):
    item_id: uuid.UUID
    code: str
    description: str
    uom_code: str
    on_hand_qty: Decimal


class DashboardAlertsOut(ORMModel):
    critical: list[StockAlertOut]
    below_minimum: list[StockAlertOut]
    unlocated: list[UnlocatedMaterialOut]


class WarehouseDashboardOut(ORMModel):
    warehouse_id: uuid.UUID | None
    zone: str | None
    family_id: uuid.UUID | None
    totals: DashboardTotalsOut
    alerts: DashboardAlertsOut


class MaterialLocationOut(ORMModel):
    location_id: uuid.UUID
    location_code: str
    hierarchy_path: str
    zone: str | None
    aisle: str | None
    rack: str | None
    level: str | None
    position: str | None
    coord_x: Decimal | None
    coord_y: Decimal | None
    status: str
    on_hand_qty: Decimal
    reserved_qty: Decimal
    available_qty: Decimal


class MaterialSearchOut(ORMModel):
    item_id: uuid.UUID
    code: str
    description: str
    manufacturer_part_no: str | None
    internal_code: str | None
    family_name: str | None
    uom_code: str
    on_hand_qty: Decimal
    available_qty: Decimal
    location_count: int
    locations: list[MaterialLocationOut]


class MaterialSearchResultOut(ORMModel):
    query: str
    materials: list[MaterialSearchOut]
    location_ids: list[uuid.UUID]
