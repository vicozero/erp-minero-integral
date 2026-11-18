from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base


class CostCenter(AuditMixin, Base):
    __tablename__ = "cost_center"
    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_company_code"),
        {"schema": "cost"},
    )

    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("org.company.id", ondelete="RESTRICT"), nullable=False)
    mining_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("org.mining_unit.id", ondelete="RESTRICT"), nullable=True
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cost.cost_center.id", ondelete="RESTRICT"), nullable=True
    )
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)


class CostLayer(AuditMixin, Base):
    __tablename__ = "cost_layer"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positiva"),
        CheckConstraint("remaining_qty >= 0", name="remaining_no_negativo"),
        CheckConstraint("unit_cost >= 0", name="unit_cost_no_negativo"),
        {"schema": "cost"},
    )

    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mdm.item.id", ondelete="RESTRICT"), nullable=False)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("org.warehouse.id", ondelete="RESTRICT"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    remaining_qty: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    source_document_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
