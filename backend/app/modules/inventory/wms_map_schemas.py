"""Esquemas del almacén virtual (proyección 2D y mapas versionados)."""

from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.master_data.schemas import ORMModel

MAP_LABEL = "Referencial · no es plano exacto"


class LocationMapNode(ORMModel):
    """Nodo dibujable, derivado de ``mdm.storage_location`` en cada consulta."""

    id: uuid.UUID
    code: str
    parent_id: uuid.UUID | None
    hierarchy_path: str
    zone: str | None
    aisle: str | None
    rack: str | None
    level: str | None
    position: str | None
    location_type: str
    status: str
    coord_x: Decimal | None
    coord_y: Decimal | None
    capacity_qty: Decimal
    occupied_qty: Decimal
    item_count: int


class LocationMapVersionOut(ORMModel):
    id: uuid.UUID
    warehouse_id: uuid.UUID
    map_version: int
    label: str
    background_url: str | None
    background_name: str | None
    background_sha256: str | None
    is_exact: bool
    width: Decimal
    height: Decimal
    is_active: bool
    notes: str | None


class LocationMapOut(LocationMapVersionOut):
    nodes: list[LocationMapNode]


class LocationMapMetadataIn(BaseModel):
    label: str = Field(default=MAP_LABEL, min_length=5, max_length=120)
    width: Decimal = Field(default=Decimal("1000"), gt=0)
    height: Decimal = Field(default=Decimal("600"), gt=0)
    notes: str | None = Field(default=None, max_length=500)


class LocationCoordinatesOut(ORMModel):
    id: uuid.UUID
    coord_x: Decimal
    coord_y: Decimal
    version: int


class LocationLookupOut(ORMModel):
    id: uuid.UUID
    warehouse_id: uuid.UUID
    warehouse_code: str
    code: str
    hierarchy_path: str
    location_type: str
    status: str
    coord_x: Decimal | None
    coord_y: Decimal | None
    qr_token: str


class QrTokenOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    location_id: uuid.UUID
    qr_token: str
    svg_url: str
    lookup_url: str
