"""Agrega captura nominal de firmas de vales para el Lote 5.

Migración aditiva: solo agrega columnas nullable a ``doc.warehouse_voucher``.
No elimina ni reescribe documentos, movimientos ni saldos. Las firmas se
registran como nombres declarados por el usuario (constancia nominal); el ERP
no genera grafías ni imágenes de firmas.

La reimpresión sigue devolviendo el archivo original; para incluir nombres
capturados se genera una versión nueva sin ``reprint``.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f7a8b9c0d1e2"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "warehouse_voucher",
        sa.Column("received_by_name", sa.String(length=120), nullable=True),
        schema="doc",
    )
    op.add_column(
        "warehouse_voucher",
        sa.Column("authorized_by_name", sa.String(length=120), nullable=True),
        schema="doc",
    )
    op.add_column(
        "warehouse_voucher",
        sa.Column("dispatched_by_name", sa.String(length=120), nullable=True),
        schema="doc",
    )
    op.add_column(
        "warehouse_voucher",
        sa.Column("signatures_recorded_at", sa.DateTime(timezone=True), nullable=True),
        schema="doc",
    )
    op.add_column(
        "warehouse_voucher",
        sa.Column("signatures_recorded_by", sa.Uuid(), nullable=True),
        schema="doc",
    )
    op.create_foreign_key(
        op.f("fk_warehouse_voucher_signatures_recorded_by"),
        "warehouse_voucher",
        "app_user",
        ["signatures_recorded_by"],
        ["id"],
        source_schema="doc",
        referent_schema="seg",
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    """No se ejecuta sobre datos reales: requiere ticket y aprobación explícita."""
    raise RuntimeError(
        "La reversión de firmas de vales está prohibida por la política de "
        "migraciones aditivas de AGENTS.md."
    )
