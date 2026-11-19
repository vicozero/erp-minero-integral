from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base


class AppUser(AuditMixin, Base):
    __tablename__ = "app_user"
    __table_args__ = (
        UniqueConstraint("username", name="uq_username"),
        UniqueConstraint("email", name="uq_email"),
        CheckConstraint("status IN ('ACTIVE','INACTIVE','LOCKED')", name="status_valido"),
        CheckConstraint("failed_login_attempts >= 0", name="ck_app_user_failed_login_attempts"),
        {"schema": "seg"},
    )

    username: Mapped[str] = mapped_column(String(80), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)
    timezone: Mapped[str] = mapped_column(String(80), default="America/Mexico_City", nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Seguridad de cuenta (Fase 3)
    failed_login_attempts: Mapped[int] = mapped_column(default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(nullable=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    password_changed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    password_changed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("seg.app_user.id", ondelete="RESTRICT"), nullable=True
    )
    deactivated_at: Mapped[datetime | None] = mapped_column(nullable=True)
    deactivated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("seg.app_user.id", ondelete="RESTRICT"), nullable=True
    )


class Role(AuditMixin, Base):
    __tablename__ = "role"
    __table_args__ = (
        UniqueConstraint("code", name="uq_role_code"),
        {"schema": "seg"},
    )

    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class Permission(AuditMixin, Base):
    __tablename__ = "permission"
    __table_args__ = (
        UniqueConstraint("code", name="uq_permission_code"),
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


class UserSession(Base):
    __tablename__ = "user_session"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_user_session_token_hash"),
        Index("ix_user_session_user_id", "user_id"),
        Index("ix_user_session_expires_at", "expires_at"),
        {"schema": "seg"},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("seg.app_user.id", ondelete="RESTRICT"), nullable=False)
    token_hash: Mapped[str] = mapped_column(Text, nullable=False)
    csrf_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=func.now(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(nullable=True)
    revoked_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("seg.app_user.id", ondelete="RESTRICT"), nullable=True
    )
    ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)


class UserDepartment(Base):
    __tablename__ = "user_department"
    __table_args__ = (
        UniqueConstraint("user_id", "department_id", name="uq_user_department_user_department"),
        Index("ix_user_department_department_id", "department_id"),
        {"schema": "seg"},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("seg.app_user.id", ondelete="RESTRICT"), nullable=False)
    department_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("org.department.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(default=func.now(), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("seg.app_user.id", ondelete="RESTRICT"), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(nullable=True)
    revoked_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("seg.app_user.id", ondelete="RESTRICT"), nullable=True
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
    user_agent_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
