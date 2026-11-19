"""Agrega la estructura transaccional del Lote B WMS en el esquema ``inv``.

La puerta D-06 (esquema físico ``wms``) no está aprobada en el repositorio.
Por ello esta migración aplica el alcance reducido definido en
``docs/ERP_MRO_WMS_DEPENDENCIAS.md`` sección 4.1:

* crea ``inv.stock_balance_detail`` y columnas nuevas en ``inv.stock_movement``;
* crea índices, restricciones, triggers, vistas y la función de backfill manual;
* **no** crea el esquema ``wms`` ni las tablas ``wms.movement_order*``;
* **no** ejecuta el backfill ni modifica datos de inventario.

Toda la DDL es aditiva. ``downgrade()`` falla deliberadamente.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b7c8d9e0f1a2"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None

_NULL_UUID = "00000000-0000-0000-0000-000000000000"
_STOCK_STATES = (
    "AVAILABLE",
    "QUARANTINE",
    "INSPECTION",
    "BLOCKED",
    "DAMAGED",
    "IN_TRANSIT",
    "SCRAP",
)


def _scope_sql(prefix: str = "") -> str:
    """Expresión canónica del ámbito detallado, reutilizable en índices y vistas."""
    p = f"{prefix}." if prefix else ""
    return (
        f"(COALESCE({p}lot_ref_id, '{_NULL_UUID}'::uuid)), "
        f"(COALESCE({p}serial_id, '{_NULL_UUID}'::uuid)), "
        f"{p}stock_state, "
        f"(COALESCE({p}location_ref_id, '{_NULL_UUID}'::uuid))"
    )


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Proyección detallada de existencias.
    # ------------------------------------------------------------------
    op.create_table(
        "stock_balance_detail",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("stock_balance_id", sa.Uuid(), nullable=False),
        sa.Column("warehouse_id", sa.Uuid(), nullable=False),
        sa.Column("item_id", sa.Uuid(), nullable=False),
        sa.Column("lot_ref_id", sa.Uuid(), nullable=True),
        sa.Column("serial_id", sa.Uuid(), nullable=True),
        sa.Column("stock_state", sa.String(length=30), nullable=False),
        sa.Column("location_ref_id", sa.Uuid(), nullable=True),
        sa.Column("on_hand_qty", sa.Numeric(18, 6), nullable=False, server_default=sa.text("0")),
        sa.Column("reserved_qty", sa.Numeric(18, 6), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.CheckConstraint("on_hand_qty >= 0", name=op.f("ck_sbd_on_hand_no_negativo")),
        sa.CheckConstraint("reserved_qty >= 0", name=op.f("ck_sbd_reserved_no_negativo")),
        sa.CheckConstraint("on_hand_qty >= reserved_qty", name=op.f("ck_sbd_reserved_dentro_de_existencia")),
        sa.CheckConstraint(
            "stock_state IN (" + ", ".join(f"'{state}'" for state in _STOCK_STATES) + ")",
            name=op.f("ck_sbd_stock_state_valido"),
        ),
        sa.CheckConstraint(
            "stock_state <> 'AVAILABLE' OR reserved_qty = 0",
            name=op.f("ck_sbd_reserved_solo_disponible"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stock_balance_detail")),
        schema="inv",
    )

    op.execute(
        sa.text(
            """
            ALTER TABLE inv.stock_balance_detail
            ADD CONSTRAINT fk_sbd_stock_balance_id
            FOREIGN KEY (stock_balance_id) REFERENCES inv.stock_balance(id) ON DELETE RESTRICT;
            """
        )
    )
    for column, schema, table in (
        ("warehouse_id", "org", "warehouse"),
        ("item_id", "mdm", "item"),
        ("lot_ref_id", "mdm", "lot"),
        ("serial_id", "mdm", "serial"),
        ("location_ref_id", "mdm", "storage_location"),
        ("created_by", "seg", "app_user"),
        ("updated_by", "seg", "app_user"),
    ):
        op.execute(
            sa.text(
                f"""
                ALTER TABLE inv.stock_balance_detail
                ADD CONSTRAINT fk_sbd_{column}
                FOREIGN KEY ({column}) REFERENCES {schema}.{table}(id) ON DELETE RESTRICT;
                """
            )
        )

    op.execute(
        sa.text(
            f"""
            CREATE UNIQUE INDEX uq_stock_balance_detail_scope
            ON inv.stock_balance_detail (
                warehouse_id,
                item_id,
                {_scope_sql()}
            );
            """
        )
    )
    for name, columns in (
        ("ix_sbd_warehouse_item_state", ("warehouse_id", "item_id", "stock_state")),
        ("ix_sbd_lot_ref", ("lot_ref_id",)),
        ("ix_sbd_serial_id", ("serial_id",)),
        ("ix_sbd_location_ref", ("location_ref_id",)),
    ):
        op.create_index(name, "stock_balance_detail", list(columns), schema="inv")

    # ------------------------------------------------------------------
    # 2. Columnas aditivas en el hecho canónico (append-only).
    # ------------------------------------------------------------------
    new_columns = (
        ("stock_state", sa.String(length=30)),
        ("serial_id", sa.Uuid()),
        ("occurred_at", sa.DateTime(timezone=True)),
        ("scope_balance_after_qty", sa.Numeric(18, 6)),
        ("delivery_seq", sa.Integer()),
        ("return_seq", sa.Integer()),
        ("movement_group_id", sa.Uuid()),
        ("return_of_movement_id", sa.Uuid()),
        ("reversal_reason", sa.Text()),
        ("reversal_requested_by", sa.Uuid()),
        ("reversal_approved_by", sa.Uuid()),
        ("approved_by", sa.Uuid()),
        ("department_id", sa.Uuid()),
        ("requester_id", sa.Uuid()),
        ("equipment_id", sa.Uuid()),
        ("cost_center_id", sa.Uuid()),
        ("work_order_no", sa.String(length=80)),
        ("movement_order_line_id", sa.Uuid()),
    )
    for name, column_type in new_columns:
        op.add_column("stock_movement", sa.Column(name, column_type, nullable=True), schema="inv")

    for column, schema, table in (
        ("serial_id", "mdm", "serial"),
        ("return_of_movement_id", "inv", "stock_movement"),
        ("reversal_requested_by", "seg", "app_user"),
        ("reversal_approved_by", "seg", "app_user"),
        ("approved_by", "seg", "app_user"),
        ("department_id", "org", "department"),
        ("requester_id", "seg", "app_user"),
        ("equipment_id", "mnt", "equipment"),
        ("cost_center_id", "cost", "cost_center"),
    ):
        op.execute(
            sa.text(
                f"""
                ALTER TABLE inv.stock_movement
                ADD CONSTRAINT fk_stock_movement_{column}
                FOREIGN KEY ({column}) REFERENCES {schema}.{table}(id) ON DELETE RESTRICT;
                """
            )
        )

    op.execute(
        sa.text(
            f"""
            ALTER TABLE inv.stock_movement
            ADD CONSTRAINT ck_stock_movement_stock_state
            CHECK (stock_state IS NULL OR stock_state IN ({', '.join(repr(s) for s in _STOCK_STATES)}));

            ALTER TABLE inv.stock_movement
            ADD CONSTRAINT ck_stock_movement_delivery_seq
            CHECK (delivery_seq IS NULL OR delivery_seq > 0);

            ALTER TABLE inv.stock_movement
            ADD CONSTRAINT ck_stock_movement_return_seq
            CHECK (return_seq IS NULL OR return_seq > 0);

            COMMENT ON COLUMN inv.stock_movement.movement_order_line_id IS
            'Referencia futura a wms.movement_order_line.id. Sin FK mientras D-06 no esté aprobada.';
            """
        )
    )

    op.execute(
        sa.text(
            """
            CREATE UNIQUE INDEX uq_stock_movement_reversal_once
            ON inv.stock_movement (reversal_of_id) WHERE reversal_of_id IS NOT NULL;

            CREATE UNIQUE INDEX uq_movement_issue_seq
            ON inv.stock_movement (requisition_line_id, delivery_seq)
            WHERE movement_type = 'ISSUE' AND delivery_seq IS NOT NULL;

            CREATE UNIQUE INDEX uq_movement_return_seq
            ON inv.stock_movement (return_of_movement_id, return_seq)
            WHERE movement_type = 'RETURN' AND return_seq IS NOT NULL;
            """
        )
    )
    for name, columns in (
        ("ix_stock_movement_serial_id", ("serial_id",)),
        ("ix_stock_movement_equipment_id", ("equipment_id",)),
        ("ix_stock_movement_cost_center_id", ("cost_center_id",)),
        ("ix_stock_movement_work_order_no", ("work_order_no",)),
        ("ix_stock_movement_occurred_at", ("occurred_at",)),
        ("ix_stock_movement_movement_order_line_id", ("movement_order_line_id",)),
        ("ix_stock_movement_return_of_id", ("return_of_movement_id",)),
    ):
        op.create_index(name, "stock_movement", list(columns), schema="inv")

    # ------------------------------------------------------------------
    # 3. Inmutabilidad. El TRUNCATE del arnés de pruebas requiere una
    #    bandera explícita y solo se activa sobre erp_minero_test.
    # ------------------------------------------------------------------
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION inv.fn_block_movement_mutation()
            RETURNS trigger LANGUAGE plpgsql AS $fn$
            BEGIN
                IF TG_OP = 'TRUNCATE' THEN
                    IF COALESCE(current_setting('inv.allow_maintenance_truncate', true), 'off') <> 'on' THEN
                        RAISE EXCEPTION 'TRUNCATE de inv.stock_movement no permitido; use REVERSAL'
                            USING ERRCODE = 'check_violation';
                    END IF;
                    RETURN NULL;
                END IF;
                RAISE EXCEPTION 'UPDATE/DELETE de inv.stock_movement no permitido; use REVERSAL'
                    USING ERRCODE = 'check_violation';
            END;
            $fn$;

            CREATE TRIGGER trg_stock_movement_no_update
            BEFORE UPDATE ON inv.stock_movement
            FOR EACH ROW EXECUTE FUNCTION inv.fn_block_movement_mutation();

            CREATE TRIGGER trg_stock_movement_no_delete
            BEFORE DELETE ON inv.stock_movement
            FOR EACH ROW EXECUTE FUNCTION inv.fn_block_movement_mutation();

            CREATE TRIGGER trg_stock_movement_no_truncate
            BEFORE TRUNCATE ON inv.stock_movement
            FOR EACH STATEMENT EXECUTE FUNCTION inv.fn_block_movement_mutation();
            """
        )
    )

    # ------------------------------------------------------------------
    # 4. Reversos controlados.
    # ------------------------------------------------------------------
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION inv.fn_check_reversal()
            RETURNS trigger LANGUAGE plpgsql AS $fn$
            DECLARE
                original inv.stock_movement%ROWTYPE;
            BEGIN
                IF NEW.movement_type IS DISTINCT FROM 'REVERSAL' THEN
                    RETURN NEW;
                END IF;

                IF NEW.reversal_of_id IS NULL THEN
                    RAISE EXCEPTION 'REVERSAL requiere reversal_of_id'
                        USING ERRCODE = 'check_violation';
                END IF;

                SELECT * INTO original
                FROM inv.stock_movement
                WHERE id = NEW.reversal_of_id
                FOR UPDATE;

                IF NOT FOUND THEN
                    RAISE EXCEPTION 'El movimiento original no existe'
                        USING ERRCODE = 'foreign_key_violation';
                END IF;
                IF original.status <> 'POSTED' THEN
                    RAISE EXCEPTION 'Solo se puede reversar un movimiento POSTED'
                        USING ERRCODE = 'check_violation';
                END IF;
                IF original.movement_type = 'REVERSAL' THEN
                    RAISE EXCEPTION 'No se admiten reversos encadenados'
                        USING ERRCODE = 'check_violation';
                END IF;
                IF NEW.direction = original.direction THEN
                    RAISE EXCEPTION 'El reverso debe tener dirección opuesta'
                        USING ERRCODE = 'check_violation';
                END IF;
                IF NEW.quantity IS DISTINCT FROM original.quantity THEN
                    RAISE EXCEPTION 'El reverso debe ser por la cantidad total del original'
                        USING ERRCODE = 'check_violation';
                END IF;
                IF NEW.item_id IS DISTINCT FROM original.item_id
                   OR NEW.warehouse_id IS DISTINCT FROM original.warehouse_id
                   OR NEW.lot_id IS DISTINCT FROM original.lot_id
                   OR NEW.location_id IS DISTINCT FROM original.location_id
                   OR NEW.lot_ref_id IS DISTINCT FROM original.lot_ref_id
                   OR NEW.location_ref_id IS DISTINCT FROM original.location_ref_id
                   OR NEW.serial_id IS DISTINCT FROM original.serial_id
                   OR NEW.stock_state IS DISTINCT FROM original.stock_state THEN
                    RAISE EXCEPTION 'El reverso debe conservar item, almacén, lote, serie, estado y ubicación'
                        USING ERRCODE = 'check_violation';
                END IF;
                RETURN NEW;
            END;
            $fn$;

            CREATE TRIGGER trg_stock_movement_reversal_guard
            BEFORE INSERT ON inv.stock_movement
            FOR EACH ROW EXECUTE FUNCTION inv.fn_check_reversal();
            """
        )
    )

    # ------------------------------------------------------------------
    # 5. Límite de devoluciones sobre la entrega original.
    # ------------------------------------------------------------------
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION inv.fn_check_return_limit()
            RETURNS trigger LANGUAGE plpgsql AS $fn$
            DECLARE
                original inv.stock_movement%ROWTYPE;
                total_devuelto numeric(18, 6);
            BEGIN
                IF NEW.movement_type IS DISTINCT FROM 'RETURN'
                   OR NEW.return_of_movement_id IS NULL THEN
                    RETURN NEW;
                END IF;

                SELECT * INTO original
                FROM inv.stock_movement
                WHERE id = NEW.return_of_movement_id
                FOR UPDATE;

                IF NOT FOUND THEN
                    RAISE EXCEPTION 'El movimiento de origen de la devolución no existe'
                        USING ERRCODE = 'foreign_key_violation';
                END IF;
                IF original.movement_type <> 'ISSUE' OR original.direction <> 'OUT' THEN
                    RAISE EXCEPTION 'Solo se puede devolver contra un ISSUE'
                        USING ERRCODE = 'check_violation';
                END IF;
                IF NEW.item_id IS DISTINCT FROM original.item_id
                   OR NEW.warehouse_id IS DISTINCT FROM original.warehouse_id THEN
                    RAISE EXCEPTION 'La devolución debe conservar item y almacén del origen'
                        USING ERRCODE = 'check_violation';
                END IF;
                IF NEW.direction <> 'IN' THEN
                    RAISE EXCEPTION 'La devolución debe ser IN'
                        USING ERRCODE = 'check_violation';
                END IF;
                IF NEW.return_seq IS NULL OR NEW.return_seq <= 0 THEN
                    RAISE EXCEPTION 'La devolución requiere return_seq positivo'
                        USING ERRCODE = 'check_violation';
                END IF;

                SELECT COALESCE(SUM(quantity), 0) INTO total_devuelto
                FROM inv.stock_movement
                WHERE return_of_movement_id = NEW.return_of_movement_id
                  AND movement_type = 'RETURN';

                IF total_devuelto + NEW.quantity > original.quantity THEN
                    RAISE EXCEPTION 'La devolución excede la cantidad entregada'
                        USING ERRCODE = 'check_violation';
                END IF;
                RETURN NEW;
            END;
            $fn$;

            CREATE TRIGGER trg_stock_movement_return_guard
            BEFORE INSERT ON inv.stock_movement
            FOR EACH ROW EXECUTE FUNCTION inv.fn_check_return_limit();
            """
        )
    )

    # ------------------------------------------------------------------
    # 6. Conciliación diferida, consciente de los registros heredados.
    #    Solo exige igualdad cuando el ámbito ya tiene filas de detalle.
    # ------------------------------------------------------------------
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION inv.fn_check_sbd_reconcile()
            RETURNS trigger LANGUAGE plpgsql AS $fn$
            DECLARE
                v_warehouse_id uuid;
                v_item_id uuid;
                v_legacy_on_hand numeric(18, 6);
                v_legacy_reserved numeric(18, 6);
                v_detail_on_hand numeric(18, 6);
                v_detail_reserved numeric(18, 6);
            BEGIN
                IF TG_OP = 'DELETE' THEN
                    v_warehouse_id := OLD.warehouse_id;
                    v_item_id := OLD.item_id;
                ELSE
                    v_warehouse_id := NEW.warehouse_id;
                    v_item_id := NEW.item_id;
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM inv.stock_balance_detail d
                    WHERE d.warehouse_id = v_warehouse_id AND d.item_id = v_item_id
                ) THEN
                    RETURN NULL;
                END IF;

                SELECT COALESCE(SUM(on_hand_qty), 0), COALESCE(SUM(reserved_qty), 0)
                INTO v_legacy_on_hand, v_legacy_reserved
                FROM inv.stock_balance
                WHERE warehouse_id = v_warehouse_id AND item_id = v_item_id;

                SELECT COALESCE(SUM(on_hand_qty), 0), COALESCE(SUM(reserved_qty), 0)
                INTO v_detail_on_hand, v_detail_reserved
                FROM inv.stock_balance_detail
                WHERE warehouse_id = v_warehouse_id AND item_id = v_item_id;

                IF v_legacy_on_hand IS DISTINCT FROM v_detail_on_hand
                   OR v_legacy_reserved IS DISTINCT FROM v_detail_reserved THEN
                    RAISE EXCEPTION
                        'Divergencia de saldos en almacén % / artículo %: agregado (%, %), detalle (%, %)',
                        v_warehouse_id, v_item_id,
                        v_legacy_on_hand, v_legacy_reserved,
                        v_detail_on_hand, v_detail_reserved
                        USING ERRCODE = 'check_violation';
                END IF;
                RETURN NULL;
            END;
            $fn$;

            CREATE CONSTRAINT TRIGGER trg_sbd_reconcile_balance
            AFTER INSERT OR UPDATE OR DELETE ON inv.stock_balance
            DEFERRABLE INITIALLY DEFERRED
            FOR EACH ROW EXECUTE FUNCTION inv.fn_check_sbd_reconcile();

            CREATE CONSTRAINT TRIGGER trg_sbd_reconcile_detail
            AFTER INSERT OR UPDATE OR DELETE ON inv.stock_balance_detail
            DEFERRABLE INITIALLY DEFERRED
            FOR EACH ROW EXECUTE FUNCTION inv.fn_check_sbd_reconcile();
            """
        )
    )

    # ------------------------------------------------------------------
    # 7. Vistas de lectura.
    # ------------------------------------------------------------------
    op.execute(
        sa.text(
            """
            CREATE VIEW inv.v_stock_balance_reconciliation AS
            WITH legacy AS (
                SELECT warehouse_id, item_id,
                       SUM(on_hand_qty) AS legacy_on_hand_qty,
                       SUM(reserved_qty) AS legacy_reserved_qty
                FROM inv.stock_balance
                GROUP BY warehouse_id, item_id
            ),
            detail AS (
                SELECT warehouse_id, item_id,
                       SUM(on_hand_qty) AS detail_on_hand_qty,
                       SUM(reserved_qty) AS detail_reserved_qty,
                       COUNT(*) AS detail_rows
                FROM inv.stock_balance_detail
                GROUP BY warehouse_id, item_id
            ),
            scopes AS (
                SELECT warehouse_id, item_id FROM legacy
                UNION
                SELECT warehouse_id, item_id FROM detail
            )
            SELECT s.warehouse_id,
                   s.item_id,
                   COALESCE(l.legacy_on_hand_qty, 0) AS legacy_on_hand_qty,
                   COALESCE(d.detail_on_hand_qty, 0) AS detail_on_hand_qty,
                   COALESCE(l.legacy_reserved_qty, 0) AS legacy_reserved_qty,
                   COALESCE(d.detail_reserved_qty, 0) AS detail_reserved_qty,
                   COALESCE(l.legacy_on_hand_qty, 0) - COALESCE(d.detail_on_hand_qty, 0)
                       AS diferencia_on_hand,
                   COALESCE(l.legacy_reserved_qty, 0) - COALESCE(d.detail_reserved_qty, 0)
                       AS diferencia_reserved,
                   CASE
                       WHEN COALESCE(d.detail_rows, 0) = 0 THEN 'SIN_DETALLE'
                       WHEN COALESCE(l.legacy_on_hand_qty, 0) <> COALESCE(d.detail_on_hand_qty, 0)
                         OR COALESCE(l.legacy_reserved_qty, 0) <> COALESCE(d.detail_reserved_qty, 0)
                         THEN 'DIVERGENTE'
                       ELSE 'OK'
                   END AS estado
            FROM scopes s
            LEFT JOIN legacy l USING (warehouse_id, item_id)
            LEFT JOIN detail d USING (warehouse_id, item_id);
            """
        )
    )

    op.execute(
        sa.text(
            f"""
            CREATE VIEW inv.v_kardex AS
            SELECT m.id AS movement_id,
                   m.movement_no,
                   m.posted_at,
                   COALESCE(m.occurred_at, m.posted_at) AS occurred_at,
                   m.movement_type,
                   m.direction,
                   m.quantity,
                   m.item_id,
                   i.code AS item_code,
                   m.warehouse_id,
                   w.code AS warehouse_code,
                   m.lot_ref_id,
                   l.lot_number,
                   m.serial_id,
                   s.serial_number,
                   m.location_ref_id,
                   sl.code AS location_code,
                   sl.zone,
                   m.stock_state,
                   m.balance_after_qty,
                   m.scope_balance_after_qty,
                   SUM(CASE WHEN m.direction = 'IN' THEN m.quantity ELSE -m.quantity END)
                       OVER (
                           PARTITION BY m.item_id, m.warehouse_id,
                                        {_scope_sql('m')}
                           ORDER BY COALESCE(m.occurred_at, m.posted_at), m.posted_at, m.id
                           ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                       ) AS signed_running_qty,
                   m.source_document_type,
                   m.source_document_id,
                   dr.full_number AS document_no,
                   m.requisition_line_id,
                   m.equipment_id,
                   m.cost_center_id,
                   m.work_order_no,
                   m.requester_id,
                   m.created_by,
                   m.reversal_of_id,
                   m.return_of_movement_id,
                   m.movement_group_id,
                   cl.unit_cost,
                   cl.unit_cost * m.quantity AS total_cost
            FROM inv.stock_movement m
            LEFT JOIN mdm.item i ON i.id = m.item_id
            LEFT JOIN org.warehouse w ON w.id = m.warehouse_id
            LEFT JOIN mdm.lot l ON l.id = m.lot_ref_id
            LEFT JOIN mdm.serial s ON s.id = m.serial_id
            LEFT JOIN mdm.storage_location sl ON sl.id = m.location_ref_id
            LEFT JOIN doc.document_registry dr ON dr.id = m.document_registry_id
            LEFT JOIN (
                SELECT source_document_type, source_document_id, item_id, MIN(unit_cost) AS unit_cost
                FROM cost.cost_layer
                GROUP BY source_document_type, source_document_id, item_id
            ) cl ON cl.source_document_type = m.source_document_type
                 AND cl.source_document_id = m.source_document_id
                 AND cl.item_id = m.item_id;
            """
        )
    )

    op.execute(
        sa.text(
            """
            CREATE VIEW req.v_requisition_line_net_quantities AS
            SELECT rl.id AS requisition_line_id,
                   rl.requisition_id,
                   rl.line_no,
                   rl.item_id,
                   rl.description,
                   rl.uom_id,
                   rl.requested_qty,
                   rl.authorised_qty,
                   rl.cancelled_qty,
                   COALESCE(res.reserved_qty, 0) AS reserved_qty,
                   COALESCE(pol.purchased_qty, 0) AS purchased_qty,
                   COALESCE(pol.received_qty, 0) AS received_qty,
                   COALESCE(mov.delivered_qty, 0) AS delivered_qty,
                   COALESCE(mov.net_issued_qty, 0) AS net_issued_qty
            FROM req.requisition_line rl
            LEFT JOIN (
                SELECT requisition_line_id, SUM(quantity - consumed_qty) AS reserved_qty
                FROM inv.stock_reservation
                WHERE status = 'ACTIVE'
                GROUP BY requisition_line_id
            ) res ON res.requisition_line_id = rl.id
            LEFT JOIN (
                SELECT requisition_line_id,
                       SUM(ordered_qty - cancelled_qty) AS purchased_qty,
                       SUM(received_qty) AS received_qty
                FROM pur.purchase_order_line
                GROUP BY requisition_line_id
            ) pol ON pol.requisition_line_id = rl.id
            LEFT JOIN (
                SELECT requisition_line_id,
                       SUM(quantity) FILTER (WHERE movement_type = 'ISSUE') AS delivered_qty,
                       SUM(CASE
                           WHEN movement_type = 'ISSUE' THEN quantity
                           WHEN movement_type = 'REVERSAL' AND reversal_of_id IN (
                               SELECT id FROM inv.stock_movement WHERE movement_type = 'ISSUE'
                           ) THEN -quantity
                           ELSE 0
                       END) AS net_issued_qty
                FROM inv.stock_movement
                GROUP BY requisition_line_id
            ) mov ON mov.requisition_line_id = rl.id;
            """
        )
    )

    # ------------------------------------------------------------------
    # 8. Backfill manual y explícito. No se invoca desde esta migración.
    # ------------------------------------------------------------------
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
                           MIN(id) AS balance_id
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
        "El Lote B.1 es aditivo y no admite downgrade automático. "
        "Conserve los objetos y desactive el código en su caso."
    )
