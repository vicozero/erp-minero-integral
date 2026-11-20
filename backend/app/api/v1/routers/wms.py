from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.v1.deps import require_permission
from app.db.session import get_db
from app.modules.identity.models import AppUser
from app.modules.identity.service import IdentityService
from app.modules.inventory.wms_dashboard_schemas import (
    LocationInventoryOut,
    MaterialSearchResultOut,
    WarehouseDashboardOut,
)
from app.modules.inventory.wms_dashboard_service import WmsDashboardService
from app.modules.inventory.wms_map_schemas import (
    LocationCoordinatesOut,
    LocationLookupOut,
    LocationMapMetadataIn,
    LocationMapOut,
    LocationMapVersionOut,
    QrTokenOut,
)
from app.modules.inventory.wms_map_service import WmsMapService
from app.modules.inventory.wms_service import WmsCatalogService
from app.modules.master_data.schemas import (
    FamilyIn,
    FamilyOut,
    ItemDetailOut,
    ItemSearchOut,
    LocationCoordinatesIn,
    LocationDetailOut,
    LocationIn,
    LocationOut,
    PhotoOut,
)

router = APIRouter(prefix="/wms", tags=["WMS · Catálogo y ubicaciones"])


def _allowed_warehouses(db: Session, actor: AppUser) -> list[uuid.UUID] | None:
    """Adaptador local: la regla vive en ``IdentityService`` y es compartida."""
    return IdentityService.allowed_warehouse_ids(db, actor.id)


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


@router.get("/locations/lookup", response_model=LocationLookupOut)
def lookup_qr(
    qr_token: str = Query(min_length=8, max_length=160),
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("warehouse.location.view")),
):
    return WmsMapService.lookup_qr(db, qr_token, _allowed_warehouses(db, actor))


@router.patch("/locations/{location_id}/coordinates", response_model=LocationCoordinatesOut)
def update_coordinates(
    location_id: uuid.UUID,
    payload: LocationCoordinatesIn,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("warehouse.map.manage")),
):
    result = WmsMapService.update_coordinates(db, actor.id, location_id, _allowed_warehouses(db, actor), payload)
    db.commit()
    return result


@router.get("/locations/{location_id}/qr", response_model=QrTokenOut)
def location_qr(
    location_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("warehouse.location.view")),
):
    detail = WmsCatalogService.location_detail(db, location_id, _allowed_warehouses(db, actor))
    return {
        "location_id": location_id,
        "qr_token": detail["qr_token"],
        "svg_url": f"/api/v1/wms/locations/{location_id}/qr.svg",
        "lookup_url": f"/api/v1/wms/locations/lookup?qr_token={detail['qr_token']}",
    }


@router.get("/locations/{location_id}/qr.svg")
def location_qr_svg(
    location_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("warehouse.location.view")),
):
    detail = WmsCatalogService.location_detail(db, location_id, _allowed_warehouses(db, actor))
    return Response(
        content=WmsMapService.qr_svg(detail["qr_token"]),
        media_type="image/svg+xml",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/locations/{location_id}", response_model=LocationDetailOut)
def location_detail(
    location_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("warehouse.location.view")),
):
    return WmsCatalogService.location_detail(db, location_id, _allowed_warehouses(db, actor))


# --- Almacén virtual interactivo: inventario, dashboard y búsqueda ---------


@router.get("/locations/{location_id}/inventory", response_model=LocationInventoryOut)
def location_inventory(
    location_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("warehouse.location.view")),
):
    can_view_cost = IdentityService.has_permission(db, actor.id, "warehouse.stock.view")
    return WmsDashboardService.location_inventory(
        db, location_id, _allowed_warehouses(db, actor), can_view_cost=can_view_cost
    )


@router.get("/dashboard", response_model=WarehouseDashboardOut)
def dashboard(
    warehouse_id: uuid.UUID | None = None,
    zone: str | None = Query(default=None, max_length=20),
    family_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("warehouse.map.view")),
):
    return WmsDashboardService.dashboard(
        db,
        _allowed_warehouses(db, actor),
        warehouse_id=warehouse_id,
        zone=zone,
        family_id=family_id,
    )


@router.get("/materials/search", response_model=MaterialSearchResultOut)
def material_search(
    query: str = Query(min_length=2, max_length=120),
    warehouse_id: uuid.UUID | None = None,
    zone: str | None = Query(default=None, max_length=20),
    family_id: uuid.UUID | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("catalog.view")),
):
    return WmsDashboardService.material_search(
        db,
        _allowed_warehouses(db, actor),
        query=query,
        warehouse_id=warehouse_id,
        zone=zone,
        family_id=family_id,
        limit=limit,
    )


# --- Almacén virtual: mapa 2D versionado ----------------------------------


@router.get("/maps/{warehouse_id}", response_model=LocationMapOut)
def active_map(
    warehouse_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("warehouse.map.view")),
):
    return WmsMapService.map_detail(db, warehouse_id, _allowed_warehouses(db, actor))


@router.get("/maps/{warehouse_id}/versions", response_model=list[LocationMapVersionOut])
def map_versions(
    warehouse_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("warehouse.map.view")),
):
    return WmsMapService.versions(db, warehouse_id, _allowed_warehouses(db, actor))


@router.patch("/maps/{warehouse_id}", response_model=LocationMapVersionOut)
def update_map(
    warehouse_id: uuid.UUID,
    payload: LocationMapMetadataIn,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("warehouse.map.manage")),
):
    result = WmsMapService.create_version(db, actor.id, warehouse_id, _allowed_warehouses(db, actor), payload)
    db.commit()
    return result


@router.post("/maps/{warehouse_id}/background", response_model=LocationMapVersionOut, status_code=201)
def upload_map_background(
    warehouse_id: uuid.UUID,
    file: UploadFile = File(...),
    label: str = Form(default="Referencial · no es plano exacto"),
    width: Decimal = Form(default=Decimal("1000")),
    height: Decimal = Form(default=Decimal("600")),
    notes: str | None = Form(default=None),
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("warehouse.map.manage")),
):
    metadata = LocationMapMetadataIn(label=label, width=width, height=height, notes=notes)
    result = WmsMapService.upload_background(
        db,
        actor.id,
        warehouse_id,
        _allowed_warehouses(db, actor),
        metadata,
        file_name=file.filename or "fondo",
        content_type=file.content_type or "application/octet-stream",
        content=file.file.read(),
    )
    db.commit()
    return result


@router.get("/maps/{warehouse_id}/background")
def map_background(
    warehouse_id: uuid.UUID,
    version: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("warehouse.map.view")),
):
    path, media_type = WmsMapService.background_path(
        db, warehouse_id, version, _allowed_warehouses(db, actor)
    )
    return FileResponse(path, media_type=media_type)
