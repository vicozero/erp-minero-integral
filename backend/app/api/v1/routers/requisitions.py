from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.deps import require_permission
from app.db.session import get_db
from app.modules.identity.models import AppUser
from app.modules.requisitions.models import Requisition
from app.modules.requisitions.schemas import (
    DecisionRequest,
    RequisitionCreate,
    RequisitionDraftUpdate,
    RequisitionOut,
)
from app.modules.requisitions.service import RequisitionService as Service

router = APIRouter(prefix="/requisitions", tags=["Requisiciones"])


@router.post("", response_model=RequisitionOut, status_code=status.HTTP_201_CREATED)
def create(
    payload: RequisitionCreate,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("requisition.create")),
) -> dict:
    req = Service.create(db, actor.id, payload)
    db.commit()
    return Service.to_out(db, req)


@router.get("", response_model=list[RequisitionOut])
def list_all(
    db: Session = Depends(get_db),
    _actor: AppUser = Depends(require_permission("requisition.view")),
) -> list[dict]:
    reqs = db.query(Requisition).order_by(Requisition.created_at.desc()).all()
    return [Service.to_out(db, req) for req in reqs]


@router.get("/{requisition_id}", response_model=RequisitionOut)
def get_one(
    requisition_id: uuid.UUID,
    db: Session = Depends(get_db),
    _actor: AppUser = Depends(require_permission("requisition.view")),
) -> dict:
    req = db.get(Requisition, requisition_id)
    if req is None:
        raise HTTPException(status_code=404, detail="Requisición inexistente.")
    return Service.to_out(db, req)


@router.patch("/{requisition_id}/draft", response_model=RequisitionOut)
def update_draft(
    requisition_id: uuid.UUID,
    payload: RequisitionDraftUpdate,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("requisition.create")),
) -> dict:
    req = Service.update_draft(db, actor.id, requisition_id, payload)
    db.commit()
    return Service.to_out(db, req)


@router.post("/{requisition_id}/submit", response_model=RequisitionOut)
def submit(
    requisition_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("requisition.submit")),
) -> dict:
    req = Service.submit(db, actor.id, requisition_id)
    db.commit()
    return Service.to_out(db, req)


@router.post("/{requisition_id}/decide", response_model=RequisitionOut)
def decide(
    requisition_id: uuid.UUID,
    payload: DecisionRequest,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("requisition.approve")),
) -> dict:
    req = Service.decide(db, actor.id, requisition_id, payload)
    db.commit()
    return Service.to_out(db, req)


@router.get("/{requisition_id}/history")
def history(
    requisition_id: uuid.UUID,
    db: Session = Depends(get_db),
    _actor: AppUser = Depends(require_permission("requisition.history.view")),
) -> list[dict]:
    return Service.history(db, requisition_id)
