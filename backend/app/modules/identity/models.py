from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base


class AppUser(AuditMixin, Base):
    __tablename__ = "app_user"
    __table_args__ = (
        UniqueConstraint("username", name="uq_username"),
        UniqueConstraint("email", name="uq_email"),
        CheckConstraint("status IN ('ACTIVE','INACTIVE','LOCKED')", name="status_valido"),
        {"schema": "seg"},
    )

    username: Mapped[str] = mapped_column(String(80), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)
    timezone: Mapped[str] = mapped_column(String(80), default="America/Mexico_City", nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(nullable=True)


class Role(AuditMixin, Base):
    __tablename__ = "role"
    __table_args__ = (
        UniqueConstraint("code", name="uq_code"),
        {"schema": "seg"},
    )

    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class Permission(AuditMixin, Base):
    __tablename__ = "permission"
    __table_args__ = (
        UniqueConstraint("code", name="uq_code"),
        {"schema": "seg"},
    )

    code: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class UserRole(AuditMixin, Base):
    __tablename__ = "user_role"
    __table_args__ = (
        UniqueConstraint("user_id", "role_id", "scope_type", "scope_id", name="uq_user_role_scope"),
        {"schema": "seg"},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("seg.app_user.id", ondelete="RESTRICT"), nullable=False)
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("seg.role.id", ondelete="RESTRICT"), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(30), default="GLOBAL", nullable=False)
    scope_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    valid_from: Mapped[datetime] = mapped_column(default=func.now(), nullable=False)
    valid_to: Mapped[datetime | None] = mapped_column(nullable=True)


class RolePermission(Base):
    __tablename__ = "role_permission"
    __table_args__ = {"schema": "seg"}

    role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("seg.role.id", ondelete="RESTRICT"), primary_key=True
    )
    permission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("seg.permission.id", ondelete="RESTRICT"), primary_key=True
    )


class LoginAudit(Base):
    __tablename__ = "login_audit"
    __table_args__ = {"schema": "seg"}

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("seg.app_user.id", ondelete="RESTRICT"), nullable=True
    )
    occurred_at: Mapped[datetime] = mapped_column(default=func.now(), nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request_id: Mapped[str] = mapped_column(String(64), default="system", nullable=False)
