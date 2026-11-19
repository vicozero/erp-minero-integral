from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api.v1.deps import require_permission
from app.db.session import get_db
from app.modules.identity.models import AppUser
from app.modules.identity.service import IdentityService
from app.modules.requisitions.models import Requisition
from app.modules.requisitions.schemas import (
    DecisionRequest,
    RequisitionAttachmentOut,
    RequisitionCancelIn,
    RequisitionCreate,
    RequisitionDraftUpdate,
    RequisitionOut,
    RequisitionTraceOut,
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
    status_filter: str | None = Query(default=None, alias="status"),
    priority: str | None = None,
    department_id: uuid.UUID | None = None,
    equipment_id: uuid.UUID | None = None,
    document_no: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    sla_color: Literal["GREEN", "YELLOW", "RED", "NONE"] | None = None,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("requisition.view")),
) -> list[dict]:
    stmt = db.query(Requisition)
    if not IdentityService.is_admin(db, actor.id):
        allowed = IdentityService.department_ids(db, actor.id)
        stmt = stmt.filter(Requisition.department_id.in_(allowed))
    if status_filter:
        stmt = stmt.filter(Requisition.status == status_filter)
    if priority:
        stmt = stmt.filter(Requisition.priority == priority)
    if department_id is not None:
        stmt = stmt.filter(Requisition.department_id == department_id)
    if equipment_id is not None:
        stmt = stmt.filter(Requisition.equipment_id == equipment_id)
    if document_no:
        stmt = stmt.filter(Requisition.document_no.ilike(f"%{document_no}%"))
    if date_from is not None:
        stmt = stmt.filter(Requisition.created_at >= date_from)
    if date_to is not None:
        stmt = stmt.filter(Requisition.created_at <= date_to)
    reqs = stmt.order_by(Requisition.created_at.desc()).all()
    results = [Service.to_out(db, req) for req in reqs]
    if sla_color is not None:
        # El color ya fue calculado por SlaService dentro de `to_out`.
        results = [item for item in results if item["sla"]["color"] == sla_color]
    return results


@router.get("/{requisition_id}", response_model=RequisitionOut)
def get_one(
    requisition_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("requisition.view")),
) -> dict:
    req = db.get(Requisition, requisition_id)
    if req is None:
        raise HTTPException(status_code=404, detail="Requisición inexistente.")
    IdentityService.assert_department_access(db, actor.id, req.department_id)
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


@router.post("/{requisition_id}/cancel", response_model=RequisitionOut)
def cancel(
    requisition_id: uuid.UUID,
    payload: RequisitionCancelIn,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("requisition.cancel")),
) -> dict:
    req = Service.cancel(db, actor.id, requisition_id, payload.reason)
    db.commit()
    return Service.to_out(db, req)


@router.get("/{requisition_id}/history")
def history(
    requisition_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("requisition.history.view")),
) -> list[dict]:
    req = db.get(Requisition, requisition_id)
    if req is None:
        raise HTTPException(status_code=404, detail="Requisición inexistente.")
    IdentityService.assert_department_access(db, actor.id, req.department_id)
    return Service.history(db, requisition_id)


@router.get("/{requisition_id}/trace", response_model=RequisitionTraceOut)
def trace(
    requisition_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("requisition.history.view")),
) -> dict:
    """Cadena Requisición → Autorización → Reserva → Entrega → Vale → Seguimiento."""
    return Service.trace(db, actor.id, requisition_id)


@router.post(
    "/{requisition_id}/attachments",
    response_model=RequisitionAttachmentOut,
    status_code=status.HTTP_201_CREATED,
)
def upload_attachment(
    requisition_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("requisition.create")),
):
    content = file.file.read()
    attachment = Service.add_attachment(
        db,
        actor.id,
        requisition_id,
        file_name=file.filename or "archivo",
        content_type=file.content_type or "application/octet-stream",
        content=content,
    )
    db.commit()
    return attachment


@router.get("/{requisition_id}/attachments", response_model=list[RequisitionAttachmentOut])
def list_attachments(
    requisition_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("requisition.view")),
):
    return Service.list_attachments(db, actor.id, requisition_id)


@router.get("/{requisition_id}/attachments/{attachment_id}/download")
def download_attachment(
    requisition_id: uuid.UUID,
    attachment_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("requisition.view")),
):
    from fastapi.responses import FileResponse

    path = Service.attachment_path(db, actor.id, attachment_id)
    return FileResponse(
        path,
        media_type="application/octet-stream",
        filename=next(
            (a.file_name for a in Service.list_attachments(db, actor.id, requisition_id) if a.id == attachment_id),
            "adjunto",
        ),
    )
