from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base


class Equipment(AuditMixin, Base):
    __tablename__ = "equipment"
    __table_args__ = (
        UniqueConstraint("company_id", "asset_tag", name="uq_company_asset"),
        CheckConstraint("status IN ('ACTIVE','INACTIVE','MAINTENANCE','RETIRED')", name="status_valido"),
        {"schema": "mnt"},
    )

    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("org.company.id", ondelete="RESTRICT"), nullable=False)
    mining_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("org.mining_unit.id", ondelete="RESTRICT"), nullable=True
    )
    cost_center_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cost.cost_center.id", ondelete="RESTRICT"), nullable=True
    )
    asset_tag: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(String(200), nullable=False)
    equipment_type: Mapped[str] = mapped_column(String(50), default="OTHER", nullable=False)
    criticality: Mapped[str] = mapped_column(String(20), default="MEDIUM", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)
    external_gmao_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
