from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.v1.deps import require_permission
from app.db.session import get_db
from app.modules.identity.models import AppUser
from app.modules.sla.schemas import (
    EmergencyApprovalIn,
    SlaEvaluationOut,
    SlaPolicyIn,
    SlaPolicyOut,
    SlaPolicyUpdate,
    SlaRequisitionOut,
)
from app.modules.sla.service import SlaService as Service

router = APIRouter(prefix="/sla", tags=["Semáforo SLA"])


@router.get("/policies", response_model=list[SlaPolicyOut])
def list_policies(
    db: Session = Depends(get_db),
    _actor: AppUser = Depends(require_permission("sla.view")),
) -> list:
    return Service.list_policies(db)


@router.post("/policies", response_model=SlaPolicyOut, status_code=status.HTTP_201_CREATED)
def create_policy(
    payload: SlaPolicyIn,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("sla.policy.configure")),
):
    policy = Service.create_policy(db, actor.id, payload)
    db.commit()
    db.refresh(policy)
    return policy


@router.patch("/policies/{policy_id}", response_model=SlaPolicyOut)
def update_policy(
    policy_id: uuid.UUID,
    payload: SlaPolicyUpdate,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("sla.policy.configure")),
):
    policy = Service.update_policy(db, actor.id, policy_id, payload)
    db.commit()
    db.refresh(policy)
    return policy


@router.post("/policies/{policy_id}/emergency", response_model=SlaPolicyOut)
def approve_emergency(
    policy_id: uuid.UUID,
    payload: EmergencyApprovalIn,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("sla.policy.approve")),
):
    policy = Service.set_emergency(db, actor.id, policy_id, payload)
    db.commit()
    db.refresh(policy)
    return policy


@router.get("/requisitions", response_model=list[SlaRequisitionOut])
def list_requisitions(
    color: str | None = Query(default=None, alias="sla_color"),
    status_filter: str | None = Query(default=None, alias="status"),
    priority: str | None = None,
    department_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("sla.view")),
) -> list[dict]:
    return Service.list_requisitions(
        db,
        actor.id,
        color=color,
        status_filter=status_filter,
        priority=priority,
        department_id=department_id,
    )


@router.get("/requisitions/{requisition_id}", response_model=SlaRequisitionOut)
def get_requisition(
    requisition_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("sla.view")),
) -> dict:
    return Service.get_requisition(db, actor.id, requisition_id)


@router.get("/requisitions/{requisition_id}/history", response_model=list[SlaEvaluationOut])
def history(
    requisition_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("sla.view")),
) -> list[dict]:
    return Service.history(db, actor.id, requisition_id)


@router.post("/evaluate", response_model=list[dict])
def evaluate_active(
    department_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("sla.policy.configure")),
) -> list[dict]:
    result = Service.evaluate_active(db, actor.id, department_id=department_id)
    db.commit()
    return result
