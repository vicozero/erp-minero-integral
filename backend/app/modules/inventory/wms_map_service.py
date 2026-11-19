"""Servicio del almacén virtual: proyección 2D, coordenadas y QR.

El mapa guarda metadatos del fondo, nunca existencias. Los nodos se derivan de
``mdm.storage_location`` en cada consulta (UB-010), por lo que el plano no es
una fuente de verdad y las imágenes se presentan siempre como referenciales.
"""

from __future__ import annotations

import hashlib
import io
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import NoReturn

import qrcode
from fastapi import HTTPException, status
from qrcode.image.svg import SvgPathImage
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.audit.service import AuditService
from app.modules.inventory.models import LocationMap
from app.modules.inventory.wms_map_schemas import MAP_LABEL, LocationMapMetadataIn
from app.modules.inventory.wms_service import WmsCatalogService, build_location_path
from app.modules.master_data.models import StorageLocation
from app.modules.master_data.schemas import LocationCoordinatesIn
from app.modules.organization.models import MiningUnit, Warehouse

_BACKGROUND_SUFFIXES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
_BACKGROUND_MAGIC = {
    "image/jpeg": b"\xff\xd8\xff",
    "image/png": b"\x89PNG\r\n\x1a\n",
    "image/webp": b"RIFF",
}
_BACKGROUND_MAX_BYTES = 5 * 1024 * 1024


def _fail(detail: str, code: int = status.HTTP_409_CONFLICT) -> NoReturn:
    raise HTTPException(status_code=code, detail=detail)


def _warehouse(
    db: Session,
    warehouse_id: uuid.UUID,
    warehouse_ids: list[uuid.UUID] | None,
) -> Warehouse:
    stmt = select(Warehouse).where(Warehouse.id == warehouse_id)
    if warehouse_ids is not None:
        if not warehouse_ids or warehouse_id not in warehouse_ids:
            _fail("Almacén inexistente o fuera de su alcance.", status.HTTP_404_NOT_FOUND)
    warehouse = db.execute(stmt).scalar_one_or_none()
    if warehouse is None:
        _fail("Almacén inexistente.", status.HTTP_404_NOT_FOUND)
    return warehouse


def _to_version_out(row: LocationMap) -> dict:
    return {
        "id": row.id,
        "warehouse_id": row.warehouse_id,
        "map_version": row.map_version,
        "label": row.label,
        "background_url": (
            f"/api/v1/wms/maps/{row.warehouse_id}/background?version={row.map_version}"
            if row.background_path
            else None
        ),
        "background_name": row.background_name,
        "background_sha256": row.background_sha256,
        "is_exact": row.is_exact,
        "width": row.width,
        "height": row.height,
        "is_active": row.is_active,
        "notes": row.notes,
    }


def _active_map(db: Session, warehouse_id: uuid.UUID, actor_id: uuid.UUID | None = None) -> LocationMap:
    row = db.execute(
        select(LocationMap).where(
            LocationMap.warehouse_id == warehouse_id,
            LocationMap.is_active.is_(True),
        )
    ).scalar_one_or_none()
    if row is not None:
        return row
    # Almacenes creados con posterioridad a la migración reciben su versión 1.
    row = LocationMap(
        warehouse_id=warehouse_id,
        map_version=1,
        label=MAP_LABEL,
        is_active=True,
        created_by=actor_id,
    )
    db.add(row)
    db.flush()
    return row


def _new_version(
    db: Session,
    actor_id: uuid.UUID,
    warehouse_id: uuid.UUID,
    metadata: LocationMapMetadataIn,
    *,
    background_path: str | None = None,
    background_name: str | None = None,
    background_sha256: str | None = None,
) -> LocationMap:
    current = _active_map(db, warehouse_id, actor_id)
    current.is_active = False
    current.updated_at = datetime.now(timezone.utc)
    current.updated_by = actor_id
    current.version += 1
    new = LocationMap(
        warehouse_id=warehouse_id,
        map_version=current.map_version + 1,
        label=metadata.label,
        width=metadata.width,
        height=metadata.height,
        notes=metadata.notes,
        background_path=background_path,
        background_name=background_name,
        background_sha256=background_sha256,
        is_active=True,
        created_by=actor_id,
    )
    db.add(new)
    db.flush()
    return new


class WmsMapService:
    """Consultas y escrituras del plano, sin afectar saldos de inventario."""

    @staticmethod
    def active_map(
        db: Session,
        warehouse_id: uuid.UUID,
        warehouse_ids: list[uuid.UUID] | None,
    ) -> dict:
        _warehouse(db, warehouse_id, warehouse_ids)
        row = _active_map(db, warehouse_id)
        return _to_version_out(row)

    @staticmethod
    def map_detail(
        db: Session,
        warehouse_id: uuid.UUID,
        warehouse_ids: list[uuid.UUID] | None,
    ) -> dict:
        _warehouse(db, warehouse_id, warehouse_ids)
        row = _active_map(db, warehouse_id)
        locations = WmsCatalogService.locations(
            db, warehouse_ids=[warehouse_id], warehouse_id=warehouse_id
        )
        nodes = [
            {
                "id": item["id"],
                "code": item["code"],
                "parent_id": item["parent_id"],
                "hierarchy_path": item["hierarchy_path"],
                "zone": item["zone"],
                "aisle": item["aisle"],
                "rack": item["rack"],
                "level": item["level"],
                "position": item["position"],
                "location_type": item["location_type"],
                "status": item["status"],
                "coord_x": item["coord_x"],
                "coord_y": item["coord_y"],
                "capacity_qty": item["capacity_qty"],
                "occupied_qty": item["occupied_qty"],
                "item_count": item["item_count"],
            }
            for item in locations
        ]
        return {**_to_version_out(row), "nodes": nodes}

    @staticmethod
    def versions(
        db: Session,
        warehouse_id: uuid.UUID,
        warehouse_ids: list[uuid.UUID] | None,
    ) -> list[dict]:
        _warehouse(db, warehouse_id, warehouse_ids)
        rows = db.execute(
            select(LocationMap)
            .where(LocationMap.warehouse_id == warehouse_id)
            .order_by(LocationMap.map_version.desc())
        ).scalars()
        return [_to_version_out(row) for row in rows]

    @staticmethod
    def create_version(
        db: Session,
        actor_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        warehouse_ids: list[uuid.UUID] | None,
        metadata: LocationMapMetadataIn,
    ) -> dict:
        _warehouse(db, warehouse_id, warehouse_ids)
        previous = _active_map(db, warehouse_id, actor_id)
        row = _new_version(db, actor_id, warehouse_id, metadata)
        AuditService.record(
            db,
            action="WMS_MAP_VERSION_CREATED",
            entity_type="LocationMap",
            entity_id=row.id,
            actor_id=actor_id,
            before={"warehouse_id": str(warehouse_id), "map_version": previous.map_version},
            after={"map_version": row.map_version, "label": row.label, "is_exact": False},
        )
        return _to_version_out(row)

    @staticmethod
    def upload_background(
        db: Session,
        actor_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        warehouse_ids: list[uuid.UUID] | None,
        metadata: LocationMapMetadataIn,
        *,
        file_name: str,
        content_type: str,
        content: bytes,
    ) -> dict:
        _warehouse(db, warehouse_id, warehouse_ids)
        mime = content_type.lower().split(";")[0].strip()
        suffix = Path(file_name).suffix.lower()
        if mime not in _BACKGROUND_SUFFIXES.values() or _BACKGROUND_SUFFIXES.get(suffix) != mime:
            _fail("Solo se admiten fondos JPG, PNG o WEBP.", status.HTTP_422_UNPROCESSABLE_ENTITY)
        if not content or len(content) > _BACKGROUND_MAX_BYTES or not content.startswith(_BACKGROUND_MAGIC[mime]):
            _fail(
                "El fondo está vacío, excede 5 MB o no corresponde al formato.",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        directory = settings.ATTACHMENT_STORAGE_DIR.parent / "location_maps" / str(warehouse_id)
        directory.mkdir(parents=True, exist_ok=True)
        stored_name = f"{uuid.uuid4().hex}{suffix}"
        path = directory / stored_name
        digest = hashlib.sha256(content).hexdigest()
        with path.open("xb") as handle:
            handle.write(content)
        try:
            stored_path = path.relative_to(settings.ATTACHMENT_STORAGE_DIR.parent).as_posix()
            row = _new_version(
                db,
                actor_id,
                warehouse_id,
                metadata,
                background_path=stored_path,
                background_name=Path(file_name).name[:180],
                background_sha256=digest,
            )
            AuditService.record(
                db,
                action="WMS_MAP_BACKGROUND_UPLOAD",
                entity_type="LocationMap",
                entity_id=row.id,
                actor_id=actor_id,
                after={
                    "map_version": row.map_version,
                    "sha256": digest,
                    "size_bytes": len(content),
                    "is_exact": False,
                    "label": row.label,
                },
            )
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return _to_version_out(row)

    @staticmethod
    def background_path(
        db: Session,
        warehouse_id: uuid.UUID,
        version: int | None,
        warehouse_ids: list[uuid.UUID] | None,
    ) -> tuple[Path, str]:
        _warehouse(db, warehouse_id, warehouse_ids)
        stmt = select(LocationMap).where(LocationMap.warehouse_id == warehouse_id)
        if version is None:
            stmt = stmt.where(LocationMap.is_active.is_(True))
        else:
            stmt = stmt.where(LocationMap.map_version == version)
        row = db.execute(stmt.order_by(LocationMap.map_version.desc())).scalar_one_or_none()
        if row is None or not row.background_path:
            _fail("La versión solicitada no tiene fondo registrado.", status.HTTP_404_NOT_FOUND)
        base = settings.ATTACHMENT_STORAGE_DIR.parent.resolve()
        candidate = (base / row.background_path).resolve()
        if not candidate.is_relative_to(base) or ".." in Path(row.background_path).parts:
            _fail("Ruta de fondo no válida.", status.HTTP_422_UNPROCESSABLE_ENTITY)
        if not candidate.is_file():
            _fail("El fondo no está disponible.", status.HTTP_404_NOT_FOUND)
        mime = _BACKGROUND_SUFFIXES.get(candidate.suffix.lower(), "application/octet-stream")
        return candidate, mime

    @staticmethod
    def update_coordinates(
        db: Session,
        actor_id: uuid.UUID,
        location_id: uuid.UUID,
        warehouse_ids: list[uuid.UUID] | None,
        payload: LocationCoordinatesIn,
    ) -> dict:
        location = db.get(StorageLocation, location_id)
        if location is None:
            _fail("Ubicación inexistente.", status.HTTP_404_NOT_FOUND)
        _warehouse(db, location.warehouse_id, warehouse_ids)
        active = _active_map(db, location.warehouse_id)
        if payload.coord_x > active.width or payload.coord_y > active.height:
            _fail(
                f"La coordenada debe estar dentro del plano activo ({active.width} × {active.height}).",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        before = {"coord_x": str(location.coord_x), "coord_y": str(location.coord_y)}
        location.coord_x = payload.coord_x
        location.coord_y = payload.coord_y
        location.updated_at = datetime.now(timezone.utc)
        location.updated_by = actor_id
        location.version += 1
        db.flush()
        AuditService.record(
            db,
            action="WMS_LOCATION_COORDINATES_UPDATED",
            entity_type="StorageLocation",
            entity_id=location.id,
            actor_id=actor_id,
            before=before,
            after={"coord_x": str(payload.coord_x), "coord_y": str(payload.coord_y)},
        )
        return {
            "id": location.id,
            "coord_x": location.coord_x,
            "coord_y": location.coord_y,
            "version": location.version,
        }

    @staticmethod
    def lookup_qr(
        db: Session,
        qr_token: str,
        warehouse_ids: list[uuid.UUID] | None,
    ) -> dict:
        row = db.execute(
            select(StorageLocation, Warehouse.code.label("warehouse_code"), MiningUnit.code.label("unit_code"))
            .join(Warehouse, Warehouse.id == StorageLocation.warehouse_id)
            .outerjoin(MiningUnit, MiningUnit.id == Warehouse.mining_unit_id)
            .where(StorageLocation.qr_token == qr_token)
        ).one_or_none()
        if row is None:
            _fail("Token QR no reconocido.", status.HTTP_404_NOT_FOUND)
        location, warehouse_code, unit_code = row
        _warehouse(db, location.warehouse_id, warehouse_ids)
        return {
            "id": location.id,
            "warehouse_id": location.warehouse_id,
            "warehouse_code": warehouse_code,
            "code": location.code,
            "hierarchy_path": build_location_path(unit_code, warehouse_code, location),
            "location_type": location.location_type,
            "status": location.status,
            "coord_x": location.coord_x,
            "coord_y": location.coord_y,
            "qr_token": location.qr_token,
        }

    @staticmethod
    def qr_svg(qr_token: str) -> bytes:
        """Genera un QR real en SVG; el token es opaco y no contiene secretos."""
        qr = qrcode.QRCode(
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=6,
            border=2,
        )
        qr.add_data(qr_token)
        qr.make(fit=True)
        image = qr.make_image(image_factory=SvgPathImage)
        buffer = io.BytesIO()
        image.save(buffer)
        return buffer.getvalue()
