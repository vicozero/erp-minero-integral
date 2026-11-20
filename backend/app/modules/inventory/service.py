from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import NoReturn

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.audit.service import AuditService
from app.modules.documentation.models import DocumentRegistry
from app.modules.inventory.models import (
    NULL_UUID,
    StockBalance,
    StockBalanceDetail,
    StockMovement,
    StockReservation,
)
from app.modules.master_data.models import Item
from app.modules.organization.models import Warehouse
from app.modules.requisitions.models import Requisition, RequisitionLine
from app.modules.sla.service import SlaService
from app.shared.constants import APPROVABLE_STATUSES
from app.shared.events import emit
from app.shared.idempotency import acquire, complete
from app.shared.numbering import attach_entity, next_document_number, record_document_event


class InventoryError(HTTPException):
    pass


def _fail(detail: str, code: int = status.HTTP_409_CONFLICT) -> NoReturn:
    raise InventoryError(status_code=code, detail=detail)


def _sync_balance_detail(
    db: Session,
    balance: StockBalance,
    actor_id: uuid.UUID | None,
) -> StockBalanceDetail:
    """Mantiene la proyección detallada alineada con el saldo agregado.

    El trigger de reconciliación y el backfill documentado comparan sumas por
    ``(warehouse_id, item_id)``, no por ``stock_balance_id``. Por eso se busca
    el detalle por el ámbito canónico y se le asigna el total del saldo agregado
    menos el resto de renglones de detalle del mismo par. Así funciona tanto con
    un backfill previo como con varios saldos heredados por almacén/artículo.
    """
    balances = list(
        db.execute(
            select(StockBalance)
            .where(
                StockBalance.warehouse_id == balance.warehouse_id,
                StockBalance.item_id == balance.item_id,
            )
            .order_by(StockBalance.id)
            .with_for_update()
        ).scalars()
    )
    legacy_on_hand = sum((row.on_hand_qty for row in balances), Decimal("0"))
    legacy_reserved = sum((row.reserved_qty for row in balances), Decimal("0"))

    details = list(
        db.execute(
            select(StockBalanceDetail)
            .where(
                StockBalanceDetail.warehouse_id == balance.warehouse_id,
                StockBalanceDetail.item_id == balance.item_id,
            )
            .order_by(StockBalanceDetail.created_at, StockBalanceDetail.id)
            .with_for_update()
        ).scalars()
    )

    def canonical_scope(row: StockBalanceDetail) -> tuple[uuid.UUID, uuid.UUID, str, uuid.UUID]:
        return (
            row.lot_ref_id or NULL_UUID,
            row.serial_id or NULL_UUID,
            row.stock_state,
            row.location_ref_id or NULL_UUID,
        )

    target_scope = (
        balance.lot_ref_id or NULL_UUID,
        NULL_UUID,
        "AVAILABLE",
        balance.location_ref_id or NULL_UUID,
    )
    own = [row for row in details if canonical_scope(row) == target_scope]
    if len(own) > 1:
        _fail("Existe más de una proyección detallada para el mismo ámbito.")
    other = [row for row in details if canonical_scope(row) != target_scope]
    other_on_hand = sum((row.on_hand_qty for row in other), Decimal("0"))
    other_reserved = sum((row.reserved_qty for row in other), Decimal("0"))
    target_on_hand = legacy_on_hand - other_on_hand
    target_reserved = legacy_reserved - other_reserved
    if target_on_hand < 0 or target_reserved < 0 or target_reserved > target_on_hand:
        _fail("La proyección detallada no puede conciliarse con el saldo agregado.")

    if own:
        detail = own[0]
        detail.on_hand_qty = target_on_hand
        detail.reserved_qty = target_reserved
        detail.lot_ref_id = balance.lot_ref_id
        detail.location_ref_id = balance.location_ref_id
        detail.updated_by = actor_id
        detail.updated_at = datetime.now(timezone.utc)
        detail.version += 1
    else:
        detail = StockBalanceDetail(
            stock_balance_id=balance.id,
            warehouse_id=balance.warehouse_id,
            item_id=balance.item_id,
            lot_ref_id=balance.lot_ref_id,
            serial_id=None,
            stock_state="AVAILABLE",
            location_ref_id=balance.location_ref_id,
            on_hand_qty=target_on_hand,
            reserved_qty=target_reserved,
            created_by=actor_id,
        )
        db.add(detail)
    db.flush()
    return detail


def _get_or_create_balance(
    db: Session,
    warehouse_id: uuid.UUID,
    item_id: uuid.UUID,
    actor_id: uuid.UUID | None = None,
) -> StockBalance:
    balance = db.execute(
        select(StockBalance)
        .where(
            StockBalance.warehouse_id == warehouse_id,
            StockBalance.item_id == item_id,
            StockBalance.lot_id == NULL_UUID,
            StockBalance.location_id == NULL_UUID,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if balance is None:
        balance = StockBalance(
            warehouse_id=warehouse_id,
            item_id=item_id,
            lot_id=NULL_UUID,
            location_id=NULL_UUID,
            on_hand_qty=Decimal("0"),
            reserved_qty=Decimal("0"),
            created_by=actor_id,
        )
        db.add(balance)
        db.flush()
    _sync_balance_detail(db, balance, actor_id)
    return balance


def _release_reservation(
    db: Session,
    reservation: StockReservation,
    actor_id: uuid.UUID,
    reason: str,
    new_status: str,
) -> None:
    """Libera el remanente de una reserva y descuenta el saldo reservado."""
    remaining = reservation.quantity - reservation.consumed_qty
    if remaining <= Decimal("0"):
        reservation.status = new_status
        return
    balance = db.execute(
        select(StockBalance)
        .where(
            StockBalance.warehouse_id == reservation.warehouse_id,
            StockBalance.item_id == reservation.item_id,
            StockBalance.lot_id == reservation.lot_id,
            StockBalance.location_id == reservation.location_id,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if balance is not None:
        balance.reserved_qty = max(Decimal("0"), balance.reserved_qty - remaining)
        _sync_balance_detail(db, balance, actor_id)
    reservation.status = new_status
    reservation.updated_by = actor_id
    AuditService.record(
        db,
        action="STOCK_RESERVATION_RELEASED",
        entity_type="StockReservation",
        entity_id=reservation.id,
        actor_id=actor_id,
        before={"status": "ACTIVE", "remaining_qty": str(remaining)},
        after={"status": new_status, "remaining_qty": "0"},
        detail=reason,
    )
    emit(
        db,
        "StockReservation",
        reservation.id,
        "STOCK_RESERVATION_RELEASED",
        {"reason": reason, "quantity": str(remaining)},
    )


class InventoryService:
    @staticmethod
    def availability(db: Session, item_id: uuid.UUID, warehouse_id: uuid.UUID) -> dict:
        item = db.get(Item, item_id)
        warehouse = db.get(Warehouse, warehouse_id)
        if item is None or warehouse is None:
            _fail("Artículo o almacén inexistente.", status.HTTP_404_NOT_FOUND)
        balance = db.execute(
            select(StockBalance).where(
                StockBalance.warehouse_id == warehouse_id,
                StockBalance.item_id == item_id,
                StockBalance.lot_id == NULL_UUID,
                StockBalance.location_id == NULL_UUID,
            )
        ).scalar_one_or_none()
        on_hand = balance.on_hand_qty if balance else Decimal("0")
        reserved = balance.reserved_qty if balance else Decimal("0")
        return {
            "item_id": item_id,
            "item_code": item.code,
            "warehouse_id": warehouse_id,
            "warehouse_code": warehouse.code,
            "on_hand_qty": on_hand,
            "reserved_qty": reserved,
            "available_qty": on_hand - reserved,
        }

    @staticmethod
    def line_reserved_qty(db: Session, requisition_line_id: uuid.UUID) -> Decimal:
        value = db.execute(
            select(func.coalesce(func.sum(StockReservation.quantity - StockReservation.consumed_qty), 0)).where(
                StockReservation.requisition_line_id == requisition_line_id,
                StockReservation.status == "ACTIVE",
                StockReservation.expires_at > datetime.now(timezone.utc),
            )
        ).scalar_one()
        return Decimal(str(value))

    @staticmethod
    def line_delivered_qty(db: Session, requisition_line_id: uuid.UUID) -> Decimal:
        value = db.execute(
            select(func.coalesce(func.sum(StockMovement.quantity), 0)).where(
                StockMovement.requisition_line_id == requisition_line_id,
                StockMovement.movement_type == "ISSUE",
                StockMovement.status == "POSTED",
            )
        ).scalar_one()
        return Decimal(str(value))

    @staticmethod
    def release_line_reservations(
        db: Session,
        requisition_line_id: uuid.UUID,
        actor_id: uuid.UUID,
        reason: str,
    ) -> int:
        """Libera de forma transaccional todas las reservas activas de una partida.

        La fila de la partida ya debe estar bloqueada por el servidor llamante
        para que la liberación no compita con una entrega concurrente.
        """
        reservations = list(
            db.execute(
                select(StockReservation)
                .where(
                    StockReservation.requisition_line_id == requisition_line_id,
                    StockReservation.status == "ACTIVE",
                )
                .with_for_update()
            ).scalars()
        )
        for reservation in reservations:
            _release_reservation(db, reservation, actor_id, reason, "RELEASED")
        return len(reservations)

    @staticmethod
    def expire_reservations(
        db: Session,
        actor_id: uuid.UUID,
        warehouse_ids: list[uuid.UUID] | None = None,
    ) -> int:
        """Libera reservas vencidas del alcance indicado.

        ``warehouse_ids=None`` conserva el comportamiento global para
        administradores; una lista vacía no libera ninguna reserva.
        """
        now = datetime.now(timezone.utc)
        stmt = select(StockReservation).where(
            StockReservation.status == "ACTIVE",
            StockReservation.expires_at <= now,
        )
        if warehouse_ids is not None:
            stmt = stmt.where(StockReservation.warehouse_id.in_(warehouse_ids))
        reservations = list(
            db.execute(
                stmt.order_by(StockReservation.expires_at).with_for_update(of=StockReservation)
            ).scalars()
        )
        for reservation in reservations:
            _release_reservation(db, reservation, actor_id, "Vencimiento de reserva", "EXPIRED")
        return len(reservations)

    @staticmethod
    def _maybe_close_requisition(db: Session, req: Requisition, actor_id: uuid.UUID) -> None:
        """Cierra la requisición cuando todas sus partidas están conciliadas."""
        lines = list(
            db.execute(
                select(RequisitionLine).where(RequisitionLine.requisition_id == req.id).with_for_update()
            ).scalars()
        )
        if not lines:
            return
        for line in lines:
            if line.status in ("CANCELLED", "CLOSED"):
                continue
            if InventoryService.line_delivered_qty(db, line.id) < line.authorised_qty:
                return
        for line in lines:
            if line.status == "CANCELLED":
                continue
            line.status = "CLOSED"
            line.updated_by = actor_id
        req.status = "CLOSED"
        req.closed_at = datetime.now(timezone.utc)
        req.updated_by = actor_id
        registry = db.get(DocumentRegistry, req.document_registry_id)
        if registry is not None:
            record_document_event(db, registry, "REQUISITION_CLOSED", req.status, "CLOSED", actor_id)
        AuditService.record(
            db,
            action="REQUISITION_CLOSE",
            entity_type="Requisition",
            entity_id=req.id,
            actor_id=actor_id,
            before={"status": "IN_PROGRESS"},
            after={"status": "CLOSED"},
            detail="Todas las partidas fueron entregadas o canceladas.",
        )
        emit(db, "Requisition", req.id, "REQUISITION_CLOSED", {})
        SlaService.record_snapshot(db, req, trigger="ON_CLOSE", actor_id=actor_id)

    @staticmethod
    def reserve(
        db: Session,
        actor_id: uuid.UUID,
        payload,
    ) -> StockReservation:
        idem = payload.idempotency_key or f"reserve:{payload.requisition_line_id}:{payload.quantity}"
        record, created = acquire(
            db,
            idem,
            operation="inventory.reserve",
            entity_type="StockReservation",
        )
        if not created:
            if record.entity_id is not None:
                existing = db.get(StockReservation, record.entity_id)
                if existing is not None:
                    return existing
            existing = db.execute(
                select(StockReservation).where(StockReservation.idempotency_key == idem)
            ).scalar_one_or_none()
            if existing is not None:
                return existing
            _fail("La clave de idempotencia ya fue utilizada por otra operación.")

        line = db.execute(
            select(RequisitionLine).where(RequisitionLine.id == payload.requisition_line_id).with_for_update()
        ).scalar_one_or_none()
        if line is None:
            _fail("Partida de requisición inexistente.", status.HTTP_404_NOT_FOUND)
        req = db.get(Requisition, line.requisition_id)
        if req is None or req.status not in APPROVABLE_STATUSES:
            _fail("La requisición no está autorizada para reservar.")
        if req.warehouse_id is None:
            _fail("La requisición no tiene almacén definido.")
        if line.item_id is None:
            _fail("La partida no tiene artículo asociado.")

        delivered = InventoryService.line_delivered_qty(db, line.id)
        reserved = InventoryService.line_reserved_qty(db, line.id)
        remaining_auth = line.authorised_qty - delivered - reserved
        if payload.quantity > remaining_auth:
            _fail("La cantidad excede lo autorizado pendiente de reservar.")

        balance = _get_or_create_balance(db, req.warehouse_id, line.item_id, actor_id)
        available = balance.on_hand_qty - balance.reserved_qty
        if payload.quantity > available:
            _fail("Existencia disponible insuficiente.")

        registry, reservation_no = next_document_number(
            db,
            "RES",
            req.company_id,
            series="LAG",
            mining_unit_id=req.mining_unit_id,
        )
        reservation = StockReservation(
            reservation_no=reservation_no,
            requisition_line_id=line.id,
            item_id=line.item_id,
            warehouse_id=req.warehouse_id,
            lot_id=NULL_UUID,
            location_id=NULL_UUID,
            quantity=payload.quantity,
            consumed_qty=Decimal("0"),
            status="ACTIVE",
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            idempotency_key=idem,
            created_by=actor_id,
        )
        db.add(reservation)
        balance.reserved_qty += payload.quantity
        _sync_balance_detail(db, balance, actor_id)
        db.flush()
        attach_entity(db, registry, "StockReservation", reservation.id)
        record_document_event(db, registry, "STOCK_RESERVED", req.status, req.status, actor_id)
        AuditService.record(
            db,
            action="STOCK_RESERVE",
            entity_type="StockReservation",
            entity_id=reservation.id,
            actor_id=actor_id,
            after={
                "requisition_line_id": str(line.id),
                "quantity": str(payload.quantity),
                "warehouse_id": str(req.warehouse_id),
            },
        )
        emit(
            db,
            "StockReservation",
            reservation.id,
            "STOCK_RESERVED",
            {"quantity": str(payload.quantity), "requisition_line_id": str(line.id)},
        )
        complete(db, record, reservation.id)
        return reservation

    @staticmethod
    def issue(
        db: Session,
        actor_id: uuid.UUID,
        payload,
    ) -> StockMovement:
        idem = payload.idempotency_key or f"issue:{payload.requisition_line_id}:{payload.quantity}"
        record, created = acquire(
            db,
            idem,
            operation="inventory.issue",
            entity_type="StockMovement",
        )
        if not created:
            if record.entity_id is not None:
                existing = db.get(StockMovement, record.entity_id)
                if existing is not None:
                    return existing
            existing = db.execute(
                select(StockMovement).where(StockMovement.idempotency_key == idem)
            ).scalar_one_or_none()
            if existing is not None:
                return existing
            _fail("La clave de idempotencia ya fue utilizada por otra operación.")

        line = db.execute(
            select(RequisitionLine).where(RequisitionLine.id == payload.requisition_line_id).with_for_update()
        ).scalar_one_or_none()
        if line is None:
            _fail("Partida de requisición inexistente.", status.HTTP_404_NOT_FOUND)
        req = db.get(Requisition, line.requisition_id)
        if req is None or req.status not in APPROVABLE_STATUSES:
            _fail("La requisición no está autorizada para entregar.")
        if req.warehouse_id is None:
            _fail("La requisición no tiene almacén definido.")

        now = datetime.now(timezone.utc)
        stmt = select(StockReservation).where(
            StockReservation.requisition_line_id == line.id,
            StockReservation.status == "ACTIVE",
            StockReservation.expires_at > now,
        )
        if payload.reservation_id is not None:
            stmt = stmt.where(StockReservation.id == payload.reservation_id)
        reservations = list(db.execute(stmt.order_by(StockReservation.created_at).with_for_update()).scalars())
        if not reservations:
            _fail("No existe reserva activa para esta partida.")

        available_reserved = sum((r.quantity - r.consumed_qty for r in reservations), Decimal("0"))
        if payload.quantity > available_reserved:
            _fail("La entrega excede la reserva activa; reserve primero la cantidad faltante.")

        delivered = InventoryService.line_delivered_qty(db, line.id)
        if delivered + payload.quantity > line.authorised_qty:
            _fail("La entrega excede la cantidad autorizada.")

        balance = _get_or_create_balance(
            db, req.warehouse_id, line.item_id or reservations[0].item_id, actor_id
        )
        if balance.on_hand_qty - payload.quantity < Decimal("0"):
            _fail("La entrega dejaría existencia negativa.")
        if balance.reserved_qty - payload.quantity < Decimal("0"):
            _fail("La entrega excede la cantidad reservada.")
        remaining = payload.quantity
        for reservation in reservations:
            if remaining <= 0:
                break
            part = min(remaining, reservation.quantity - reservation.consumed_qty)
            reservation.consumed_qty += part
            if reservation.consumed_qty >= reservation.quantity:
                reservation.status = "CONSUMED"
            reservation.updated_by = actor_id
            remaining -= part

        balance.on_hand_qty -= payload.quantity
        balance.reserved_qty -= payload.quantity
        _sync_balance_detail(db, balance, actor_id)

        registry, movement_no = next_document_number(
            db,
            "INV_MOV",
            req.company_id,
            series="LAG",
            mining_unit_id=req.mining_unit_id,
        )
        movement = StockMovement(
            movement_no=movement_no,
            document_registry_id=registry.id,
            movement_type="ISSUE",
            direction="OUT",
            quantity=payload.quantity,
            item_id=balance.item_id,
            warehouse_id=balance.warehouse_id,
            lot_id=NULL_UUID,
            location_id=NULL_UUID,
            balance_after_qty=balance.on_hand_qty,
            requisition_line_id=line.id,
            source_document_type="REQUISITION",
            source_document_id=req.id,
            idempotency_key=idem,
            created_by=actor_id,
        )
        db.add(movement)
        db.flush()
        attach_entity(db, registry, "StockMovement", movement.id)
        record_document_event(db, registry, "STOCK_ISSUED", req.status, "IN_PROGRESS", actor_id)
        AuditService.record(
            db,
            action="STOCK_ISSUE",
            entity_type="StockMovement",
            entity_id=movement.id,
            actor_id=actor_id,
            after={
                "requisition_line_id": str(line.id),
                "quantity": str(payload.quantity),
                "balance_after": str(balance.on_hand_qty),
            },
        )
        emit(
            db,
            "StockMovement",
            movement.id,
            "STOCK_ISSUED",
            {"quantity": str(payload.quantity), "requisition_line_id": str(line.id)},
        )
        complete(db, record, movement.id)
        InventoryService._maybe_close_requisition(db, req, actor_id)
        return movement

    @staticmethod
    def receive_stock(
        db: Session,
        *,
        actor_id: uuid.UUID,
        company_id: uuid.UUID,
        mining_unit_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        item_id: uuid.UUID,
        quantity: Decimal,
        idempotency_key: str,
        source_document_type: str,
        source_document_id: uuid.UUID,
        purchase_order_line_id: uuid.UUID | None = None,
    ) -> StockMovement:
        record, created = acquire(
            db,
            idempotency_key,
            operation="inventory.receive_stock",
            entity_type="StockMovement",
        )
        if not created:
            if record.entity_id is not None:
                existing = db.get(StockMovement, record.entity_id)
                if existing is not None:
                    return existing
            existing = db.execute(
                select(StockMovement).where(StockMovement.idempotency_key == idempotency_key)
            ).scalar_one_or_none()
            if existing is not None:
                return existing
            _fail("La clave de idempotencia ya fue utilizada por otra operación.")

        balance = _get_or_create_balance(db, warehouse_id, item_id, actor_id)
        balance.on_hand_qty += quantity
        _sync_balance_detail(db, balance, actor_id)
        registry, movement_no = next_document_number(
            db,
            "INV_MOV",
            company_id,
            series="LAG",
            mining_unit_id=mining_unit_id,
        )
        movement = StockMovement(
            movement_no=movement_no,
            document_registry_id=registry.id,
            movement_type="RECEIPT",
            direction="IN",
            quantity=quantity,
            item_id=item_id,
            warehouse_id=warehouse_id,
            lot_id=NULL_UUID,
            location_id=NULL_UUID,
            balance_after_qty=balance.on_hand_qty,
            purchase_order_line_id=purchase_order_line_id,
            source_document_type=source_document_type,
            source_document_id=source_document_id,
            idempotency_key=idempotency_key,
            created_by=actor_id,
        )
        db.add(movement)
        db.flush()
        attach_entity(db, registry, "StockMovement", movement.id)
        record_document_event(db, registry, "STOCK_RECEIVED", None, "POSTED", actor_id)
        AuditService.record(
            db,
            action="STOCK_RECEIPT",
            entity_type="StockMovement",
            entity_id=movement.id,
            actor_id=actor_id,
            after={"quantity": str(quantity), "warehouse_id": str(warehouse_id)},
        )
        emit(
            db,
            "StockMovement",
            movement.id,
            "STOCK_RECEIVED",
            {"quantity": str(quantity), "source": source_document_type},
        )
        complete(db, record, movement.id)
        return movement
