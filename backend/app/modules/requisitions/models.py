from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Numeric, String, Text, UniqueConstraint, func
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
    work_order_no: Mapped[str | None] = mapped_column(String(80), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Orden determinista por número de partida (evita depender del orden físico).
    lines: Mapped[list["RequisitionLine"]] = relationship(
        back_populates="requisition", order_by="RequisitionLine.line_no"
    )


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


class RequisitionAttachment(Base):
    """Metadatos de un archivo adjunto almacenado fuera de la base.

    El contenido se guarda en un directorio controlado por configuración; en
    la base solo se conserva el nombre lógico, el nombre físico generado, el
    tipo MIME, el tamaño y el SHA-256 del contenido. Es append-only: solo se
    conservan ``id`` y ``created_at`` además de los datos del archivo.
    """

    __tablename__ = "requisition_attachment"
    __table_args__ = (
        UniqueConstraint("stored_name", name="uq_requisition_attachment_stored_name"),
        CheckConstraint("size_bytes > 0", name="ck_requisition_attachment_size"),
        {"schema": "req"},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(default=func.now(), nullable=False)
    requisition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("req.requisition.id", ondelete="RESTRICT"), nullable=False
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("seg.app_user.id", ondelete="RESTRICT"), nullable=False
    )
