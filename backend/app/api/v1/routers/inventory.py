from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.deps import require_permission
from app.db.session import get_db
from app.modules.identity.models import AppUser
from app.modules.identity.service import IdentityService
from app.modules.inventory.models import StockMovement, StockReservation
from app.modules.requisitions.models import Requisition, RequisitionLine
from app.modules.inventory.schemas import (
    AvailabilityOut,
    ExpirationResult,
    IssueIn,
    MovementOut,
    ReserveIn,
    ReservationOut,
)
from app.modules.inventory.service import InventoryService

router = APIRouter(prefix="/inventory", tags=["Almacén"])


def _warehouse_for_requisition_line(db: Session, line_id: uuid.UUID) -> uuid.UUID:
    warehouse_id = db.execute(
        select(Requisition.warehouse_id)
        .select_from(RequisitionLine)
        .join(Requisition, Requisition.id == RequisitionLine.requisition_id)
        .where(RequisitionLine.id == line_id)
    ).scalar_one_or_none()
    if warehouse_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Partida de requisición inexistente.")
    return warehouse_id


@router.get("/availability", response_model=AvailabilityOut)
def availability(
    item_id: uuid.UUID = Query(...),
    warehouse_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("inventory.availability.view")),
) -> dict:
    IdentityService.assert_warehouse_access(db, actor.id, warehouse_id)
    result = InventoryService.availability(db, item_id, warehouse_id)
    db.commit()
    return result


@router.post("/reservations", response_model=ReservationOut, status_code=201)
def reserve(
    payload: ReserveIn,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("inventory.reserve")),
):
    warehouse_id = _warehouse_for_requisition_line(db, payload.requisition_line_id)
    IdentityService.assert_warehouse_access(db, actor.id, warehouse_id)
    reservation = InventoryService.reserve(db, actor.id, payload)
    db.commit()
    return reservation


@router.post("/issues", response_model=MovementOut, status_code=201)
def issue(
    payload: IssueIn,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("inventory.issue")),
):
    warehouse_id = _warehouse_for_requisition_line(db, payload.requisition_line_id)
    IdentityService.assert_warehouse_access(db, actor.id, warehouse_id)
    movement = InventoryService.issue(db, actor.id, payload)
    db.commit()
    return movement


@router.get("/kardex", response_model=list[MovementOut])
def kardex(
    item_id: uuid.UUID | None = None,
    warehouse_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("inventory.kardex.view")),
):
    allowed = IdentityService.allowed_warehouse_ids(db, actor.id)
    stmt = select(StockMovement).order_by(StockMovement.posted_at.desc())
    if item_id is not None:
        stmt = stmt.where(StockMovement.item_id == item_id)
    if warehouse_id is not None:
        IdentityService.assert_warehouse_access(db, actor.id, warehouse_id)
        stmt = stmt.where(StockMovement.warehouse_id == warehouse_id)
    elif allowed is not None:
        stmt = stmt.where(StockMovement.warehouse_id.in_(allowed))
    return list(db.execute(stmt).scalars())


@router.post("/reservations/expire", response_model=ExpirationResult)
def expire_reservations(
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("inventory.reserve")),
) -> dict:
    allowed = IdentityService.allowed_warehouse_ids(db, actor.id)
    released = InventoryService.expire_reservations(db, actor.id, allowed)
    db.commit()
    return {"released": released}


@router.get("/reservations", response_model=list[ReservationOut])
def reservations(
    requisition_line_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("inventory.kardex.view")),
):
    allowed = IdentityService.allowed_warehouse_ids(db, actor.id)
    stmt = select(StockReservation).order_by(StockReservation.created_at.desc())
    if requisition_line_id is not None:
        warehouse_id = _warehouse_for_requisition_line(db, requisition_line_id)
        IdentityService.assert_warehouse_access(db, actor.id, warehouse_id)
        stmt = stmt.where(StockReservation.requisition_line_id == requisition_line_id)
    elif allowed is not None:
        stmt = stmt.where(StockReservation.warehouse_id.in_(allowed))
    return list(db.execute(stmt).scalars())
