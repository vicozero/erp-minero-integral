"""Contratos del diseñador de planos 2D/3D del Lote 7.

La geometría es referencial por defecto y nunca transporta existencias. Los
elementos se validan en backend antes de persistirse, incluida la importación
de diseños JSON.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from app.modules.inventory.wms_map_schemas import MAP_LABEL

ELEMENT_TYPES: frozenset[str] = frozenset(
    {
        "WALL",
        "DOOR",
        "AISLE",
        "RACK",
        "SHELF",
        "POSITION",
        "ZONE",
        "RECEIPT",
        "DISPATCH",
        "QUARANTINE",
        "OFFICE",
        "TEXT",
        "LABEL",
        "RECTANGLE",
        "POLYGON",
        "MEASUREMENT",
    }
)

MAX_ELEMENTS = 1000
MAX_PROPERTIES_JSON = 20_000


class PlanElementIn(BaseModel):
    """Un objeto de la escena compartida por 2D y 3D."""

    id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    type: str = Field(max_length=24)
    name: str = Field(default="", max_length=120)
    code: str | None = Field(default=None, max_length=80)
    x: Decimal = Field(ge=-100_000, le=100_000)
    y: Decimal = Field(ge=-100_000, le=100_000)
    width: Decimal = Field(gt=0, le=100_000)
    height: Decimal = Field(gt=0, le=100_000)
    depth: Decimal | None = Field(default=None, gt=0, le=100_000)
    rotation: Decimal = Field(default=Decimal("0"), ge=-360, le=360)
    color: str = Field(default="#64748b", pattern=r"^#[0-9A-Fa-f]{6}$")
    visible: bool = True
    locked: bool = False
    layer: str = Field(default="default", min_length=1, max_length=40)
    z_index: int = Field(default=0, ge=-1000, le=1000)
    dimensions_verified: bool = False
    wms_location_id: uuid.UUID | None = None
    properties: dict[str, Any] = Field(default_factory=dict)

    @field_validator("type")
    @classmethod
    def _known_type(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in ELEMENT_TYPES:
            raise ValueError(f"Tipo de elemento no admitido: {value}")
        return normalized

    @field_validator("layer")
    @classmethod
    def _layer(cls, value: str) -> str:
        return value.strip().lower() or "default"

    @field_validator("properties")
    @classmethod
    def _bounded_properties(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(value) > 40:
            raise ValueError("El elemento admite como máximo 40 propiedades.")
        if len(str(value)) > MAX_PROPERTIES_JSON:
            raise ValueError("Las propiedades del elemento son demasiado grandes.")
        return value


class PlanPayloadIn(BaseModel):
    """Borrador editable; ``revision`` habilita control optimista de concurrencia."""

    label: str = Field(default=MAP_LABEL, min_length=5, max_length=120)
    width: Decimal = Field(gt=0, le=100_000)
    height: Decimal = Field(gt=0, le=100_000)
    grid_size: Decimal = Field(gt=0, le=1_000)
    scale_label: str | None = Field(default=None, max_length=40)
    dimensions_verified: bool = False
    elements: list[PlanElementIn] = Field(default_factory=list)
    revision: int = Field(ge=1)
    notes: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _bounded_scene(self) -> PlanPayloadIn:
        if len(self.elements) > MAX_ELEMENTS:
            raise ValueError(f"El plano admite como máximo {MAX_ELEMENTS} elementos.")
        ids = [element.id for element in self.elements]
        if len(ids) != len(set(ids)):
            raise ValueError("Hay identificadores de elemento repetidos.")
        linked = [e.wms_location_id for e in self.elements if e.wms_location_id is not None]
        if len(linked) != len(set(linked)):
            raise ValueError("Una ubicación WMS no puede vincularse a varias posiciones físicas.")
        for element in self.elements:
            if element.x > self.width or element.y > self.height:
                raise ValueError(
                    f"El elemento {element.id} está fuera del lienzo ({self.width} × {self.height})."
                )
        return self


class PlanImportIn(PlanPayloadIn):
    """Esquema de importación: sin campos de estado, dueño ni existencias."""

    pass


class RackBlueprintIn(BaseModel):
    """Configuración del asistente de racks; no modifica inventario."""

    name: str = Field(min_length=2, max_length=80)
    code: str = Field(min_length=2, max_length=40, pattern=r"^[A-Z0-9][A-Z0-9_.-]*$")
    zone: str = Field(min_length=1, max_length=20)
    aisle: str = Field(min_length=1, max_length=20)
    rack: str = Field(min_length=1, max_length=20)
    modules: int = Field(ge=1, le=50)
    levels: int = Field(ge=1, le=20)
    positions_per_level: int = Field(ge=1, le=20)
    width: Decimal = Field(gt=0, le=10_000)
    depth: Decimal = Field(gt=0, le=10_000)
    level_height: Decimal = Field(gt=0, le=10_000)
    orientation: int = Field(default=0, ge=0, le=270)
    capacity_per_position: Decimal = Field(default=Decimal("0"), ge=0)
    capacity_validated: bool = False
    location_type: str = Field(default="STANDARD", pattern=r"^(STANDARD|RECEIPT|QUARANTINE|DISPATCH)$")
    x: Decimal = Field(ge=0)
    y: Decimal = Field(ge=0)
    create_locations: bool = True

    @property
    def total_positions(self) -> int:
        return self.modules * self.levels * self.positions_per_level

    @field_validator("orientation")
    @classmethod
    def _step_90(cls, value: int) -> int:
        if value % 90 != 0:
            raise ValueError("La orientación debe ser múltiplo de 90 grados.")
        return value

    @model_validator(mode="after")
    def _bounded_rack(self) -> RackBlueprintIn:
        if self.total_positions > 500:
            raise ValueError("Un rack no puede generar más de 500 posiciones.")
        return self


class FloorPlanOut(BaseModel):
    id: uuid.UUID
    warehouse_id: uuid.UUID
    plan_version: int
    status: str
    label: str
    width: Decimal
    height: Decimal
    grid_size: Decimal
    scale_label: str | None
    dimensions_verified: bool
    elements: list[dict[str, Any]]
    location_refs: list[dict[str, Any]]
    revision: int
    is_active: bool
    notes: str | None
    can_edit: bool = False
    can_publish: bool = False
    created_at: datetime
    updated_at: datetime | None
    published_at: datetime | None
    model_config = {"from_attributes": True}


class FloorPlanWorkspaceOut(BaseModel):
    warehouse_id: uuid.UUID
    active: FloorPlanOut | None
    draft: FloorPlanOut | None
    versions: list[FloorPlanOut]


class RackBlueprintOut(BaseModel):
    element: dict[str, Any]
    locations: list[dict[str, Any]]
    created_count: int
    total_positions: int
    warning: str


class PlanImportPreviewOut(BaseModel):
    label: str
    width: Decimal
    height: Decimal
    element_count: int
    linked_location_count: int
    revision: int
    warning: str
