from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.deps import require_permission
from app.db.session import get_db
from app.modules.identity.models import AppUser
from app.modules.inventory.models import StockMovement, StockReservation
from app.modules.inventory.schemas import AvailabilityOut, IssueIn, MovementOut, ReserveIn, ReservationOut
from app.modules.inventory.service import InventoryService

router = APIRouter(prefix="/inventory", tags=["Almacén"])


@router.get("/availability", response_model=AvailabilityOut)
def availability(
    item_id: uuid.UUID = Query(...),
    warehouse_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    _actor: AppUser = Depends(require_permission("inventory.availability.view")),
) -> dict:
    result = InventoryService.availability(db, item_id, warehouse_id)
    db.commit()
    return result


@router.post("/reservations", response_model=ReservationOut, status_code=201)
def reserve(
    payload: ReserveIn,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("inventory.reserve")),
):
    reservation = InventoryService.reserve(db, actor.id, payload)
    db.commit()
    return reservation


@router.post("/issues", response_model=MovementOut, status_code=201)
def issue(
    payload: IssueIn,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("inventory.issue")),
):
    movement = InventoryService.issue(db, actor.id, payload)
    db.commit()
    return movement


@router.get("/kardex", response_model=list[MovementOut])
def kardex(
    item_id: uuid.UUID | None = None,
    warehouse_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    _actor: AppUser = Depends(require_permission("inventory.kardex.view")),
):
    stmt = select(StockMovement).order_by(StockMovement.posted_at.desc())
    if item_id is not None:
        stmt = stmt.where(StockMovement.item_id == item_id)
    if warehouse_id is not None:
        stmt = stmt.where(StockMovement.warehouse_id == warehouse_id)
    return list(db.execute(stmt).scalars())


@router.get("/reservations", response_model=list[ReservationOut])
def reservations(
    requisition_line_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    _actor: AppUser = Depends(require_permission("inventory.kardex.view")),
):
    stmt = select(StockReservation).order_by(StockReservation.created_at.desc())
    if requisition_line_id is not None:
        stmt = stmt.where(StockReservation.requisition_line_id == requisition_line_id)
    return list(db.execute(stmt).scalars())
