from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base
from app.shared.constants import MOVEMENT_DIRECTIONS, MOVEMENT_TYPES, RESERVATION_STATUSES

NULL_UUID = uuid.UUID(int=0)


class StockBalance(AuditMixin, Base):
    __tablename__ = "stock_balance"
    __table_args__ = (
        UniqueConstraint("warehouse_id", "item_id", "lot_id", "location_id", name="uq_stock_scope"),
        CheckConstraint("on_hand_qty >= 0", name="on_hand_no_negativo"),
        CheckConstraint("reserved_qty >= 0", name="reserved_no_negativo"),
        CheckConstraint("on_hand_qty >= reserved_qty", name="reserved_dentro_de_existencia"),
        {"schema": "inv"},
    )

    warehouse_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("org.warehouse.id", ondelete="RESTRICT"), nullable=False)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mdm.item.id", ondelete="RESTRICT"), nullable=False)
    lot_id: Mapped[uuid.UUID] = mapped_column(default=NULL_UUID, nullable=False)
    location_id: Mapped[uuid.UUID] = mapped_column(default=NULL_UUID, nullable=False)
    on_hand_qty: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"), nullable=False)
    reserved_qty: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"), nullable=False)

    # Lote A WMS — referencias enriquecidas. Los UUID centinela heredados
    # (`lot_id`, `location_id`) se conservan intactos por compatibilidad.
    lot_ref_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("mdm.lot.id", ondelete="RESTRICT"), nullable=True
    )
    location_ref_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("mdm.storage_location.id", ondelete="RESTRICT"), nullable=True
    )


class StockReservation(AuditMixin, Base):
    __tablename__ = "stock_reservation"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_reservation_idem"),
        CheckConstraint("quantity > 0", name="quantity_positiva"),
        CheckConstraint("consumed_qty >= 0", name="consumed_no_negativo"),
        CheckConstraint("consumed_qty <= quantity", name="consumed_dentro_de_reserva"),
        CheckConstraint("status IN ('" + "','".join(RESERVATION_STATUSES) + "')", name="status_valido"),
        {"schema": "inv"},
    )

    reservation_no: Mapped[str] = mapped_column(String(60), nullable=False)
    requisition_line_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("req.requisition_line.id", ondelete="RESTRICT"), nullable=False
    )
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mdm.item.id", ondelete="RESTRICT"), nullable=False)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("org.warehouse.id", ondelete="RESTRICT"), nullable=False)
    lot_id: Mapped[uuid.UUID] = mapped_column(default=NULL_UUID, nullable=False)
    location_id: Mapped[uuid.UUID] = mapped_column(default=NULL_UUID, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    consumed_qty: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    lot_ref_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("mdm.lot.id", ondelete="RESTRICT"), nullable=True
    )
    location_ref_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("mdm.storage_location.id", ondelete="RESTRICT"), nullable=True
    )


class StockMovement(Base):
    __tablename__ = "stock_movement"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_movement_idem"),
        CheckConstraint("quantity > 0", name="quantity_positiva"),
        CheckConstraint("direction IN ('" + "','".join(MOVEMENT_DIRECTIONS) + "')", name="direccion_valida"),
        CheckConstraint("movement_type IN ('" + "','".join(MOVEMENT_TYPES) + "')", name="tipo_valido"),
        CheckConstraint("balance_after_qty >= 0", name="saldo_no_negativo"),
        {"schema": "inv"},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    movement_no: Mapped[str] = mapped_column(String(60), nullable=False)
    document_registry_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("doc.document_registry.id", ondelete="RESTRICT"), nullable=True
    )
    movement_type: Mapped[str] = mapped_column(String(30), nullable=False)
    direction: Mapped[str] = mapped_column(String(5), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mdm.item.id", ondelete="RESTRICT"), nullable=False)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("org.warehouse.id", ondelete="RESTRICT"), nullable=False)
    lot_id: Mapped[uuid.UUID] = mapped_column(default=NULL_UUID, nullable=False)
    location_id: Mapped[uuid.UUID] = mapped_column(default=NULL_UUID, nullable=False)
    balance_after_qty: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    requisition_line_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("req.requisition_line.id", ondelete="RESTRICT"), nullable=True
    )
    purchase_order_line_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("pur.purchase_order_line.id", ondelete="RESTRICT"), nullable=True
    )
    goods_receipt_line_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    source_document_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    reversal_of_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("inv.stock_movement.id", ondelete="RESTRICT"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default="POSTED", nullable=False)
    posted_at: Mapped[datetime] = mapped_column(default=func.now(), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("seg.app_user.id", ondelete="RESTRICT"), nullable=True
    )
    lot_ref_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("mdm.lot.id", ondelete="RESTRICT"), nullable=True
    )
    location_ref_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("mdm.storage_location.id", ondelete="RESTRICT"), nullable=True
    )


class LocationMap(AuditMixin, Base):
    """Versión inmutable del plano 2D de un almacén.

    Guarda sólo metadatos del fondo. Los nodos se derivan en cada consulta de
    ``mdm.storage_location`` (UB-010): esta tabla nunca es la fuente de verdad
    de las posiciones. ``is_exact`` permanece falso por diseño: ninguna imagen
    se presenta como plano exacto sin una decisión formal y una migración.
    """

    __tablename__ = "location_map"
    __table_args__ = (
        CheckConstraint("width > 0", name="ck_location_map_width"),
        CheckConstraint("height > 0", name="ck_location_map_height"),
        CheckConstraint("is_exact = false", name="ck_location_map_no_exacto"),
        CheckConstraint("map_version >= 1", name="ck_location_map_version"),
        UniqueConstraint("warehouse_id", "map_version", name="uq_location_map_version"),
        Index(
            "uq_location_map_active",
            "warehouse_id",
            unique=True,
            postgresql_where=text("is_active"),
        ),
        {"schema": "wms"},
    )

    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("org.warehouse.id", ondelete="RESTRICT"), nullable=False
    )
    map_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    label: Mapped[str] = mapped_column(
        String(120), default="Referencial · no es plano exacto", nullable=False
    )
    background_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    background_name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    background_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_exact: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    width: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("1000"), nullable=False)
    height: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("600"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
