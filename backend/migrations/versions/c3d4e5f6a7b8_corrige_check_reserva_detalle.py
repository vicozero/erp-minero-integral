"""Corrige la restricción de reservas en ``inv.stock_balance_detail``.

El diseño ``docs/WMS_LOTE_B_DISENO.md`` establece que ``reserved_qty`` sólo
puede ser distinto de cero en el estado ``AVAILABLE``. La revisión
``b7c8d9e0f1a2`` implementó la implicación invertida, por lo que la proyección
detallada no podía reflejar las reservas reales del saldo agregado.

Esta migración sustituye únicamente esa restricción CHECK. No modifica datos,
no ejecuta el backfill manual y no altera ninguna otra tabla.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c3d4e5f6a7b8"
down_revision = "a2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            ALTER TABLE inv.stock_balance_detail
            DROP CONSTRAINT IF EXISTS ck_sbd_reserved_solo_disponible
            """
        )
    )
    op.execute(
        sa.text(
            """
            ALTER TABLE inv.stock_balance_detail
            ADD CONSTRAINT ck_sbd_reserved_solo_disponible
            CHECK (stock_state = 'AVAILABLE' OR reserved_qty = 0)
            """
        )
    )


def downgrade() -> None:
    raise RuntimeError(
        "La corrección de la restricción de reservas no admite downgrade automático."
    )
