from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.deps import require_permission
from app.db.session import get_db
from app.modules.identity.models import AppUser
from app.modules.purchasing.models import PurchaseOrder
from app.modules.purchasing.schemas import (
    PurchaseFromShortagesIn,
    PurchaseOrderCancelIn,
    PurchaseOrderOut,
    ReceiptIn,
)
from app.modules.purchasing.service import PurchasingService

router = APIRouter(prefix="/purchases", tags=["Compras"])


@router.post(
    "/from-shortages",
    response_model=PurchaseOrderOut,
    status_code=status.HTTP_201_CREATED,
)
def create_from_shortages(
    payload: PurchaseFromShortagesIn,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("purchase.order.create")),
):
    po = PurchasingService.create_from_shortages(db, actor.id, payload)
    db.commit()
    return po


@router.get("", response_model=list[PurchaseOrderOut])
def list_all(
    db: Session = Depends(get_db),
    _actor: AppUser = Depends(require_permission("purchase.view")),
):
    return list(db.query(PurchaseOrder).order_by(PurchaseOrder.created_at.desc()).all())


@router.get("/{purchase_order_id}", response_model=PurchaseOrderOut)
def get_one(
    purchase_order_id: uuid.UUID,
    db: Session = Depends(get_db),
    _actor: AppUser = Depends(require_permission("purchase.view")),
):
    po = db.get(PurchaseOrder, purchase_order_id)
    if po is None:
        raise HTTPException(status_code=404, detail="Orden de compra inexistente.")
    return po


@router.post("/{purchase_order_id}/approve", response_model=PurchaseOrderOut)
def approve(
    purchase_order_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("purchase.order.approve")),
):
    po = PurchasingService.approve(db, actor.id, purchase_order_id)
    db.commit()
    return po


@router.post("/{purchase_order_id}/cancel", response_model=PurchaseOrderOut)
def cancel(
    purchase_order_id: uuid.UUID,
    payload: PurchaseOrderCancelIn,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("purchase.order.approve")),
):
    po = PurchasingService.cancel(db, actor.id, purchase_order_id, payload.reason)
    db.commit()
    return po


@router.post("/{purchase_order_id}/receive", status_code=status.HTTP_201_CREATED)
def receive(
    purchase_order_id: uuid.UUID,
    payload: ReceiptIn,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("purchase.receive")),
) -> dict:
    grn = PurchasingService.receive(db, actor.id, purchase_order_id, payload)
    db.commit()
    return {"id": str(grn.id), "document_no": grn.document_no}
