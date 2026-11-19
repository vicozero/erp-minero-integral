"""Fase 4 — requisiciones, adjuntos e idempotencia atómica

Revision ID: f4a7c1e2b3d6
Revises: f3a9c1d7b2e4
Create Date: 2026-11-18

Migración estrictamente aditiva: crea tablas nuevas, agrega una columna
opcional y refuerza invariantes de cantidades. No elimina tablas, columnas
ni datos. El downgrade está bloqueado por política del repositorio.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f4a7c1e2b3d6"
down_revision = "f3a9c1d7b2e4"
branch_labels = None
depends_on = None


def _now() -> sa.text:
    return sa.text("now()")


def upgrade() -> None:
    # Registro de idempotencia: la restricción única permite INSERT ... ON
    # CONFLICT DO NOTHING RETURNING, que es atómico incluso bajo concurrencia.
    op.create_table(
        "idempotency_record",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("operation", sa.String(length=60), nullable=False),
        sa.Column("entity_type", sa.String(length=60), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column("request_id", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="IN_PROGRESS"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=_now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('IN_PROGRESS','COMPLETED')", name="ck_idempotency_record_status"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_idempotency_record"),
        sa.UniqueConstraint("idempotency_key", name="uq_idempotency_record_key"),
        schema="doc",
    )

    # Referencia a orden de trabajo externa (GMAO). No se crea una entidad OT
    # local para no duplicar el sistema externo; solo se guarda la referencia.
    op.add_column("requisition", sa.Column("work_order_no", sa.String(length=80), nullable=True), schema="req")

    # Adjuntos controlados: el archivo vive fuera de la base; aquí se guarda
    # únicamente metadatos verificables (hash, tamaño, tipo y responsable).
    op.create_table(
        "requisition_attachment",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("requisition_id", sa.Uuid(), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("stored_name", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("uploaded_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=_now()),
        sa.CheckConstraint("size_bytes > 0", name="ck_requisition_attachment_size"),
        sa.ForeignKeyConstraint(
            ["requisition_id"],
            ["req.requisition.id"],
            name="fk_requisition_attachment_requisition_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by"],
            ["seg.app_user.id"],
            name="fk_requisition_attachment_uploaded_by",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_requisition_attachment"),
        sa.UniqueConstraint("stored_name", name="uq_requisition_attachment_stored_name"),
        schema="req",
    )
    op.create_index(
        "ix_requisition_attachment_requisition_id",
        "requisition_attachment",
        ["requisition_id"],
        unique=False,
        schema="req",
    )

    # Invariantes de cantidades en base de datos, además de la validación del
    # servicio. Los datos sintéticos actuales cumplen estas reglas.
    op.create_check_constraint(
        "ck_requisition_line_cancelled_within_requested",
        "requisition_line",
        "cancelled_qty <= requested_qty",
        schema="req",
    )
    op.create_check_constraint(
        "ck_requisition_line_authorised_within_remaining",
        "requisition_line",
        "authorised_qty <= requested_qty - cancelled_qty",
        schema="req",
    )

    # El barrido de reservas vencidas debe ser una consulta indexada.
    op.create_index(
        "ix_stock_reservation_expiry",
        "stock_reservation",
        ["expires_at", "status"],
        unique=False,
        schema="inv",
    )


def downgrade() -> None:
    raise RuntimeError(
        "El downgrade de Fase 4 está bloqueado por política: no se eliminan datos ni auditoría."
    )
