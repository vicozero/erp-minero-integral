from __future__ import annotations

import uuid

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base


class Company(AuditMixin, Base):
    __tablename__ = "company"
    __table_args__ = (
        UniqueConstraint("code", name="uq_code"),
        CheckConstraint("is_active IN (0,1)", name="is_active_valido"),
        {"schema": "org"},
    )

    code: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class MiningUnit(AuditMixin, Base):
    __tablename__ = "mining_unit"
    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_company_code"),
        CheckConstraint("status IN ('ACTIVE','INACTIVE')", name="status_valido"),
        {"schema": "org"},
    )

    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("org.company.id", ondelete="RESTRICT"), nullable=False)
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)


class Department(AuditMixin, Base):
    __tablename__ = "department"
    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_company_code"),
        {"schema": "org"},
    )

    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("org.company.id", ondelete="RESTRICT"), nullable=False)
    mining_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("org.mining_unit.id", ondelete="RESTRICT"), nullable=True
    )
    parent_department_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("org.department.id", ondelete="RESTRICT"), nullable=True
    )
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)


class Warehouse(AuditMixin, Base):
    __tablename__ = "warehouse"
    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_company_code"),
        CheckConstraint(
            "warehouse_type IN ('MAIN','SURFACE','UNDERGROUND','TRANSIT','SCRAP')",
            name="warehouse_type_valido",
        ),
        {"schema": "org"},
    )

    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("org.company.id", ondelete="RESTRICT"), nullable=False)
    mining_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("org.mining_unit.id", ondelete="RESTRICT"), nullable=True
    )
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    warehouse_type: Mapped[str] = mapped_column(String(30), default="MAIN", nullable=False)
    allows_negative: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Employee(AuditMixin, Base):
    __tablename__ = "employee"
    __table_args__ = (
        UniqueConstraint("company_id", "employee_code", name="uq_company_code"),
        {"schema": "org"},
    )

    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("org.company.id", ondelete="RESTRICT"), nullable=False)
    employee_code: Mapped[str] = mapped_column(String(40), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("seg.app_user.id", ondelete="RESTRICT"), nullable=True
    )
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("org.department.id", ondelete="RESTRICT"), nullable=True
    )
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)
