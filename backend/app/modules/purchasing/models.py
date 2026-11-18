from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import AuditMixin, Base
from app.shared.constants import PURCHASE_ORDER_STATUSES


class PurchaseOrder(AuditMixin, Base):
    __tablename__ = "purchase_order"
    __table_args__ = (
        UniqueConstraint("document_registry_id", name="uq_po_document"),
        CheckConstraint("status IN ('" + "','".join(PURCHASE_ORDER_STATUSES) + "')", name="status_valido"),
        {"schema": "pur"},
    )

    document_no: Mapped[str] = mapped_column(String(60), nullable=False)
    document_registry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("doc.document_registry.id", ondelete="RESTRICT"), nullable=False
    )
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("org.company.id", ondelete="RESTRICT"), nullable=False)
    mining_unit_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("org.mining_unit.id", ondelete="RESTRICT"), nullable=False
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mdm.supplier.id", ondelete="RESTRICT"), nullable=False)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("org.warehouse.id", ondelete="RESTRICT"), nullable=False)
    buyer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("seg.app_user.id", ondelete="RESTRICT"), nullable=False)
    requisition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("req.requisition.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(30), default="DRAFT", nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="MXN", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(nullable=True)

    lines: Mapped[list["PurchaseOrderLine"]] = relationship(back_populates="purchase_order")


class PurchaseOrderLine(AuditMixin, Base):
    __tablename__ = "purchase_order_line"
    __table_args__ = (
        UniqueConstraint("purchase_order_id", "line_no", name="uq_po_line"),
        CheckConstraint("ordered_qty > 0", name="ordered_positiva"),
        CheckConstraint("received_qty >= 0", name="received_no_negativa"),
        CheckConstraint("cancelled_qty >= 0", name="cancelled_no_negativa"),
        CheckConstraint("unit_price >= 0", name="unit_price_no_negativo"),
        {"schema": "pur"},
    )

    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pur.purchase_order.id", ondelete="RESTRICT"), nullable=False
    )
    line_no: Mapped[int] = mapped_column(nullable=False)
    requisition_line_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("req.requisition_line.id", ondelete="RESTRICT"), nullable=False
    )
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mdm.item.id", ondelete="RESTRICT"), nullable=False)
    uom_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mdm.uom.id", ondelete="RESTRICT"), nullable=False)
    ordered_qty: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    received_qty: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"), nullable=False)
    cancelled_qty: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)

    purchase_order: Mapped["PurchaseOrder"] = relationship(back_populates="lines")


class GoodsReceipt(AuditMixin, Base):
    __tablename__ = "goods_receipt"
    __table_args__ = (
        UniqueConstraint("document_registry_id", name="uq_grn_document"),
        UniqueConstraint("idempotency_key", name="uq_grn_idem"),
        {"schema": "pur"},
    )

    document_no: Mapped[str] = mapped_column(String(60), nullable=False)
    document_registry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("doc.document_registry.id", ondelete="RESTRICT"), nullable=False
    )
    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pur.purchase_order.id", ondelete="RESTRICT"), nullable=False
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("org.warehouse.id", ondelete="RESTRICT"), nullable=False)
    received_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("seg.app_user.id", ondelete="RESTRICT"), nullable=False)
    received_at: Mapped[datetime] = mapped_column(default=func.now(), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)


class GoodsReceiptLine(Base):
    __tablename__ = "goods_receipt_line"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positiva"),
        {"schema": "pur"},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    goods_receipt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pur.goods_receipt.id", ondelete="RESTRICT"), nullable=False
    )
    purchase_order_line_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pur.purchase_order_line.id", ondelete="RESTRICT"), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    stock_movement_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("inv.stock_movement.id", ondelete="RESTRICT"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(default=func.now(), nullable=False)
