"""Endpoints del diseñador profesional de planos 2D/3D (Lote 7).

Permisos separados: consultar, editar borradores y publicar. Las escrituras
requieren CSRF cuando se usa cookie de sesión, igual que el resto del portal.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.deps import require_any_permission, require_permission
from app.api.v1.routers.wms import _allowed_warehouses
from app.db.session import get_db
from app.modules.identity.models import AppUser
from app.modules.identity.service import IdentityService
from app.modules.inventory.models import FloorPlan
from app.modules.inventory.wms_designer_schemas import (
    FloorPlanOut,
    FloorPlanWorkspaceOut,
    PlanImportIn,
    PlanImportPreviewOut,
    PlanPayloadIn,
    RackBlueprintIn,
    RackBlueprintOut,
)
from app.modules.inventory.wms_designer_service import WmsDesignerService
from app.modules.organization.models import Warehouse

router = APIRouter(prefix="/wms/plans", tags=["WMS · Diseñador de planos 2D/3D"])


def _can(db: Session, actor: AppUser, permission: str) -> bool:
    return IdentityService.has_permission(db, actor.id, permission)


def _draft(
    db: Session, plan_id: uuid.UUID, warehouse_id: uuid.UUID
) -> FloorPlan:
    row = db.execute(
        select(FloorPlan).where(
            FloorPlan.id == plan_id,
            FloorPlan.warehouse_id == warehouse_id,
            FloorPlan.status == "DRAFT",
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Borrador inexistente.")
    return row


@router.get("/workspace", response_model=FloorPlanWorkspaceOut)
def workspace(
    warehouse_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_any_permission("warehouse.plan.view", "warehouse.map.view")),
):
    return WmsDesignerService.workspace(
        db,
        actor.id,
        _allowed_warehouses(db, actor),
        warehouse_id,
        can_edit=_can(db, actor, "warehouse.plan.draft"),
        can_publish=_can(db, actor, "warehouse.plan.publish"),
    )


@router.post("/draft", response_model=FloorPlanOut, status_code=201)
def ensure_draft(
    warehouse_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("warehouse.plan.draft")),
):
    result = WmsDesignerService.ensure_draft(
        db, actor.id, _allowed_warehouses(db, actor), warehouse_id
    )
    db.commit()
    return result


@router.put("/{plan_id}", response_model=FloorPlanOut)
def save_draft(
    plan_id: uuid.UUID,
    payload: PlanPayloadIn,
    warehouse_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("warehouse.plan.draft")),
):
    result = WmsDesignerService.save_draft(
        db, actor.id, _allowed_warehouses(db, actor), warehouse_id, plan_id, payload
    )
    db.commit()
    return result


@router.post("/{plan_id}/publish", response_model=FloorPlanWorkspaceOut)
def publish(
    plan_id: uuid.UUID,
    warehouse_id: uuid.UUID,
    revision: int = Query(ge=1),
    notes: str | None = Query(default=None, max_length=500),
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("warehouse.plan.publish")),
):
    result = WmsDesignerService.publish(
        db,
        actor.id,
        _allowed_warehouses(db, actor),
        warehouse_id,
        plan_id,
        revision,
        notes,
    )
    db.commit()
    return result


@router.post("/{plan_id}/racks", response_model=RackBlueprintOut, status_code=201)
def create_rack(
    plan_id: uuid.UUID,
    payload: RackBlueprintIn,
    warehouse_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("warehouse.plan.draft")),
):
    allowed = _allowed_warehouses(db, actor)
    warehouse = db.get(Warehouse, warehouse_id)
    if warehouse is None or (allowed is not None and warehouse_id not in allowed):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Almacén inexistente.")
    draft = _draft(db, plan_id, warehouse_id)
    result = WmsDesignerService.create_rack(
        db,
        actor.id,
        allowed,
        warehouse,
        draft,
        payload,
        can_create_locations=_can(db, actor, "warehouse.location.manage"),
    )
    db.commit()
    return result


@router.post("/import-preview", response_model=PlanImportPreviewOut)
def import_preview(
    payload: PlanImportIn,
    _actor: AppUser = Depends(require_permission("warehouse.plan.draft")),
):
    return WmsDesignerService.import_preview(payload)


@router.get("/{plan_id}/export")
def export_plan(
    plan_id: uuid.UUID,
    warehouse_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_any_permission("warehouse.plan.view", "warehouse.map.view")),
):
    allowed = _allowed_warehouses(db, actor)
    row = db.execute(
        select(FloorPlan).where(
            FloorPlan.id == plan_id, FloorPlan.warehouse_id == warehouse_id
        )
    ).scalar_one_or_none()
    if row is None or (allowed is not None and warehouse_id not in allowed):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plano inexistente.")
    return WmsDesignerService.export(row)
