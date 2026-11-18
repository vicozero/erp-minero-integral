from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base


class Uom(AuditMixin, Base):
    __tablename__ = "uom"
    __table_args__ = (UniqueConstraint("code", name="uq_code"), {"schema": "mdm"})

    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    precision: Mapped[int] = mapped_column(default=2, nullable=False)


class Item(AuditMixin, Base):
    __tablename__ = "item"
    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_company_code"),
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


class Supplier(AuditMixin, Base):
    __tablename__ = "supplier"
    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_company_code"),
        {"schema": "mdm"},
    )

    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("org.company.id", ondelete="RESTRICT"), nullable=False)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    payment_terms: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)
