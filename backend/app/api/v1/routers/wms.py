from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.deps import require_permission
from app.db.session import get_db
from app.modules.identity.models import AppUser
from app.modules.identity.service import IdentityService
from app.modules.inventory.wms_service import WmsCatalogService
from app.modules.master_data.schemas import (
    FamilyIn,
    FamilyOut,
    ItemDetailOut,
    ItemSearchOut,
    LocationDetailOut,
    LocationIn,
    LocationOut,
    PhotoOut,
)
from app.modules.organization.models import Warehouse

router = APIRouter(prefix="/wms", tags=["WMS · Catálogo y ubicaciones"])


def _allowed_warehouses(db: Session, actor: AppUser) -> list[uuid.UUID] | None:
    """None significa acceso total; lista vacía, ningún almacén permitido."""
    if IdentityService.is_admin(db, actor.id):
        return None
    unit_ids = IdentityService.mining_unit_ids(db, actor.id)
    if not unit_ids:
        return []
    return list(
        db.execute(select(Warehouse.id).where(Warehouse.mining_unit_id.in_(unit_ids))).scalars()
    )


@router.get("/families", response_model=list[FamilyOut])
def families(
    db: Session = Depends(get_db),
    _actor: AppUser = Depends(require_permission("catalog.view")),
):
    return WmsCatalogService.families(db)


@router.post("/families", response_model=FamilyOut, status_code=201)
def create_family(
    payload: FamilyIn,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("catalog.manage")),
):
    result = WmsCatalogService.create_family(db, actor.id, _allowed_warehouses(db, actor), payload)
    db.commit()
    return result


@router.get("/items/search", response_model=list[ItemSearchOut])
def search_items(
    query: str | None = Query(default=None, max_length=120),
    family_id: uuid.UUID | None = None,
    warehouse_id: uuid.UUID | None = None,
    location_id: uuid.UUID | None = None,
    equipment_id: uuid.UUID | None = None,
    active_only: bool = True,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("catalog.view")),
):
    return WmsCatalogService.search_items(
        db,
        warehouse_ids=_allowed_warehouses(db, actor),
        query=query,
        family_id=family_id,
        warehouse_id=warehouse_id,
        location_id=location_id,
        equipment_id=equipment_id,
        active_only=active_only,
        limit=limit,
        offset=offset,
    )


@router.get("/items/{item_id}", response_model=ItemDetailOut)
def item_detail(
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("catalog.view")),
):
    return WmsCatalogService.item_detail(db, item_id, _allowed_warehouses(db, actor))


@router.get("/items/{item_id}/photo")
def item_photo(
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    _actor: AppUser = Depends(require_permission("catalog.view")),
):
    path, media_type = WmsCatalogService.photo_path(db, item_id)
    return FileResponse(path, media_type=media_type)


@router.post("/items/{item_id}/photo", response_model=PhotoOut, status_code=201)
def upload_item_photo(
    item_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("catalog.manage")),
):
    result = WmsCatalogService.save_photo(
        db,
        actor.id,
        item_id,
        file_name=file.filename or "fotografia",
        content_type=file.content_type or "application/octet-stream",
        content=file.file.read(),
    )
    db.commit()
    return result


@router.get("/locations", response_model=list[LocationOut])
def locations(
    warehouse_id: uuid.UUID | None = None,
    location_type: str | None = Query(default=None, pattern=r"^(RECEIPT|STANDARD|QUARANTINE|DISPATCH|TRANSIT|SCRAP)$"),
    status: str | None = Query(default=None, pattern=r"^(ACTIVE|BLOCKED|INACTIVE)$"),
    query: str | None = Query(default=None, max_length=120),
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("warehouse.location.view")),
):
    return WmsCatalogService.locations(
        db,
        warehouse_ids=_allowed_warehouses(db, actor),
        warehouse_id=warehouse_id,
        location_type=location_type,
        status=status,
        query=query,
    )


@router.post("/locations", response_model=LocationOut, status_code=201)
def create_location(
    payload: LocationIn,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("warehouse.location.manage")),
):
    result = WmsCatalogService.create_location(db, actor.id, _allowed_warehouses(db, actor), payload)
    db.commit()
    return result


@router.get("/locations/{location_id}", response_model=LocationDetailOut)
def location_detail(
    location_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("warehouse.location.view")),
):
    return WmsCatalogService.location_detail(db, location_id, _allowed_warehouses(db, actor))
