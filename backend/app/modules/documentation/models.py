from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import AuditMixin, Base, JSON_DICT


class DocumentType(AuditMixin, Base):
    __tablename__ = "document_type"
    __table_args__ = (UniqueConstraint("code", name="uq_document_type_code"), {"schema": "doc"})

    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)


class DocumentNumbering(AuditMixin, Base):
    __tablename__ = "document_numbering"
    __table_args__ = (
        UniqueConstraint(
            "document_type_id",
            "company_id",
            "mining_unit_id",
            "series",
            "year",
            name="uq_numbering_scope",
        ),
        {"schema": "doc"},
    )

    document_type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("doc.document_type.id", ondelete="RESTRICT"), nullable=False
    )
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("org.company.id", ondelete="RESTRICT"), nullable=False)
    mining_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("org.mining_unit.id", ondelete="RESTRICT"), nullable=True
    )
    series: Mapped[str] = mapped_column(String(20), default="GEN", nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    next_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class DocumentRegistry(Base):
    __tablename__ = "document_registry"
    __table_args__ = (
        UniqueConstraint("full_number", name="uq_full_number"),
        {"schema": "doc"},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("doc.document_type.id", ondelete="RESTRICT"), nullable=False
    )
    numbering_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("doc.document_numbering.id", ondelete="RESTRICT"), nullable=False
    )
    full_number: Mapped[str] = mapped_column(String(60), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    issued_at: Mapped[datetime] = mapped_column(default=func.now(), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ISSUED", nullable=False)


class IdempotencyRecord(Base):
    """Reserva atómica de una clave de idempotencia.

    La restricción única de ``idempotency_key`` permite reclamar la operación
    con ``INSERT ... ON CONFLICT DO NOTHING RETURNING`` dentro de la misma
    transacción del cambio de negocio. No sustituye a las claves de las tablas
    de detalle; coordina su creación y permite reproductir el resultado.
    """

    __tablename__ = "idempotency_record"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_idempotency_record_key"),
        CheckConstraint(
            "status IN ('IN_PROGRESS','COMPLETED')", name="ck_idempotency_record_status"
        ),
        {"schema": "doc"},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    operation: Mapped[str] = mapped_column(String(60), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(60), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="IN_PROGRESS", nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)


class DocumentEvent(Base):
    __tablename__ = "document_event"
    __table_args__ = (
        Index("ix_document_event_registry", "document_registry_id", "occurred_at"),
        {"schema": "doc"},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_registry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("doc.document_registry.id", ondelete="RESTRICT"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("seg.app_user.id", ondelete="RESTRICT"), nullable=True
    )
    occurred_at: Mapped[datetime] = mapped_column(default=func.now(), nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSON_DICT, nullable=True)


class DocumentTemplate(AuditMixin, Base):
    """Plantilla versionada, inmutable después de su primera emisión."""

    __tablename__ = "document_template"
    __table_args__ = (
        UniqueConstraint("code", "template_version", name="uq_document_template_version"),
        {"schema": "doc"},
    )

    code: Mapped[str] = mapped_column(String(40), nullable=False)
    document_type_code: Mapped[str] = mapped_column(String(20), nullable=False)
    template_version: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_width_pt: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    page_height_pt: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    orientation: Mapped[str] = mapped_column(String(12), nullable=False)
    source_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)


class DocumentRender(Base):
    """Registro append-only de cada PDF/XLSX emitido o reimpreso."""

    __tablename__ = "document_render"
    __table_args__ = (
        UniqueConstraint("storage_name", name="uq_document_render_storage_name"),
        Index("ix_document_render_entity", "entity_type", "entity_id", "rendered_at"),
        {"schema": "doc"},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_template_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("doc.document_template.id", ondelete="RESTRICT"), nullable=False
    )
    entity_type: Mapped[str] = mapped_column(String(60), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    document_no: Mapped[str] = mapped_column(String(60), nullable=False)
    document_format: Mapped[str] = mapped_column(String(10), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    storage_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_reprint: Mapped[bool] = mapped_column(default=False, nullable=False)
    source_render_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("doc.document_render.id", ondelete="RESTRICT"), nullable=True
    )
    rendered_at: Mapped[datetime] = mapped_column(default=func.now(), nullable=False)
    rendered_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("seg.app_user.id", ondelete="RESTRICT"), nullable=True
    )
    metadata_json: Mapped[dict | None] = mapped_column(JSON_DICT, nullable=True)


class WarehouseVoucher(AuditMixin, Base):
    """Vale de salida: borrador o reflejo de entregas confirmadas."""

    __tablename__ = "warehouse_voucher"
    __table_args__ = (
        UniqueConstraint("document_registry_id", name="uq_warehouse_voucher_registry"),
        UniqueConstraint("idempotency_key", name="uq_warehouse_voucher_idem"),
        CheckConstraint("status IN ('DRAFT','ISSUED')", name="ck_voucher_status_valido"),
        {"schema": "doc"},
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
    source_requisition_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("req.requisition.id", ondelete="RESTRICT"), nullable=True
    )
    cost_center_code: Mapped[str | None] = mapped_column(String(60), nullable=True)
    area: Mapped[str | None] = mapped_column(String(120), nullable=True)
    usage_equipment: Mapped[str | None] = mapped_column(String(255), nullable=True)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    template_code: Mapped[str] = mapped_column(String(40), nullable=False)
    template_version: Mapped[int] = mapped_column(Integer, nullable=False)
    issued_at: Mapped[datetime | None] = mapped_column(nullable=True)
    issued_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("seg.app_user.id", ondelete="RESTRICT"), nullable=True
    )

    lines: Mapped[list["WarehouseVoucherLine"]] = relationship(
        back_populates="voucher", order_by="WarehouseVoucherLine.line_no"
    )


class WarehouseVoucherLine(AuditMixin, Base):
    __tablename__ = "warehouse_voucher_line"
    __table_args__ = (
        UniqueConstraint("voucher_id", "line_no", name="uq_voucher_line"),
        CheckConstraint("requested_qty >= 0", name="ck_voucher_line_requested_no_negativa"),
        CheckConstraint("dispatched_qty >= 0", name="ck_voucher_line_dispatched_no_negativa"),
        {"schema": "doc"},
    )

    voucher_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("doc.warehouse_voucher.id", ondelete="RESTRICT"), nullable=False
    )
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    requisition_line_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("req.requisition_line.id", ondelete="RESTRICT"), nullable=True
    )
    stock_movement_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("inv.stock_movement.id", ondelete="RESTRICT"), nullable=True
    )
    item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("mdm.item.id", ondelete="RESTRICT"), nullable=True
    )
    item_code: Mapped[str] = mapped_column(String(60), nullable=False)
    uom_code: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    requested_qty: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    dispatched_qty: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)

    voucher: Mapped["WarehouseVoucher"] = relationship(back_populates="lines")
