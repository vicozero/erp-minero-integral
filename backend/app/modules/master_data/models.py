from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base


class Uom(AuditMixin, Base):
    __tablename__ = "uom"
    __table_args__ = (UniqueConstraint("code", name="uq_uom_code"), {"schema": "mdm"})

    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    precision: Mapped[int] = mapped_column(default=2, nullable=False)


class Item(AuditMixin, Base):
    __tablename__ = "item"
    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_item_company_code"),
        CheckConstraint("item_type IN ('STOCK','SERVICE','FIXED_ASSET')", name="item_type_valido"),
        CheckConstraint("standard_cost >= 0", name="standard_cost_no_negativo"),
        {"schema": "mdm"},
    )

    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("org.company.id", ondelete="RESTRICT"), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    item_type: Mapped[str] = mapped_column(String(20), default="STOCK", nullable=False)
    uom_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mdm.uom.id", ondelete="RESTRICT"), nullable=False)
    purchase_uom_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("mdm.uom.id", ondelete="RESTRICT"), nullable=True
    )
    lot_tracked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    serial_tracked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    standard_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Lote A WMS — atributos ampliados del catálogo (migración aditiva).
    family_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("mdm.item_family.id", ondelete="RESTRICT"), nullable=True
    )
    manufacturer: Mapped[str | None] = mapped_column(String(120), nullable=True)
    manufacturer_part_no: Mapped[str | None] = mapped_column(String(80), nullable=True)
    barcode: Mapped[str | None] = mapped_column(String(80), nullable=True)
    image_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    image_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    volume_m3: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    storage_temperature_min: Mapped[Decimal | None] = mapped_column(Numeric(7, 2), nullable=True)
    storage_temperature_max: Mapped[Decimal | None] = mapped_column(Numeric(7, 2), nullable=True)
    is_consumable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_returnable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_tool: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    default_supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("mdm.supplier.id", ondelete="RESTRICT"), nullable=True
    )
    reorder_point: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    safety_stock: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    max_stock: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)


class ItemFamily(AuditMixin, Base):
    __tablename__ = "item_family"
    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_item_family_company_code"),
        {"schema": "mdm"},
    )

    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("org.company.id", ondelete="RESTRICT"), nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("mdm.item_family.id", ondelete="RESTRICT"), nullable=True
    )
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ItemUomConversion(AuditMixin, Base):
    __tablename__ = "item_uom_conversion"
    __table_args__ = (
        CheckConstraint("factor > 0", name="ck_item_uom_conversion_factor"),
        UniqueConstraint("item_id", "from_uom_id", "to_uom_id", "valid_from", name="uq_item_uom_conversion"),
        {"schema": "mdm"},
    )

    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mdm.item.id", ondelete="RESTRICT"), nullable=False)
    from_uom_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mdm.uom.id", ondelete="RESTRICT"), nullable=False)
    to_uom_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mdm.uom.id", ondelete="RESTRICT"), nullable=False)
    factor: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    is_base: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_purchase: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_issue: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    valid_from: Mapped[datetime] = mapped_column(nullable=False)
    valid_to: Mapped[datetime | None] = mapped_column(nullable=True)


class ItemCrossReference(AuditMixin, Base):
    __tablename__ = "item_cross_reference"
    __table_args__ = (
        CheckConstraint(
            "reference_type IN ('INTERNAL','MANUFACTURER','CONTPAQI','GMAO','CUSTOMER')",
            name="ck_item_xref_type",
        ),
        CheckConstraint("authorised = false OR approved_by IS NOT NULL", name="ck_item_xref_approval"),
        UniqueConstraint("item_id", "reference_type", "reference_code", name="uq_item_xref"),
        {"schema": "mdm"},
    )

    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mdm.item.id", ondelete="RESTRICT"), nullable=False)
    reference_type: Mapped[str] = mapped_column(String(20), nullable=False)
    reference_code: Mapped[str] = mapped_column(String(120), nullable=False)
    equivalent_item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("mdm.item.id", ondelete="RESTRICT"), nullable=True
    )
    authorised: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("seg.app_user.id", ondelete="RESTRICT"), nullable=True
    )
    valid_from: Mapped[datetime] = mapped_column(nullable=False)
    valid_to: Mapped[datetime | None] = mapped_column(nullable=True)
    source_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class ItemSupplier(AuditMixin, Base):
    __tablename__ = "item_supplier"
    __table_args__ = (
        CheckConstraint("lead_time_days >= 0", name="ck_item_supplier_lead"),
        CheckConstraint("min_order_qty >= 0", name="ck_item_supplier_moq"),
        CheckConstraint("last_unit_cost IS NULL OR last_unit_cost >= 0", name="ck_item_supplier_cost"),
        CheckConstraint("status IN ('ACTIVE','INACTIVE')", name="ck_item_supplier_status"),
        UniqueConstraint("item_id", "supplier_id", name="uq_item_supplier"),
        {"schema": "mdm"},
    )

    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mdm.item.id", ondelete="RESTRICT"), nullable=False)
    supplier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mdm.supplier.id", ondelete="RESTRICT"), nullable=False)
    supplier_part_number: Mapped[str | None] = mapped_column(String(80), nullable=True)
    lead_time_days: Mapped[int] = mapped_column(default=0, nullable=False)
    min_order_qty: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"), nullable=False)
    preferred: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="MXN", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)


class StorageLocation(AuditMixin, Base):
    __tablename__ = "storage_location"
    __table_args__ = (
        CheckConstraint(
            "location_type IN ('RECEIPT','STANDARD','QUARANTINE','DISPATCH','TRANSIT','SCRAP')",
            name="ck_storage_location_type",
        ),
        CheckConstraint("status IN ('ACTIVE','BLOCKED','INACTIVE')", name="ck_storage_location_status"),
        CheckConstraint("capacity_qty >= 0", name="ck_storage_location_capacity"),
        CheckConstraint(
            "(coord_x IS NULL AND coord_y IS NULL) OR (coord_x IS NOT NULL AND coord_y IS NOT NULL)",
            name="ck_storage_location_coordenadas",
        ),
        UniqueConstraint("warehouse_id", "code", name="uq_storage_location_code"),
        UniqueConstraint("qr_token", name="uq_storage_location_qr"),
        {"schema": "mdm"},
    )

    warehouse_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("org.warehouse.id", ondelete="RESTRICT"), nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("mdm.storage_location.id", ondelete="RESTRICT"), nullable=True
    )
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    zone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    aisle: Mapped[str | None] = mapped_column(String(20), nullable=True)
    rack: Mapped[str | None] = mapped_column(String(20), nullable=True)
    level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    position: Mapped[str | None] = mapped_column(String(20), nullable=True)
    location_type: Mapped[str] = mapped_column(String(20), nullable=False)
    qr_token: Mapped[str] = mapped_column(String(160), nullable=False)
    capacity_qty: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)
    is_pickable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_receivable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Almacén virtual: proyección 2D. No son existencias ni una fuente oficial.
    coord_x: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    coord_y: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)


class LocationRestriction(AuditMixin, Base):
    __tablename__ = "location_restriction"
    __table_args__ = (
        CheckConstraint("item_family_id IS NOT NULL OR item_id IS NOT NULL", name="ck_location_restriction_target"),
        CheckConstraint("max_qty IS NULL OR max_qty >= 0", name="ck_location_restriction_qty"),
        UniqueConstraint("location_id", "item_family_id", "item_id", name="uq_location_restriction"),
        {"schema": "mdm"},
    )

    location_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("mdm.storage_location.id", ondelete="RESTRICT"), nullable=False
    )
    item_family_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("mdm.item_family.id", ondelete="RESTRICT"), nullable=True
    )
    item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("mdm.item.id", ondelete="RESTRICT"), nullable=True)
    max_qty: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    temperature_min: Mapped[Decimal | None] = mapped_column(Numeric(7, 2), nullable=True)
    temperature_max: Mapped[Decimal | None] = mapped_column(Numeric(7, 2), nullable=True)
    allows_lot_mix: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    allows_serial_mix: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Lot(AuditMixin, Base):
    __tablename__ = "lot"
    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE','QUARANTINE','EXPIRED','BLOCKED')", name="ck_lot_status"),
        UniqueConstraint("item_id", "lot_number", name="uq_lot_item_number"),
        {"schema": "mdm"},
    )

    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mdm.item.id", ondelete="RESTRICT"), nullable=False)
    lot_number: Mapped[str] = mapped_column(String(80), nullable=False)
    manufactured_at: Mapped[datetime | None] = mapped_column(nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(120), nullable=True)


class Serial(AuditMixin, Base):
    __tablename__ = "serial"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE','ISSUED','RETURNED','DAMAGED','LOST','RETIRED')", name="ck_serial_status"
        ),
        UniqueConstraint("item_id", "serial_number", name="uq_serial_item_number"),
        {"schema": "mdm"},
    )

    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mdm.item.id", ondelete="RESTRICT"), nullable=False)
    serial_number: Mapped[str] = mapped_column(String(120), nullable=False)
    lot_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("mdm.lot.id", ondelete="RESTRICT"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)
    current_location_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("mdm.storage_location.id", ondelete="RESTRICT"), nullable=True
    )


class Supplier(AuditMixin, Base):
    __tablename__ = "supplier"
    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_supplier_company_code"),
        {"schema": "mdm"},
    )

    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("org.company.id", ondelete="RESTRICT"), nullable=False)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    payment_terms: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)
