"""Servicio del diseñador profesional de planos 2D/3D del Lote 7.

Reglas inviolables:

* Un solo array de elementos es la escena compartida por 2D y 3D.
* Existe como máximo un borrador por almacén; las versiones publicadas nunca
  se sobrescriben y la activa sólo cambia al publicar explícitamente.
* La concurrencia es optimista mediante ``revision``.
* La geometría nunca modifica ``inv.stock_balance``; las posiciones WMS se
  crean únicamente con ``WmsCatalogService.create_location``.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, NoReturn

from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.audit.service import AuditService
from app.modules.inventory.models import FloorPlan
from app.modules.inventory.wms_designer_schemas import (
    MAX_ELEMENTS,
    FloorPlanOut,
    FloorPlanWorkspaceOut,
    PlanElementIn,
    PlanImportIn,
    PlanImportPreviewOut,
    PlanPayloadIn,
    RackBlueprintIn,
    RackBlueprintOut,
)
from app.modules.inventory.wms_map_schemas import MAP_LABEL
from app.modules.inventory.wms_service import WmsCatalogService
from app.modules.master_data.models import StorageLocation
from app.modules.master_data.schemas import LocationIn
from app.modules.organization.models import Warehouse


def _fail(message: str, code: int = status.HTTP_422_UNPROCESSABLE_CONTENT) -> NoReturn:
    raise HTTPException(status_code=code, detail=message)


def _warehouse(
    db: Session, warehouse_id: uuid.UUID, warehouse_ids: list[uuid.UUID] | None
) -> Warehouse:
    if warehouse_ids is not None and warehouse_id not in warehouse_ids:
        _fail("Almacén inexistente o fuera de su alcance.", status.HTTP_404_NOT_FOUND)
    warehouse = db.get(Warehouse, warehouse_id)
    if warehouse is None:
        _fail("Almacén inexistente.", status.HTTP_404_NOT_FOUND)
    return warehouse


def _assert_location_ids_in_warehouse(
    db: Session, warehouse_id: uuid.UUID, location_ids: set[uuid.UUID]
) -> None:
    if not location_ids:
        return
    found = set(
        db.execute(
            select(StorageLocation.id).where(
                StorageLocation.warehouse_id == warehouse_id,
                StorageLocation.id.in_(location_ids),
            )
        ).scalars()
    )
    if found != location_ids:
        _fail("Una o más ubicaciones WMS no pertenecen a este almacén.")


def _decimal(value: Any) -> float:
    if value is None:
        return 0.0
    return float(Decimal(str(value)))


def _element_dict(element: PlanElementIn) -> dict[str, Any]:
    data = element.model_dump(mode="json", exclude_none=True)
    for field in ("x", "y", "width", "height", "depth", "rotation"):
        if field in data and data[field] is not None:
            data[field] = _decimal(data[field])
    if element.wms_location_id is None:
        data.pop("wms_location_id", None)
    return data


def _plan_dict(row: FloorPlan, can_edit: bool, can_publish: bool) -> dict[str, Any]:
    return {
        "id": row.id,
        "warehouse_id": row.warehouse_id,
        "plan_version": row.plan_version,
        "status": row.status,
        "label": row.label,
        "width": _decimal(row.width),
        "height": _decimal(row.height),
        "grid_size": _decimal(row.grid_size),
        "scale_label": row.scale_label,
        "dimensions_verified": row.dimensions_verified,
        "elements": row.elements or [],
        "location_refs": row.location_refs or [],
        "revision": row.revision,
        "is_active": row.is_active,
        "notes": row.notes,
        "can_edit": can_edit and row.status == "DRAFT",
        "can_publish": can_publish and row.status == "DRAFT",
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "published_at": row.published_at,
    }


def _to_out(row: FloorPlan, can_edit: bool, can_publish: bool) -> FloorPlanOut:
    return FloorPlanOut.model_validate(_plan_dict(row, can_edit, can_publish))


def _default_payload() -> PlanPayloadIn:
    return PlanPayloadIn(
        label=MAP_LABEL,
        width=Decimal("1000"),
        height=Decimal("600"),
        grid_size=Decimal("20"),
        revision=1,
    )


def _apply_payload(
    row: FloorPlan, payload: PlanPayloadIn, actor_id: uuid.UUID, *, increment_revision: bool = True
) -> dict:
    before = _plan_dict(row, True, True)
    row.label = payload.label
    row.width = payload.width
    row.height = payload.height
    row.grid_size = payload.grid_size
    row.scale_label = payload.scale_label
    row.dimensions_verified = payload.dimensions_verified
    row.elements = [_element_dict(element) for element in payload.elements]
    refs: dict[str, dict[str, Any]] = {}
    for element in row.elements:
        if element.get("wms_location_id"):
            refs[str(element["wms_location_id"])] = {
                "location_id": element["wms_location_id"],
                "element_id": element["id"],
                "code": element.get("code"),
            }
    row.location_refs = list(refs.values())
    row.notes = payload.notes
    if increment_revision:
        row.revision += 1
    row.updated_at = datetime.now(timezone.utc)
    row.updated_by = actor_id
    return before


def _draft_for(db: Session, warehouse_id: uuid.UUID) -> FloorPlan | None:
    """Devuelve el borrador persistido del almacén, nunca una fila pendiente."""

    return db.execute(
        select(FloorPlan)
        .where(FloorPlan.warehouse_id == warehouse_id, FloorPlan.status == "DRAFT")
        .order_by(FloorPlan.created_at.desc(), FloorPlan.id.desc())
    ).scalars().first()


def _active_for(db: Session, warehouse_id: uuid.UUID) -> FloorPlan | None:
    return db.execute(
        select(FloorPlan).where(
            FloorPlan.warehouse_id == warehouse_id,
            FloorPlan.is_active.is_(True),
        )
    ).scalar_one_or_none()


def _build_draft(
    actor_id: uuid.UUID, warehouse_id: uuid.UUID, active: FloorPlan | None
) -> FloorPlan:
    payload = (
        PlanPayloadIn.model_validate(
            {
                "label": source.label,
                "width": source.width,
                "height": source.height,
                "grid_size": source.grid_size,
                "scale_label": source.scale_label,
                "dimensions_verified": source.dimensions_verified,
                "elements": source.elements,
                "revision": 1,
                "notes": source.notes,
            }
        )
        if (source := active) is not None
        else _default_payload()
    )
    draft = FloorPlan(
        warehouse_id=warehouse_id,
        plan_version=1 if active is None else active.plan_version + 1,
        status="DRAFT",
        label=MAP_LABEL,
        width=Decimal("1000"),
        height=Decimal("600"),
        grid_size=Decimal("20"),
        dimensions_verified=False,
        elements=[],
        location_refs=[],
        created_by=actor_id,
        revision=1,
    )
    _apply_payload(draft, payload, actor_id, increment_revision=False)
    return draft


class WmsDesignerService:
    @staticmethod
    def workspace(
        db: Session,
        actor_id: uuid.UUID,
        warehouse_ids: list[uuid.UUID] | None,
        warehouse_id: uuid.UUID,
        *,
        can_edit: bool = False,
        can_publish: bool = False,
    ) -> FloorPlanWorkspaceOut:
        _warehouse(db, warehouse_id, warehouse_ids)
        # GET es de sólo lectura: crear el borrador aquí provocaba filas no
        # confirmadas, identificadores distintos por llamada y 409 al guardar.
        active = _active_for(db, warehouse_id)
        draft = _draft_for(db, warehouse_id)
        versions = list(
            db.execute(
                select(FloorPlan)
                .where(
                    FloorPlan.warehouse_id == warehouse_id,
                    FloorPlan.status == "PUBLISHED",
                )
                .order_by(FloorPlan.plan_version.desc())
            ).scalars()
        )
        return FloorPlanWorkspaceOut(
            warehouse_id=warehouse_id,
            active=_to_out(active, can_edit, can_publish) if active is not None else None,
            draft=_to_out(draft, can_edit, can_publish) if draft is not None else None,
            versions=[_to_out(row, can_edit, can_publish) for row in versions],
        )

    @staticmethod
    def ensure_draft(
        db: Session,
        actor_id: uuid.UUID,
        warehouse_ids: list[uuid.UUID] | None,
        warehouse_id: uuid.UUID,
    ) -> FloorPlanOut:
        _warehouse(db, warehouse_id, warehouse_ids)
        draft = _draft_for(db, warehouse_id)
        if draft is None:
            new_draft = _build_draft(actor_id, warehouse_id, _active_for(db, warehouse_id))
            try:
                with db.begin_nested():
                    db.add(new_draft)
                    db.flush()
            except IntegrityError:
                # Otra petición ganó la carrera: el índice parcial garantiza un
                # solo borrador por almacén. Se reutiliza la fila persistida.
                draft = _draft_for(db, warehouse_id)
                if draft is None:
                    _fail("No fue posible crear el borrador del plano.")
            else:
                draft = new_draft
                AuditService.record(
                    db,
                    action="WMS_PLAN_DRAFT_CREATED",
                    entity_type="FloorPlan",
                    entity_id=draft.id,
                    actor_id=actor_id,
                    after={"warehouse_id": str(warehouse_id), "source": "workspace"},
                )
        return _to_out(draft, True, False)

    @staticmethod
    def save_draft(
        db: Session,
        actor_id: uuid.UUID,
        warehouse_ids: list[uuid.UUID] | None,
        warehouse_id: uuid.UUID,
        plan_id: uuid.UUID,
        payload: PlanPayloadIn,
    ) -> FloorPlanOut:
        _warehouse(db, warehouse_id, warehouse_ids)
        draft = db.execute(
            select(FloorPlan)
            .where(FloorPlan.id == plan_id, FloorPlan.warehouse_id == warehouse_id)
            .with_for_update()
        ).scalar_one_or_none()
        if draft is None:
            _fail("Borrador inexistente.", status.HTTP_404_NOT_FOUND)
        if draft.status != "DRAFT":
            _fail("Sólo se puede editar un borrador.")
        if draft.revision != payload.revision:
            _fail(
                "El plano fue modificado por otro usuario. Recargue antes de guardar.",
                status.HTTP_409_CONFLICT,
            )
        _assert_location_ids_in_warehouse(
            db,
            warehouse_id,
            {
                uuid.UUID(str(element.wms_location_id))
                for element in payload.elements
                if element.wms_location_id is not None
            },
        )
        before = _apply_payload(draft, payload, actor_id)
        AuditService.record(
            db,
            action="WMS_PLAN_DRAFT_SAVED",
            entity_type="FloorPlan",
            entity_id=draft.id,
            actor_id=actor_id,
            before={"revision": before["revision"], "elements": len(before["elements"])},
            after={"revision": draft.revision, "elements": len(draft.elements)},
        )
        db.flush()
        return _to_out(draft, True, False)

    @staticmethod
    def publish(
        db: Session,
        actor_id: uuid.UUID,
        warehouse_ids: list[uuid.UUID] | None,
        warehouse_id: uuid.UUID,
        plan_id: uuid.UUID,
        expected_revision: int,
        notes: str | None = None,
        *,
        can_edit: bool = True,
        can_publish: bool = True,
    ) -> FloorPlanWorkspaceOut:
        _warehouse(db, warehouse_id, warehouse_ids)
        draft = db.execute(
            select(FloorPlan)
            .where(FloorPlan.id == plan_id, FloorPlan.warehouse_id == warehouse_id)
            .with_for_update()
        ).scalar_one_or_none()
        if draft is None or draft.status != "DRAFT":
            _fail("Borrador inexistente.", status.HTTP_404_NOT_FOUND)
        if draft.revision != expected_revision:
            _fail(
                "El plano cambió después de la última carga. Recargue antes de publicar.",
                status.HTTP_409_CONFLICT,
            )
        if not draft.elements:
            _fail("No se puede publicar un plano vacío.")
        _assert_location_ids_in_warehouse(
            db,
            warehouse_id,
            {
                uuid.UUID(str(element["wms_location_id"]))
                for element in draft.elements
                if element.get("wms_location_id")
            },
        )
        current = db.execute(
            select(FloorPlan)
            .where(
                FloorPlan.warehouse_id == warehouse_id,
                FloorPlan.is_active.is_(True),
            )
            .with_for_update()
        ).scalar_one_or_none()
        if current is not None:
            current.is_active = False
            current.updated_at = datetime.now(timezone.utc)
            current.updated_by = actor_id
        next_version = int(
            db.execute(
                select(func.coalesce(func.max(FloorPlan.plan_version), 0)).where(
                    FloorPlan.warehouse_id == warehouse_id
                )
            ).scalar_one()
            + 1
        )
        now = datetime.now(timezone.utc)
        published = FloorPlan(
            warehouse_id=warehouse_id,
            plan_version=next_version,
            status="PUBLISHED",
            label=draft.label,
            width=draft.width,
            height=draft.height,
            grid_size=draft.grid_size,
            scale_label=draft.scale_label,
            dimensions_verified=draft.dimensions_verified,
            elements=list(draft.elements),
            location_refs=list(draft.location_refs),
            background_path=draft.background_path,
            background_name=draft.background_name,
            background_sha256=draft.background_sha256,
            revision=1,
            is_active=True,
            notes=notes or draft.notes,
            created_by=actor_id,
            published_at=now,
            published_by=actor_id,
        )
        db.add(published)
        db.flush()
        draft.status = "ARCHIVED"
        draft.is_active = False
        draft.updated_at = now
        draft.updated_by = actor_id
        successor = FloorPlan(
            warehouse_id=warehouse_id,
            plan_version=next_version + 1,
            status="DRAFT",
            label=published.label,
            width=published.width,
            height=published.height,
            grid_size=published.grid_size,
            scale_label=published.scale_label,
            dimensions_verified=published.dimensions_verified,
            elements=list(published.elements),
            location_refs=list(published.location_refs),
            background_path=published.background_path,
            background_name=published.background_name,
            background_sha256=published.background_sha256,
            revision=1,
            is_active=False,
            notes=published.notes,
            created_by=actor_id,
        )
        db.add(successor)
        db.flush()
        AuditService.record(
            db,
            action="WMS_PLAN_PUBLISHED",
            entity_type="FloorPlan",
            entity_id=published.id,
            actor_id=actor_id,
            before={"draft_revision": draft.revision},
            after={"plan_version": published.plan_version, "elements": len(published.elements)},
            detail=notes,
        )
        return WmsDesignerService.workspace(
            db, actor_id, warehouse_ids, warehouse_id, can_edit=can_edit, can_publish=can_publish
        )

    @staticmethod
    def _existing_location_codes(
        db: Session, warehouse_id: uuid.UUID, codes: list[str]
    ) -> dict[str, StorageLocation]:
        if not codes:
            return {}
        rows = db.execute(
            select(StorageLocation).where(
                StorageLocation.warehouse_id == warehouse_id,
                StorageLocation.code.in_(codes),
            )
        ).scalars()
        return {row.code: row for row in rows}

    @staticmethod
    def create_rack(
        db: Session,
        actor_id: uuid.UUID,
        warehouse_ids: list[uuid.UUID] | None,
        warehouse: Warehouse,
        draft: FloorPlan,
        payload: RackBlueprintIn,
        *,
        can_create_locations: bool = False,
    ) -> RackBlueprintOut:
        if draft.status != "DRAFT":
            _fail("El rack debe agregarse a un borrador.")
        if len(draft.elements) + payload.total_positions + 1 > MAX_ELEMENTS:
            _fail("El rack excede el número máximo de elementos del plano.")
        rack_code = payload.code.strip().upper()
        element_slug = "".join(char if char.isalnum() else "-" for char in rack_code.lower())
        while "--" in element_slug:
            element_slug = element_slug.replace("--", "-")
        # Sufijo único: códigos distintos pueden colapsar al mismo slug y
        # provocar IDs duplicados dentro de la escena.
        element_slug = f"{element_slug}-{uuid.uuid4().hex[:8]}"
        if any(
            str(element.get("code", "")).upper() == rack_code
            for element in draft.elements
        ):
            _fail("Ya existe un rack con ese código en el plano.")
        width = _decimal(draft.width)
        height = _decimal(draft.height)
        rack_width = _decimal(payload.width)
        rack_depth = _decimal(payload.depth)
        if _decimal(payload.x) + rack_width > width or _decimal(payload.y) + rack_depth > height:
            _fail("El rack no cabe dentro del lienzo del plano.")
        if payload.capacity_validated and payload.capacity_per_position <= 0:
            _fail("La capacidad validada debe ser mayor que cero.")
        level_height = _decimal(payload.level_height)
        total_height = level_height * payload.levels
        if total_height > 100_000 or _decimal(payload.y) + total_height > height:
            _fail("La altura acumulada de niveles excede el lienzo del plano.")

        codes: list[str] = []
        specs: list[dict[str, Any]] = []
        module_width = rack_width / payload.modules
        slot_width = module_width / payload.positions_per_level
        for module in range(payload.modules):
            for level in range(payload.levels):
                for slot in range(payload.positions_per_level):
                    code = f"{rack_code}-{module + 1:02d}-{level + 1:02d}-{slot + 1:02d}"
                    codes.append(code)
                    specs.append(
                        {
                            "code": code,
                            "module": module + 1,
                            "level": level + 1,
                            "slot": slot + 1,
                            "x": _decimal(payload.x) + module * module_width + slot * slot_width,
                            "y": _decimal(payload.y) + level * level_height,
                            "width": slot_width,
                            "height": level_height,
                        }
                    )
        existing = WmsDesignerService._existing_location_codes(db, warehouse.id, codes)
        linked_ids = {
            str(element.get("wms_location_id"))
            for element in draft.elements
            if element.get("wms_location_id")
        }
        created: list[dict[str, Any]] = []
        elements: list[dict[str, Any]] = []
        skipped = 0
        for spec in specs:
            location = existing.get(spec["code"])
            if location is None and payload.create_locations:
                if not can_create_locations:
                    _fail(
                        "Se requiere permiso para crear ubicaciones WMS.",
                        status.HTTP_403_FORBIDDEN,
                    )
                capacity = (
                    payload.capacity_per_position if payload.capacity_validated else Decimal("0")
                )
                location_out = WmsCatalogService.create_location(
                    db,
                    actor_id,
                    [warehouse.id],
                    LocationIn(
                        warehouse_id=warehouse.id,
                        code=spec["code"],
                        zone=payload.zone,
                        aisle=payload.aisle,
                        rack=payload.rack,
                        level=f"N{spec['level']:02d}",
                        position=f"P{spec['slot']:02d}",
                        coord_x=Decimal(str(round(spec["x"], 4))),
                        coord_y=Decimal(str(round(spec["y"], 4))),
                        location_type=payload.location_type,
                        capacity_qty=capacity,
                        status="ACTIVE",
                    ),
                )
                created.append(location_out)
                location_id: uuid.UUID | None = uuid.UUID(str(location_out["id"]))
            elif location is not None:
                location_id = location.id
            else:
                location_id = None
            if location_id is not None and str(location_id) in linked_ids:
                skipped += 1
                location_id = None
            if location_id is not None:
                linked_ids.add(str(location_id))
            elements.append(
                _element_dict(
                    PlanElementIn(
                        id=f"pos-{element_slug}-{spec['module']:02d}-{spec['level']:02d}-{spec['slot']:02d}",
                        type="POSITION",
                        name=spec["code"],
                        code=spec["code"],
                        x=Decimal(str(round(spec["x"], 4))),
                        y=Decimal(str(round(spec["y"], 4))),
                        width=Decimal(str(round(spec["width"], 4))),
                        height=Decimal(str(round(spec["height"], 4))),
                        depth=Decimal(str(round(rack_depth, 4))),
                        color="#38bdf8",
                        layer="posiciones",
                        wms_location_id=location_id,
                        properties={
                            "module": spec["module"],
                            "level": spec["level"],
                            "slot": spec["slot"],
                            "capacity_validated": payload.capacity_validated,
                        },
                    )
                )
            )
        rack_element = _element_dict(
            PlanElementIn(
                id=f"rack-{element_slug}",
                type="RACK",
                name=payload.name,
                code=rack_code,
                x=payload.x,
                y=payload.y,
                width=payload.width,
                height=payload.depth,
                depth=Decimal(str(round(_decimal(payload.level_height) * payload.levels, 4))),
                rotation=Decimal(payload.orientation),
                color="#2563eb",
                layer="racks",
                properties={
                    "modules": payload.modules,
                    "levels": payload.levels,
                    "positions_per_level": payload.positions_per_level,
                    "total_positions": payload.total_positions,
                    "allowed_materials": [],
                    "qr": f"/api/v1/wms/racks/{rack_code}/qr",
                },
            )
        )
        merged = list(draft.elements) + [rack_element] + elements
        try:
            payload_update = PlanPayloadIn(
                label=draft.label,
                width=draft.width,
                height=draft.height,
                grid_size=draft.grid_size,
                scale_label=draft.scale_label,
                dimensions_verified=draft.dimensions_verified,
                elements=merged,
                revision=draft.revision,
                notes=draft.notes,
            )
        except ValidationError as exc:
            _fail(f"El rack genera una escena inválida: {exc.errors()[0]['msg']}")
        _apply_payload(draft, payload_update, actor_id)
        AuditService.record(
            db,
            action="WMS_PLAN_RACK_CREATED",
            entity_type="FloorPlan",
            entity_id=draft.id,
            actor_id=actor_id,
            after={
                "rack": rack_code,
                "positions": payload.total_positions,
                "locations_created": len(created),
            },
        )
        db.flush()
        warning = (
            "Geometría referencial: no constituye un plano exacto ni modifica inventario."
        )
        if not payload.capacity_validated:
            warning += " La capacidad no está validada y se registró como cero."
        if skipped:
            warning += f" {skipped} ubicaciones ya estaban vinculadas a otra posición."
        return RackBlueprintOut(
            element=rack_element,
            locations=created,
            created_count=len(created),
            total_positions=payload.total_positions,
            warning=warning,
        )

    @staticmethod
    def import_preview(payload: PlanImportIn) -> PlanImportPreviewOut:
        return PlanImportPreviewOut(
            label=payload.label,
            width=payload.width,
            height=payload.height,
            element_count=len(payload.elements),
            linked_location_count=sum(
                1 for element in payload.elements if element.wms_location_id is not None
            ),
            revision=payload.revision,
            warning=(
                "Vista previa únicamente: importar no ejecuta scripts ni modifica inventario. "
                "Las ubicaciones vinculadas se validarán contra el almacén destino."
            ),
        )

    @staticmethod
    def export(row: FloorPlan) -> dict[str, Any]:
        return {
            "schema": "erp-minero.floor-plan.v1",
            "warehouse_id": str(row.warehouse_id),
            "plan_version": row.plan_version,
            "status": row.status,
            "label": row.label,
            "width": _decimal(row.width),
            "height": _decimal(row.height),
            "grid_size": _decimal(row.grid_size),
            "scale_label": row.scale_label,
            "dimensions_verified": row.dimensions_verified,
            "revision": row.revision,
            "elements": row.elements or [],
            "location_refs": [
                {key: str(value) if isinstance(value, uuid.UUID) else value for key, value in ref.items()}
                for ref in row.location_refs or []
            ],
            "warning": "Geometría referencial. No incluye saldos, costos ni datos confidenciales.",
        }
