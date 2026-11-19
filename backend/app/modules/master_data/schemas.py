from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class FamilyIn(BaseModel):
    code: str = Field(min_length=2, max_length=40, pattern=r"^[A-Z0-9][A-Z0-9_.-]*$")
    name: str = Field(min_length=3, max_length=160)
    parent_id: uuid.UUID | None = None
    is_active: bool = True


class FamilyOut(ORMModel):
    id: uuid.UUID
    code: str
    name: str
    parent_id: uuid.UUID | None
    is_active: bool


class LocationIn(BaseModel):
    warehouse_id: uuid.UUID
    code: str = Field(min_length=3, max_length=80, pattern=r"^[A-Z0-9][A-Z0-9_.-]*$")
    parent_id: uuid.UUID | None = None
    zone: str | None = Field(default=None, max_length=20)
    aisle: str | None = Field(default=None, max_length=20)
    rack: str | None = Field(default=None, max_length=20)
    level: str | None = Field(default=None, max_length=20)
    position: str | None = Field(default=None, max_length=20)
    coord_x: Decimal | None = Field(default=None, ge=0)
    coord_y: Decimal | None = Field(default=None, ge=0)
    location_type: str = Field(
        default="STANDARD",
        pattern=r"^(RECEIPT|STANDARD|QUARANTINE|DISPATCH|TRANSIT|SCRAP)$",
    )
    capacity_qty: Decimal = Field(default=Decimal("0"), ge=0)
    status: str = Field(default="ACTIVE", pattern=r"^(ACTIVE|BLOCKED|INACTIVE)$")
    is_pickable: bool = True
    is_receivable: bool = True


class LocationCoordinatesIn(BaseModel):
    coord_x: Decimal = Field(ge=0)
    coord_y: Decimal = Field(ge=0)


class LocationOut(ORMModel):
    id: uuid.UUID
    warehouse_id: uuid.UUID
    warehouse_code: str
    code: str
    parent_id: uuid.UUID | None
    zone: str | None
    aisle: str | None
    rack: str | None
    level: str | None
    position: str | None
    location_type: str
    qr_token: str
    capacity_qty: Decimal
    status: str
    is_pickable: bool
    is_receivable: bool
    coord_x: Decimal | None
    coord_y: Decimal | None
    hierarchy_path: str
    occupied_qty: Decimal
    item_count: int


class RestrictionOut(ORMModel):
    item_family_id: uuid.UUID | None
    item_id: uuid.UUID | None
    max_qty: Decimal | None
    allows_lot_mix: bool
    allows_serial_mix: bool


class StockLocationOut(ORMModel):
    location_id: uuid.UUID
    location_code: str
    warehouse_code: str
    zone: str | None
    aisle: str | None
    lot_number: str | None
    on_hand_qty: Decimal
    reserved_qty: Decimal
    available_qty: Decimal


class LocationDetailOut(LocationOut):
    restrictions: list[RestrictionOut]
    items: list[StockLocationOut]


class LotOut(ORMModel):
    id: uuid.UUID
    lot_number: str
    status: str
    manufactured_at: datetime | None
    expiry_date: date | None


class SerialOut(ORMModel):
    id: uuid.UUID
    serial_number: str
    status: str
    lot_id: uuid.UUID | None
    current_location_id: uuid.UUID | None


class CrossReferenceOut(ORMModel):
    id: uuid.UUID
    reference_type: str
    reference_code: str
    equivalent_item_id: uuid.UUID | None
    authorised: bool


class ItemSupplierOut(ORMModel):
    id: uuid.UUID
    supplier_id: uuid.UUID
    supplier_name: str
    supplier_part_number: str | None
    lead_time_days: int
    min_order_qty: Decimal
    preferred: bool
    last_unit_cost: Decimal | None
    currency: str


class WmsMovementOut(ORMModel):
    id: uuid.UUID
    movement_no: str
    movement_type: str
    direction: str
    quantity: Decimal
    balance_after_qty: Decimal
    posted_at: datetime
    source_document_type: str


class RelatedDocumentOut(ORMModel):
    document_no: str
    document_type: str
    status: str
    occurred_at: datetime


class ItemSearchOut(ORMModel):
    id: uuid.UUID
    code: str
    description: str
    family_id: uuid.UUID | None
    family_name: str | None
    manufacturer: str | None
    manufacturer_part_no: str | None
    barcode: str | None
    uom_id: uuid.UUID
    uom_code: str
    standard_cost: Decimal
    lot_tracked: bool
    serial_tracked: bool
    is_consumable: bool
    is_returnable: bool
    is_tool: bool
    is_active: bool
    on_hand_qty: Decimal
    reserved_qty: Decimal
    available_qty: Decimal
    location_count: int


class ItemDetailOut(ItemSearchOut):
    image_url: str | None
    supplier_name: str | None
    default_supplier_id: uuid.UUID | None
    reorder_point: Decimal | None
    safety_stock: Decimal | None
    max_stock: Decimal | None
    weight_kg: Decimal | None
    volume_m3: Decimal | None
    storage_temperature_min: Decimal | None
    storage_temperature_max: Decimal | None
    locations: list[StockLocationOut]
    lots: list[LotOut]
    serials: list[SerialOut]
    cross_references: list[CrossReferenceOut]
    suppliers: list[ItemSupplierOut]
    movements: list[WmsMovementOut]
    related_documents: list[RelatedDocumentOut]


class PhotoOut(ORMModel):
    item_id: uuid.UUID
    image_path: str
    image_sha256: str
    image_url: str
