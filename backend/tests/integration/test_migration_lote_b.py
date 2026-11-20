"""Pruebas PostgreSQL reales para la migración aditiva del Lote B.1.

No usan SQLite. Todas las mutationes se ejecutan dentro de transacciones que
se revierten, salvo el caso de concurrencia, donde dos conexiones independientes
mantienen transacciones abiertas y se revierten al finalizar.
"""

from __future__ import annotations

import threading
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

NULL_UUID = "00000000-0000-0000-0000-000000000000"
REVISION_B1 = "b7c8d9e0f1a3"
# Revisiones posteriores legítimas: el módulo documental, el semáforo SLA, el
# almacén virtual y las firmas nominales del Lote 5 son aditivos y no invalidan
# las garantías del Lote B.1.
REVISIONES_POSTERIORES = {
    "c1d2e3f4a5b6",
    "d2e3f4a5b6c7",
    "e5f6a7b8c9d0",
    "f7a8b9c0d1e2",
    "a2b3c4d5e6f7",
    "c3d4e5f6a7b8",
    "e4f5a6b7c8d9",
}


def _fetch_original(conn: object) -> dict[str, object]:
    """Devuelve un movimiento semilla POSTED para usar como origen."""
    row = conn.execute(  # type: ignore[attr-defined]
        text(
            """
            SELECT id, movement_no, movement_type, direction, quantity,
                   item_id, warehouse_id, lot_id, location_id,
                   lot_ref_id, location_ref_id, serial_id, stock_state,
                   balance_after_qty, status, idempotency_key,
                   source_document_type, source_document_id, document_registry_id
            FROM inv.stock_movement
            WHERE movement_type = 'INITIAL' AND status = 'POSTED'
            ORDER BY movement_no
            LIMIT 1
            """
        )
    ).mappings().one()
    return dict(row)


def _fetch_admin_id(conn: object) -> uuid.UUID:
    return conn.execute(  # type: ignore[attr-defined]
        text("SELECT id FROM seg.app_user WHERE username = 'demo.admin'")
    ).scalar_one()


def _insert_movement(
    conn: object,
    *,
    item_id: uuid.UUID,
    warehouse_id: uuid.UUID,
    movement_type: str,
    direction: str,
    quantity: Decimal,
    movement_id: uuid.UUID | None = None,
    movement_no: str | None = None,
    idempotency_key: str | None = None,
    balance_after_qty: Decimal = Decimal("0"),
    source_document_type: str = "TEST",
    status: str = "POSTED",
    lot_id: str = NULL_UUID,
    location_id: str = NULL_UUID,
    **extra: object,
) -> uuid.UUID:
    """Inserta un movimiento con todas las columnas NOT NULL heredadas."""
    movement_id = movement_id or uuid.uuid4()
    params: dict[str, object] = {
        "id": movement_id,
        "movement_no": movement_no or f"TEST-{uuid.uuid4().hex[:12]}",
        "movement_type": movement_type,
        "direction": direction,
        "quantity": quantity,
        "item_id": item_id,
        "warehouse_id": warehouse_id,
        "lot_id": lot_id,
        "location_id": location_id,
        "balance_after_qty": balance_after_qty,
        "source_document_type": source_document_type,
        "idempotency_key": idempotency_key or f"test:{uuid.uuid4().hex}",
        "status": status,
        "posted_at": datetime.now(timezone.utc),
    }
    params.update(extra)
    columns = ", ".join(params)
    placeholders = ", ".join(f":{name}" for name in params)
    conn.execute(  # type: ignore[attr-defined]
        text(f"INSERT INTO inv.stock_movement ({columns}) VALUES ({placeholders})"),
        params,
    )
    return movement_id


def _insert_reversal(conn: object, original: dict[str, object], admin_id: uuid.UUID, tag: str) -> uuid.UUID:
    opposite = "OUT" if original["direction"] == "IN" else "IN"
    return _insert_movement(
        conn,
        item_id=original["item_id"],  # type: ignore[arg-type]
        warehouse_id=original["warehouse_id"],  # type: ignore[arg-type]
        movement_type="REVERSAL",
        direction=opposite,
        quantity=original["quantity"],  # type: ignore[arg-type]
        movement_no=f"TEST-REV-{tag}-{uuid.uuid4().hex[:8]}",
        idempotency_key=f"test:rev:{tag}:{uuid.uuid4().hex}",
        lot_id=original["lot_id"],  # type: ignore[arg-type]
        location_id=original["location_id"],  # type: ignore[arg-type]
        reversal_of_id=original["id"],
        reversal_reason=f"Prueba B.1 {tag}",
        reversal_requested_by=admin_id,
        reversal_approved_by=admin_id,
        approved_by=admin_id,
        lot_ref_id=original["lot_ref_id"],
        location_ref_id=original["location_ref_id"],
        serial_id=original["serial_id"],
        stock_state=original["stock_state"],
    )


def _fetch_balance(conn: object, item_id: uuid.UUID, warehouse_id: uuid.UUID) -> dict[str, object]:
    row = conn.execute(  # type: ignore[attr-defined]
        text(
            """
            SELECT id, on_hand_qty, reserved_qty
            FROM inv.stock_balance
            WHERE item_id = :item_id AND warehouse_id = :warehouse_id
            ORDER BY id
            LIMIT 1
            """
        ),
        {"item_id": item_id, "warehouse_id": warehouse_id},
    ).mappings().one()
    return dict(row)


def _insert_detail(
    conn: object,
    *,
    stock_balance_id: uuid.UUID,
    warehouse_id: uuid.UUID,
    item_id: uuid.UUID,
    on_hand_qty: Decimal,
    reserved_qty: Decimal = Decimal("0"),
    stock_state: str = "AVAILABLE",
    lot_ref_id: uuid.UUID | None = None,
    serial_id: uuid.UUID | None = None,
    location_ref_id: uuid.UUID | None = None,
) -> None:
    conn.execute(  # type: ignore[attr-defined]
        text(
            """
            INSERT INTO inv.stock_balance_detail (
                stock_balance_id, warehouse_id, item_id,
                lot_ref_id, serial_id, stock_state, location_ref_id,
                on_hand_qty, reserved_qty
            ) VALUES (
                :stock_balance_id, :warehouse_id, :item_id,
                :lot_ref_id, :serial_id, :stock_state, :location_ref_id,
                :on_hand_qty, :reserved_qty
            )
            """
        ),
        {
            "stock_balance_id": stock_balance_id,
            "warehouse_id": warehouse_id,
            "item_id": item_id,
            "lot_ref_id": lot_ref_id,
            "serial_id": serial_id,
            "stock_state": stock_state,
            "location_ref_id": location_ref_id,
            "on_hand_qty": on_hand_qty,
            "reserved_qty": reserved_qty,
        },
    )


# ---------------------------------------------------------------------------
# 1 y 2. Migración, objetos, índices y claves.
# ---------------------------------------------------------------------------


def test_migracion_aplicada_y_objetos_creados(engine: Engine) -> None:
    with engine.connect() as conn:
        revision = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        assert revision == REVISION_B1 or revision in REVISIONES_POSTERIORES
        # El esquema `wms` quedó aprobado para el almacén virtual (Lote 3),
        # que sólo crea `wms.location_map`. D-06 sigue sin aprobarse: no deben
        # existir las tablas de órdenes de movimiento.
        assert conn.execute(
            text("SELECT EXISTS(SELECT 1 FROM pg_namespace WHERE nspname = 'wms')")
        ).scalar_one(), "El esquema wms del almacén virtual debe existir"
        assert conn.execute(
            text("SELECT EXISTS(SELECT 1 FROM pg_tables WHERE schemaname = 'wms' AND tablename = 'location_map')")
        ).scalar_one(), "Debe existir la tabla versionada del plano 2D"
        assert not conn.execute(
            text(
                "SELECT EXISTS(SELECT 1 FROM pg_tables "
                "WHERE schemaname = 'wms' AND tablename IN ('movement_order', 'movement_order_line'))"
            )
        ).scalar_one(), "D-06 no está aprobada: no deben existir órdenes de movimiento"

        relations = {
            (row[0], row[1]): row[2]
            for row in conn.execute(
                text(
                    """
                    SELECT n.nspname, c.relname, c.relkind
                    FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE (n.nspname, c.relname) IN (
                        ('inv', 'stock_balance_detail'),
                        ('inv', 'v_stock_balance_reconciliation'),
                        ('inv', 'v_kardex'),
                        ('req', 'v_requisition_line_net_quantities')
                    )
                    """
                )
            )
        }
        assert relations[("inv", "stock_balance_detail")] == "r"
        assert relations[("inv", "v_stock_balance_reconciliation")] == "v"
        assert relations[("inv", "v_kardex")] == "v"
        assert relations[("req", "v_requisition_line_net_quantities")] == "v"

        functions = set(
            conn.execute(
                text(
                    """
                    SELECT n.nspname || '.' || p.proname
                    FROM pg_proc p
                    JOIN pg_namespace n ON n.oid = p.pronamespace
                    WHERE n.nspname = 'inv'
                      AND p.proname IN (
                          'fn_block_movement_mutation', 'fn_check_reversal',
                          'fn_check_return_limit', 'fn_check_sbd_reconcile',
                          'backfill_lote_b_detail'
                      )
                    """
                )
            ).scalars()
        )
        assert functions == {
            "inv.fn_block_movement_mutation",
            "inv.fn_check_reversal",
            "inv.fn_check_return_limit",
            "inv.fn_check_sbd_reconcile",
            "inv.backfill_lote_b_detail",
        }

        triggers = set(
            conn.execute(
                text(
                    """
                    SELECT t.tgname
                    FROM pg_trigger t
                    JOIN pg_class c ON c.oid = t.tgrelid
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = 'inv' AND NOT t.tgisinternal
                    """
                )
            ).scalars()
        )
        assert {
            "trg_stock_movement_no_update",
            "trg_stock_movement_no_delete",
            "trg_stock_movement_no_truncate",
            "trg_stock_movement_reversal_guard",
            "trg_stock_movement_return_guard",
            "trg_sbd_reconcile_balance",
            "trg_sbd_reconcile_detail",
        } <= triggers

        movement_columns = set(
            conn.execute(
                text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'inv' AND table_name = 'stock_movement'
                    """
                )
            ).scalars()
        )
        assert {
            "stock_state",
            "serial_id",
            "occurred_at",
            "scope_balance_after_qty",
            "delivery_seq",
            "return_seq",
            "movement_group_id",
            "return_of_movement_id",
            "reversal_reason",
            "reversal_requested_by",
            "reversal_approved_by",
            "approved_by",
            "department_id",
            "requester_id",
            "equipment_id",
            "cost_center_id",
            "work_order_no",
            "movement_order_line_id",
        } <= movement_columns


def test_indices_y_restricciones(engine: Engine) -> None:
    with engine.connect() as conn:
        indexes = set(
            conn.execute(text("SELECT indexname FROM pg_indexes WHERE schemaname = 'inv'")).scalars()
        )
        assert {
            "uq_stock_balance_detail_scope",
            "ix_sbd_warehouse_item_state",
            "ix_sbd_lot_ref",
            "ix_sbd_serial_id",
            "ix_sbd_location_ref",
            "uq_stock_movement_reversal_once",
            "uq_movement_issue_seq",
            "uq_movement_return_seq",
        } <= indexes

        constraints = {
            (row[0], row[1])
            for row in conn.execute(
                text(
                    """
                    SELECT conname, contype
                    FROM pg_constraint c
                    JOIN pg_namespace n ON n.oid = c.connamespace
                    WHERE n.nspname = 'inv'
                    """
                )
            )
        }
        assert ("pk_stock_balance_detail", "p") in constraints
        for name in (
            "ck_sbd_on_hand_no_negativo",
            "ck_sbd_reserved_no_negativo",
            "ck_sbd_reserved_dentro_de_existencia",
            "ck_sbd_stock_state_valido",
            "ck_sbd_reserved_solo_disponible",
            "ck_stock_movement_stock_state",
            "ck_stock_movement_delivery_seq",
            "ck_stock_movement_return_seq",
        ):
            assert (name, "c") in constraints

        detail_fks = {name for name, kind in constraints if kind == "f" and name.startswith("fk_sbd_")}
        assert len(detail_fks) == 8
        assert ("fk_stock_movement_movement_order_line_id", "f") not in constraints, (
            "D-06 no aprobada: movement_order_line_id no debe tener FK a wms"
        )

        index_def = conn.execute(
            text("SELECT indexdef FROM pg_indexes WHERE indexname = 'uq_stock_balance_detail_scope'")
        ).scalar_one()
        assert "COALESCE" in index_def and "stock_state" in index_def


# ---------------------------------------------------------------------------
# 4 y 5. Inmutabilidad del movimiento histórico.
# ---------------------------------------------------------------------------


def test_update_movimiento_historico_rechazado(engine: Engine) -> None:
    with engine.connect() as conn:
        tx = conn.begin()
        try:
            original = _fetch_original(conn)
            with pytest.raises(IntegrityError):
                conn.execute(
                    text(
                        "UPDATE inv.stock_movement SET balance_after_qty = balance_after_qty + 1 "
                        "WHERE id = :id"
                    ),
                    {"id": original["id"]},
                )
        finally:
            tx.rollback()


def test_delete_movimiento_historico_rechazado(engine: Engine) -> None:
    with engine.connect() as conn:
        tx = conn.begin()
        try:
            original = _fetch_original(conn)
            with pytest.raises(IntegrityError):
                conn.execute(
                    text("DELETE FROM inv.stock_movement WHERE id = :id"),
                    {"id": original["id"]},
                )
        finally:
            tx.rollback()


# ---------------------------------------------------------------------------
# 6. Reversos y devoluciones controladas.
# ---------------------------------------------------------------------------


def test_reversion_duplicada_rechazada(engine: Engine) -> None:
    with engine.connect() as conn:
        tx = conn.begin()
        try:
            original = _fetch_original(conn)
            admin_id = _fetch_admin_id(conn)
            _insert_reversal(conn, original, admin_id, "UNICO")
            with pytest.raises(IntegrityError):
                _insert_reversal(conn, original, admin_id, "DUPLICADO")
        finally:
            tx.rollback()


def test_devolucion_invalida_rechazada(engine: Engine) -> None:
    with engine.connect() as conn:
        tx = conn.begin()
        try:
            original = _fetch_original(conn)
            issue_id = _insert_movement(
                conn,
                item_id=original["item_id"],  # type: ignore[arg-type]
                warehouse_id=original["warehouse_id"],  # type: ignore[arg-type]
                movement_type="ISSUE",
                direction="OUT",
                quantity=Decimal("10"),
                lot_id=original["lot_id"],  # type: ignore[arg-type]
                location_id=original["location_id"],  # type: ignore[arg-type]
            )
            with pytest.raises(IntegrityError):
                _insert_movement(
                    conn,
                    item_id=original["item_id"],  # type: ignore[arg-type]
                    warehouse_id=original["warehouse_id"],  # type: ignore[arg-type]
                    movement_type="RETURN",
                    direction="IN",
                    quantity=Decimal("11"),
                    lot_id=original["lot_id"],  # type: ignore[arg-type]
                    location_id=original["location_id"],  # type: ignore[arg-type]
                    return_of_movement_id=issue_id,
                    return_seq=1,
                )
        finally:
            tx.rollback()


# ---------------------------------------------------------------------------
# 7, 8 y 9. Conciliación, heredados y rollback.
# ---------------------------------------------------------------------------


def test_divergencia_de_saldos_detectada(engine: Engine) -> None:
    with engine.connect() as conn:
        tx = conn.begin()
        try:
            original = _fetch_original(conn)
            balance = _fetch_balance(
                conn,
                original["item_id"],  # type: ignore[arg-type]
                original["warehouse_id"],  # type: ignore[arg-type]
            )
            _insert_detail(
                conn,
                stock_balance_id=balance["id"],  # type: ignore[arg-type]
                warehouse_id=original["warehouse_id"],  # type: ignore[arg-type]
                item_id=original["item_id"],  # type: ignore[arg-type]
                on_hand_qty=balance["on_hand_qty"] + Decimal("1"),  # type: ignore[operator]
            )
            with pytest.raises(IntegrityError):
                conn.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
        finally:
            tx.rollback()


def test_compatibilidad_con_datos_heredados(engine: Engine) -> None:
    with engine.connect() as conn:
        tx = conn.begin()
        try:
            original = _fetch_original(conn)
            balance = _fetch_balance(
                conn,
                original["item_id"],  # type: ignore[arg-type]
                original["warehouse_id"],  # type: ignore[arg-type]
            )
            assert conn.execute(text("SELECT COUNT(*) FROM inv.stock_balance_detail")).scalar_one() == 0
            estado = conn.execute(
                text(
                    "SELECT estado FROM inv.v_stock_balance_reconciliation "
                    "WHERE warehouse_id = :warehouse_id AND item_id = :item_id"
                ),
                {"warehouse_id": original["warehouse_id"], "item_id": original["item_id"]},
            ).scalar_one()
            assert estado == "SIN_DETALLE"

            conn.execute(
                text(
                    "UPDATE inv.stock_balance SET on_hand_qty = on_hand_qty + 1, "
                    "version = version + 1 WHERE id = :id"
                ),
                {"id": balance["id"]},
            )
            conn.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
            nuevo = conn.execute(
                text("SELECT on_hand_qty FROM inv.stock_balance WHERE id = :id"),
                {"id": balance["id"]},
            ).scalar_one()
            assert nuevo == balance["on_hand_qty"] + Decimal("1")
        finally:
            tx.rollback()


def test_rollback_ante_error(engine: Engine) -> None:
    with engine.connect() as conn:
        tx = conn.begin()
        try:
            original = _fetch_original(conn)
            balance = _fetch_balance(
                conn,
                original["item_id"],  # type: ignore[arg-type]
                original["warehouse_id"],  # type: ignore[arg-type]
            )
            _insert_detail(
                conn,
                stock_balance_id=balance["id"],  # type: ignore[arg-type]
                warehouse_id=original["warehouse_id"],  # type: ignore[arg-type]
                item_id=original["item_id"],  # type: ignore[arg-type]
                on_hand_qty=balance["on_hand_qty"],  # type: ignore[arg-type]
            )
            conn.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
            assert conn.execute(text("SELECT COUNT(*) FROM inv.stock_balance_detail")).scalar_one() == 1

            with pytest.raises(IntegrityError):
                _insert_detail(
                    conn,
                    stock_balance_id=balance["id"],  # type: ignore[arg-type]
                    warehouse_id=original["warehouse_id"],  # type: ignore[arg-type]
                    item_id=original["item_id"],  # type: ignore[arg-type]
                    on_hand_qty=balance["on_hand_qty"],  # type: ignore[arg-type]
                )
        finally:
            tx.rollback()

    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM inv.stock_balance_detail")).scalar_one() == 0


def test_backfill_manual_idempotente(engine: Engine) -> None:
    with engine.connect() as conn:
        tx = conn.begin()
        try:
            audit_before = conn.execute(text("SELECT COUNT(*) FROM aud.audit_log")).scalar_one()
            assert conn.execute(text("SELECT COUNT(*) FROM inv.stock_balance_detail")).scalar_one() == 0

            inserted = conn.execute(text("SELECT inv.backfill_lote_b_detail()")).scalar_one()
            assert inserted == 3
            assert conn.execute(text("SELECT COUNT(*) FROM inv.stock_balance_detail")).scalar_one() == 3
            estados = set(
                conn.execute(text("SELECT estado FROM inv.v_stock_balance_reconciliation")).scalars()
            )
            assert estados == {"OK"}

            inserted_again = conn.execute(text("SELECT inv.backfill_lote_b_detail()")).scalar_one()
            assert inserted_again == 0
            assert conn.execute(text("SELECT COUNT(*) FROM inv.stock_balance_detail")).scalar_one() == 3

            audit_after = conn.execute(text("SELECT COUNT(*) FROM aud.audit_log")).scalar_one()
            assert audit_after == audit_before + 2
            conn.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
        finally:
            tx.rollback()


# ---------------------------------------------------------------------------
# 10. Concurrencia con conexiones independientes.
# ---------------------------------------------------------------------------


def test_concurrencia_conexiones_independientes(engine: Engine) -> None:
    with engine.connect() as conn_a:
        tx_a = conn_a.begin()
        try:
            original = _fetch_original(conn_a)
            admin_id = _fetch_admin_id(conn_a)
            _insert_reversal(conn_a, original, admin_id, "HOLDER")

            resultado: dict[str, object] = {}
            iniciado = threading.Event()

            def intento_concurrent() -> None:
                iniciado.set()
                try:
                    with engine.connect() as conn_b:
                        tx_b = conn_b.begin()
                        try:
                            conn_b.execute(text("SET LOCAL lock_timeout = '2s'"))
                            _insert_reversal(conn_b, original, admin_id, "CONCURRENTE")
                            tx_b.commit()
                            resultado["ok"] = True
                        except Exception:  # noqa: BLE001
                            tx_b.rollback()
                            raise
                except Exception as exc:  # noqa: BLE001
                    resultado["error"] = exc

            thread = threading.Thread(target=intento_concurrent, name="b1-concurrencia")
            thread.start()
            assert iniciado.wait(timeout=5)
            time.sleep(0.2)
            thread.join(timeout=10)
            assert not thread.is_alive(), "La conexión concurrente quedó bloqueada"

            error = resultado.get("error")
            assert error is not None, "La conexión concurrente debió esperar el bloqueo del original"
            sqlstate = getattr(getattr(error, "orig", None), "sqlstate", None)
            assert sqlstate == "55P03", f"Se esperaba lock_not_available (55P03), obtuvo {sqlstate!r}"
        finally:
            tx_a.rollback()

    # Con el bloqueo liberado, una nueva conexión puede insertar el reverso.
    with engine.connect() as conn_c:
        tx_c = conn_c.begin()
        try:
            _insert_reversal(conn_c, original, admin_id, "LIBERADO")
            conn_c.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
        finally:
            tx_c.rollback()
