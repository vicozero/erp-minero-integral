from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import AuditMixin, Base
from app.shared.constants import REQUISITION_LINE_STATUSES, REQUISITION_STATUSES


class Requisition(AuditMixin, Base):
    __tablename__ = "requisition"
    __table_args__ = (
        UniqueConstraint("document_registry_id", name="uq_document_registry"),
        CheckConstraint("status IN ('" + "','".join(REQUISITION_STATUSES) + "')", name="status_valido"),
        CheckConstraint(
            "requisition_type IN ('STOCK','PURCHASE','SERVICE')", name="requisition_type_valido"
        ),
        CheckConstraint("priority IN ('LOW','NORMAL','HIGH','URGENT')", name="priority_valida"),
        {"schema": "req"},
    )

    document_no: Mapped[str] = mapped_column(String(60), nullable=False)
    document_registry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("doc.document_registry.id", ondelete="RESTRICT"), nullable=False
    )
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("org.company.id", ondelete="RESTRICT"), nullable=False)
    mining_unit_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("org.mining_unit.id", ondelete="RESTRICT"), nullable=False
    )
    department_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("org.department.id", ondelete="RESTRICT"), nullable=False
    )
    warehouse_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("org.warehouse.id", ondelete="RESTRICT"), nullable=True
    )
    equipment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("mnt.equipment.id", ondelete="RESTRICT"), nullable=True
    )
    cost_center_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cost.cost_center.id", ondelete="RESTRICT"), nullable=False
    )
    requester_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("seg.app_user.id", ondelete="RESTRICT"), nullable=False
    )
    requisition_type: Mapped[str] = mapped_column(String(20), default="STOCK", nullable=False)
    priority: Mapped[str] = mapped_column(String(20), default="NORMAL", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="DRAFT", nullable=False)
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    observations: Mapped[str | None] = mapped_column(Text, nullable=True)
    needed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    lines: Mapped[list["RequisitionLine"]] = relationship(back_populates="requisition")


class RequisitionLine(AuditMixin, Base):
    __tablename__ = "requisition_line"
    __table_args__ = (
        UniqueConstraint("requisition_id", "line_no", name="uq_requisition_line"),
        CheckConstraint("requested_qty > 0", name="requested_positiva"),
        CheckConstraint("authorised_qty >= 0", name="authorised_no_negativa"),
        CheckConstraint("cancelled_qty >= 0", name="cancelled_no_negativa"),
        CheckConstraint(
            "status IN ('" + "','".join(REQUISITION_LINE_STATUSES) + "')", name="status_valido"
        ),
        {"schema": "req"},
    )

    requisition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("req.requisition.id", ondelete="RESTRICT"), nullable=False
    )
    line_no: Mapped[int] = mapped_column(nullable=False)
    item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("mdm.item.id", ondelete="RESTRICT"), nullable=True
    )
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    uom_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mdm.uom.id", ondelete="RESTRICT"), nullable=False)
    requested_qty: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    authorised_qty: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"), nullable=False)
    cancelled_qty: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="OPEN", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    requisition: Mapped["Requisition"] = relationship(back_populates="lines")
