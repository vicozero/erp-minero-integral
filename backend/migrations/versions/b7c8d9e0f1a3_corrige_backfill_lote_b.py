"""Corrige el backfill manual del Lote B.1 para PostgreSQL 17.

La revisión ``b7c8d9e0f1a2`` usó ``MIN(id)`` sobre una columna UUID; PostgreSQL
no define ``min(uuid)``. Esta migración reemplaza únicamente esa función por una
equivalente que agrega el UUID como texto. No modifica datos ni objetos
adicionales.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b7c8d9e0f1a3"
down_revision = "b7c8d9e0f1a2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION inv.backfill_lote_b_detail()
            RETURNS integer LANGUAGE plpgsql AS $fn$
            DECLARE
                row_scope record;
                inserted_rows integer := 0;
            BEGIN
                FOR row_scope IN
                    SELECT warehouse_id, item_id,
                           SUM(on_hand_qty) AS on_hand_qty,
                           SUM(reserved_qty) AS reserved_qty,
                           MIN(id::text)::uuid AS balance_id
                    FROM inv.stock_balance
                    GROUP BY warehouse_id, item_id
                    HAVING SUM(on_hand_qty) <> 0 OR SUM(reserved_qty) <> 0
                LOOP
                    IF EXISTS (
                        SELECT 1 FROM inv.stock_balance_detail d
                        WHERE d.warehouse_id = row_scope.warehouse_id
                          AND d.item_id = row_scope.item_id
                    ) THEN
                        CONTINUE;
                    END IF;

                    INSERT INTO inv.stock_balance_detail (
                        id, stock_balance_id, warehouse_id, item_id,
                        lot_ref_id, serial_id, stock_state, location_ref_id,
                        on_hand_qty, reserved_qty, created_at, version
                    ) VALUES (
                        gen_random_uuid(), row_scope.balance_id,
                        row_scope.warehouse_id, row_scope.item_id,
                        NULL, NULL, 'AVAILABLE', NULL,
                        row_scope.on_hand_qty, row_scope.reserved_qty, now(), 1
                    )
                    ON CONFLICT (
                        warehouse_id, item_id,
                        (COALESCE(lot_ref_id, '00000000-0000-0000-0000-000000000000'::uuid)),
                        (COALESCE(serial_id, '00000000-0000-0000-0000-000000000000'::uuid)),
                        stock_state,
                        (COALESCE(location_ref_id, '00000000-0000-0000-0000-000000000000'::uuid))
                    ) DO NOTHING;

                    IF FOUND THEN
                        inserted_rows := inserted_rows + 1;
                    END IF;
                END LOOP;

                INSERT INTO aud.audit_log (
                    id, occurred_at, actor_id, actor_username, action,
                    entity_type, entity_id, before_json, after_json,
                    request_id, correlation_id, ip_hash, detail
                ) VALUES (
                    gen_random_uuid(), now(), NULL, 'system',
                    'BACKFILL_LOTE_B_DETAIL', 'inv.stock_balance_detail', NULL,
                    NULL, jsonb_build_object('inserted_rows', inserted_rows),
                    'system', NULL, NULL,
                    'Backfill manual de detalle Lote B; ejecutar solo con ticket autorizado.'
                );

                RETURN inserted_rows;
            END;
            $fn$;
            """
        )
    )


def downgrade() -> None:
    raise RuntimeError(
        "La corrección del backfill Lote B.1 no admite downgrade automático."
    )
