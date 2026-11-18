from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base


class ApprovalRequest(AuditMixin, Base):
    __tablename__ = "approval_request"
    __table_args__ = (
        UniqueConstraint("document_type", "document_id", name="uq_approval_document"),
        CheckConstraint("status IN ('PENDING','APPROVED','PARTIAL','REJECTED','CANCELLED')", name="status_valido"),
        {"schema": "wfl"},
    )

    document_type: Mapped[str] = mapped_column(String(40), nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    requisition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("req.requisition.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False)
    current_step_no: Mapped[int] = mapped_column(default=1, nullable=False)
    requested_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)


class ApprovalStep(AuditMixin, Base):
    __tablename__ = "approval_step"
    __table_args__ = (
        UniqueConstraint("approval_request_id", "step_no", name="uq_request_step"),
        CheckConstraint("status IN ('PENDING','APPROVED','REJECTED','SKIPPED')", name="status_valido"),
        {"schema": "wfl"},
    )

    approval_request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("wfl.approval_request.id", ondelete="RESTRICT"), nullable=False
    )
    step_no: Mapped[int] = mapped_column(nullable=False)
    role_code: Mapped[str] = mapped_column(String(40), default="APROBADOR", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(nullable=True)
    acted_at: Mapped[datetime | None] = mapped_column(nullable=True)


class ApprovalDecision(AuditMixin, Base):
    __tablename__ = "approval_decision"
    __table_args__ = (
        UniqueConstraint("approval_step_id", "requisition_line_id", name="uq_step_line"),
        CheckConstraint("decision IN ('APPROVE','REJECT')", name="decision_valida"),
        CheckConstraint("approved_qty >= 0", name="approved_no_negativa"),
        {"schema": "wfl"},
    )

    approval_step_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("wfl.approval_step.id", ondelete="RESTRICT"), nullable=False
    )
    requisition_line_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("req.requisition_line.id", ondelete="RESTRICT"), nullable=False
    )
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    approved_qty: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("seg.app_user.id", ondelete="RESTRICT"), nullable=False
    )
    decided_at: Mapped[datetime | None] = mapped_column(nullable=True)
