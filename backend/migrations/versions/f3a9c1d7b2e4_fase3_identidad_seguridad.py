"""Fase 3 — identidad, sesiones y alcance RBAC

Revision ID: f3a9c1d7b2e4
Revises: d147e7ec92fb
Create Date: 2026-11-18

Migración aditiva: no elimina columnas, tablas ni datos. El downgrade está
bloqueado por política del repositorio (AGENTS.md, principio 6).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f3a9c1d7b2e4"
down_revision = "d147e7ec92fb"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Campos de_control de cuenta. Todos con valores por defecto para no
    # requerir reescritura de las filas existentes.
    op.add_column(
        "app_user",
        sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default="0"),
        schema="seg",
    )
    op.add_column("app_user", sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True), schema="seg")
    op.add_column(
        "app_user",
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()),
        schema="seg",
    )
    op.add_column("app_user", sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True), schema="seg")
    op.add_column("app_user", sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True), schema="seg")
    op.add_column(
        "app_user",
        sa.Column(
            "password_changed_by",
            sa.Uuid(),
            nullable=True,
        ),
        schema="seg",
    )
    op.add_column(
        "app_user",
        sa.Column(
            "deactivated_by",
            sa.Uuid(),
            nullable=True,
        ),
        schema="seg",
    )
    op.create_foreign_key(
        "fk_app_user_password_changed_by",
        "app_user",
        "app_user",
        ["password_changed_by"],
        ["id"],
        source_schema="seg",
        referent_schema="seg",
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_app_user_deactivated_by",
        "app_user",
        "app_user",
        ["deactivated_by"],
        ["id"],
        source_schema="seg",
        referent_schema="seg",
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_app_user_failed_login_attempts",
        "app_user",
        "failed_login_attempts >= 0",
        schema="seg",
    )

    # Sesiones opacas: el token viaja solo en cookie HttpOnly; en la base se
    # guarda únicamente su hash SHA-256. Nunca se persiste el token en claro.
    op.create_table(
        "user_session",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("csrf_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=func_now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", sa.Uuid(), nullable=True),
        sa.Column("ip_hash", sa.String(length=64), nullable=True),
        sa.Column("user_agent_hash", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["seg.app_user.id"], name="fk_user_session_user_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["revoked_by"], ["seg.app_user.id"], name="fk_user_session_revoked_by", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_user_session"),
        sa.UniqueConstraint("token_hash", name="uq_user_session_token_hash"),
        schema="seg",
    )
    op.create_index("ix_user_session_user_id", "user_session", ["user_id"], unique=False, schema="seg")
    op.create_index("ix_user_session_expires_at", "user_session", ["expires_at"], unique=False, schema="seg")

    # Pertenencia a departamentos para alcance RBAC. La unidad minera se
    # deriva del departamento, evitando un segundo inventario de organizational scope.
    op.create_table(
        "user_department",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("department_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=func_now()),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["seg.app_user.id"], name="fk_user_department_user_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["department_id"],
            ["org.department.id"],
            name="fk_user_department_department_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["seg.app_user.id"], name="fk_user_department_created_by", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["revoked_by"], ["seg.app_user.id"], name="fk_user_department_revoked_by", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_user_department"),
        sa.UniqueConstraint("user_id", "department_id", name="uq_user_department_user_department"),
        schema="seg",
    )
    op.create_index("ix_user_department_department_id", "user_department", ["department_id"], unique=False, schema="seg")

    # LoginAudit solo registro: sin passwords, sin tokens.
    op.add_column(
        "login_audit",
        sa.Column("user_agent_hash", sa.String(length=64), nullable=True),
        schema="seg",
    )

    # La bitácora aud.audit_log es inmutable también para ADMIN desde la BD.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION aud.prevent_audit_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'La bitácora de auditoría es inmutable';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_audit_log_immutable
        BEFORE UPDATE OR DELETE ON aud.audit_log
        FOR EACH ROW EXECUTE FUNCTION aud.prevent_audit_mutation()
        """
    )


def func_now():
    """Expresión SQL para defaults sin depender de la sesión de Python."""
    return sa.text("now()")


def downgrade() -> None:
    raise RuntimeError(
        "El downgrade de Fase 3 está bloqueado por política: no se eliminan datos ni auditoría."
    )
