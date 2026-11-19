"""Servicio de catálogo y ubicaciones del Lote A del WMS.

Expone una proyección operativa para catálogo, ubicaciones, lotes y series.
No modifica saldos: las escrituras de inventario siguen gobernadas por
``InventoryService`` y sus reglas transaccionales.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import NoReturn

from fastapi import HTTPException, status
from sqlalchemy import ColumnElement, and_, false, func, literal, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.audit.service import AuditService
from app.modules.inventory.models import StockBalance, StockMovement
from app.modules.master_data.models import (
    Item,
    ItemCrossReference,
    ItemFamily,
    ItemSupplier,
    LocationRestriction,
    Lot,
    Serial,
    StorageLocation,
    Supplier,
    Uom,
)
from app.modules.master_data.schemas import FamilyIn, LocationIn
from app.modules.organization.models import Company, Warehouse
from app.modules.purchasing.models import PurchaseOrder, PurchaseOrderLine
from app.modules.requisitions.models import Requisition, RequisitionLine

_PHOTO_SUFFIXES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
_PHOTO_MAGIC = {
    "image/jpeg": b"\xff\xd8\xff",
    "image/png": b"\x89PNG\r\n\x1a\n",
    "image/webp": b"RIFF",
}
_PHOTO_MAX_BYTES = 2 * 1024 * 1024


def _fail(detail: str, code: int = status.HTTP_409_CONFLICT) -> NoReturn:
    raise HTTPException(status_code=code, detail=detail)


def _dec(value: object | None) -> Decimal:
    return Decimal(str(value or 0))


def _warehouse_condition(warehouse_ids: list[uuid.UUID] | None, column):
    if warehouse_ids is None:
        return None
    if not warehouse_ids:
        return false()
    return column.in_(warehouse_ids)


def _default_company_id(db: Session, warehouse_ids: list[uuid.UUID] | None = None) -> uuid.UUID:
    if warehouse_ids:
        company_id = db.execute(
            select(Warehouse.company_id).where(Warehouse.id == warehouse_ids[0])
        ).scalar_one_or_none()
        if company_id is not None:
            return company_id
    company_id = db.execute(select(Company.id).order_by(Company.created_at).limit(1)).scalar_one_or_none()
    if company_id is None:
        _fail("No existe una empresa configurada.", status.HTTP_404_NOT_FOUND)
    return company_id


class WmsCatalogService:
    """Consultas de catálogo y altas controladas, sin afectar existencias."""

    @staticmethod
    def families(db: Session) -> list[dict]:
        rows = db.execute(select(ItemFamily).order_by(ItemFamily.code)).scalars()
        return [
            {
                "id": row.id,
                "code": row.code,
                "name": row.name,
                "parent_id": row.parent_id,
                "is_active": row.is_active,
            }
            for row in rows
        ]

    @staticmethod
    def create_family(
        db: Session,
        actor_id: uuid.UUID,
        warehouse_ids: list[uuid.UUID] | None,
        payload: FamilyIn,
    ) -> dict:
        company_id = _default_company_id(db, warehouse_ids)
        code = payload.code.strip().upper()
        exists = db.execute(
            select(ItemFamily.id).where(ItemFamily.company_id == company_id, ItemFamily.code == code)
        ).scalar_one_or_none()
        if exists is not None:
            _fail("Ya existe una familia con ese código.")
        if payload.parent_id is not None and db.get(ItemFamily, payload.parent_id) is None:
            _fail("La familia padre no existe.", status.HTTP_404_NOT_FOUND)
        family = ItemFamily(
            company_id=company_id,
            parent_id=payload.parent_id,
            code=code,
            name=payload.name.strip(),
            is_active=payload.is_active,
            created_by=actor_id,
        )
        db.add(family)
        db.flush()
        AuditService.record(
            db,
            action="WMS_FAMILY_CREATED",
            entity_type="ItemFamily",
            entity_id=family.id,
            actor_id=actor_id,
            after={"code": family.code, "name": family.name},
        )
        return {
            "id": family.id,
            "code": family.code,
            "name": family.name,
            "parent_id": family.parent_id,
            "is_active": family.is_active,
        }

    @staticmethod
    def search_items(
        db: Session,
        *,
        warehouse_ids: list[uuid.UUID] | None,
        query: str | None = None,
        family_id: uuid.UUID | None = None,
        warehouse_id: uuid.UUID | None = None,
        location_id: uuid.UUID | None = None,
        equipment_id: uuid.UUID | None = None,
        active_only: bool = True,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        if warehouse_ids is not None and not warehouse_ids:
            return []
        limit = max(1, min(limit, 200))
        offset = max(0, offset)

        stock_conditions = [StockBalance.item_id == Item.id]
        allowed = _warehouse_condition(warehouse_ids, StockBalance.warehouse_id)
        if allowed is not None:
            stock_conditions.append(allowed)
        if warehouse_id is not None:
            stock_conditions.append(StockBalance.warehouse_id == warehouse_id)
        if location_id is not None:
            stock_conditions.append(StockBalance.location_ref_id == location_id)

        columns = (
            Item.id.label("id"),
            Item.code.label("code"),
            Item.description.label("description"),
            Item.family_id.label("family_id"),
            ItemFamily.name.label("family_name"),
            Item.manufacturer.label("manufacturer"),
            Item.manufacturer_part_no.label("manufacturer_part_no"),
            Item.barcode.label("barcode"),
            Item.uom_id.label("uom_id"),
            Uom.code.label("uom_code"),
            Item.standard_cost.label("standard_cost"),
            Item.lot_tracked.label("lot_tracked"),
            Item.serial_tracked.label("serial_tracked"),
            Item.is_consumable.label("is_consumable"),
            Item.is_returnable.label("is_returnable"),
            Item.is_tool.label("is_tool"),
            Item.is_active.label("is_active"),
            func.coalesce(func.sum(StockBalance.on_hand_qty), 0).label("on_hand_qty"),
            func.coalesce(func.sum(StockBalance.reserved_qty), 0).label("reserved_qty"),
            func.count(func.distinct(StockBalance.location_ref_id)).label("location_count"),
        )
        stmt = (
            select(*columns)
            .outerjoin(Uom, Uom.id == Item.uom_id)
            .outerjoin(ItemFamily, ItemFamily.id == Item.family_id)
            .outerjoin(StockBalance, and_(*stock_conditions))
            .group_by(*columns[:-3])
        )

        filters: list[ColumnElement[bool]] = []
        if active_only:
            filters.append(Item.is_active.is_(True))
        if family_id is not None:
            filters.append(Item.family_id == family_id)
        needle = query.strip() if query else ""
        if needle:
            pattern = f"%{needle}%"
            filters.append(
                or_(
                    Item.code.ilike(pattern),
                    Item.description.ilike(pattern),
                    Item.manufacturer.ilike(pattern),
                    Item.manufacturer_part_no.ilike(pattern),
                    Item.barcode.ilike(pattern),
                )
            )
        if equipment_id is not None:
            equipment_items = (
                select(RequisitionLine.item_id)
                .join(Requisition, Requisition.id == RequisitionLine.requisition_id)
                .where(Requisition.equipment_id == equipment_id)
            )
            filters.append(Item.id.in_(equipment_items))
        if filters:
            stmt = stmt.where(*filters)
        stmt = stmt.order_by(Item.code).limit(limit).offset(offset)

        result = []
        for row in db.execute(stmt):
            item = row._mapping
            on_hand = _dec(item["on_hand_qty"])
            reserved = _dec(item["reserved_qty"])
            result.append(
                {
                    "id": item["id"],
                    "code": item["code"],
                    "description": item["description"],
                    "family_id": item["family_id"],
                    "family_name": item["family_name"],
                    "manufacturer": item["manufacturer"],
                    "manufacturer_part_no": item["manufacturer_part_no"],
                    "barcode": item["barcode"],
                    "uom_id": item["uom_id"],
                    "uom_code": item["uom_code"],
                    "standard_cost": item["standard_cost"],
                    "lot_tracked": item["lot_tracked"],
                    "serial_tracked": item["serial_tracked"],
                    "is_consumable": item["is_consumable"],
                    "is_returnable": item["is_returnable"],
                    "is_tool": item["is_tool"],
                    "is_active": item["is_active"],
                    "on_hand_qty": on_hand,
                    "reserved_qty": reserved,
                    "available_qty": on_hand - reserved,
                    "location_count": int(item["location_count"] or 0),
                }
            )
        return result

    @staticmethod
    def item_detail(db: Session, item_id: uuid.UUID, warehouse_ids: list[uuid.UUID] | None) -> dict:
        row = db.execute(
            select(Item, Uom.code.label("uom_code"), ItemFamily.name.label("family_name"), Supplier.name.label("supplier_name"))
            .outerjoin(Uom, Uom.id == Item.uom_id)
            .outerjoin(ItemFamily, ItemFamily.id == Item.family_id)
            .outerjoin(Supplier, Supplier.id == Item.default_supplier_id)
            .where(Item.id == item_id)
        ).one_or_none()
        if row is None:
            _fail("Artículo inexistente.", status.HTTP_404_NOT_FOUND)
        item, uom_code, family_name, supplier_name = row

        totals_stmt = select(
            func.coalesce(func.sum(StockBalance.on_hand_qty), 0),
            func.coalesce(func.sum(StockBalance.reserved_qty), 0),
        ).where(StockBalance.item_id == item_id)
        allowed = _warehouse_condition(warehouse_ids, StockBalance.warehouse_id)
        if allowed is not None:
            totals_stmt = totals_stmt.where(allowed)
        totals = db.execute(totals_stmt).one()
        on_hand, reserved = _dec(totals[0]), _dec(totals[1])

        location_stmt = (
            select(StockBalance, StorageLocation, Warehouse.code, Lot.lot_number)
            .join(StorageLocation, StorageLocation.id == StockBalance.location_ref_id)
            .join(Warehouse, Warehouse.id == StockBalance.warehouse_id)
            .outerjoin(Lot, Lot.id == StockBalance.lot_ref_id)
            .where(StockBalance.item_id == item_id)
            .order_by(Warehouse.code, StorageLocation.code)
        )
        if allowed is not None:
            location_stmt = location_stmt.where(allowed)
        locations = [
            {
                "location_id": location.id,
                "location_code": location.code,
                "warehouse_code": warehouse_code,
                "zone": location.zone,
                "aisle": location.aisle,
                "lot_number": lot_number,
                "on_hand_qty": balance.on_hand_qty,
                "reserved_qty": balance.reserved_qty,
                "available_qty": balance.on_hand_qty - balance.reserved_qty,
            }
            for balance, location, warehouse_code, lot_number in db.execute(location_stmt)
        ]

        lots = [
            {
                "id": lot.id,
                "lot_number": lot.lot_number,
                "status": lot.status,
                "manufactured_at": lot.manufactured_at,
                "expiry_date": lot.expiry_date,
            }
            for lot in db.execute(select(Lot).where(Lot.item_id == item_id).order_by(Lot.lot_number)).scalars()
        ]
        serials = [
            {
                "id": serial.id,
                "serial_number": serial.serial_number,
                "status": serial.status,
                "lot_id": serial.lot_id,
                "current_location_id": serial.current_location_id,
            }
            for serial in db.execute(select(Serial).where(Serial.item_id == item_id).order_by(Serial.serial_number)).scalars()
        ]
        xrefs = [
            {
                "id": ref.id,
                "reference_type": ref.reference_type,
                "reference_code": ref.reference_code,
                "equivalent_item_id": ref.equivalent_item_id,
                "authorised": ref.authorised,
            }
            for ref in db.execute(
                select(ItemCrossReference).where(ItemCrossReference.item_id == item_id).order_by(ItemCrossReference.reference_code)
            ).scalars()
        ]
        suppliers = [
            {
                "id": relation.id,
                "supplier_id": supplier.id,
                "supplier_name": supplier.name,
                "supplier_part_number": relation.supplier_part_number,
                "lead_time_days": relation.lead_time_days,
                "min_order_qty": relation.min_order_qty,
                "preferred": relation.preferred,
                "last_unit_cost": relation.last_unit_cost,
                "currency": relation.currency,
            }
            for relation, supplier in db.execute(
                select(ItemSupplier, Supplier)
                .join(Supplier, Supplier.id == ItemSupplier.supplier_id)
                .where(ItemSupplier.item_id == item_id)
                .order_by(Supplier.name)
            )
        ]
        movements = [
            {
                "id": movement.id,
                "movement_no": movement.movement_no,
                "movement_type": movement.movement_type,
                "direction": movement.direction,
                "quantity": movement.quantity,
                "balance_after_qty": movement.balance_after_qty,
                "posted_at": movement.posted_at,
                "source_document_type": movement.source_document_type,
            }
            for movement in db.execute(
                select(StockMovement)
                .where(StockMovement.item_id == item_id)
                .order_by(StockMovement.posted_at.desc())
                .limit(20)
            ).scalars()
        ]

        related: list[dict] = []
        for document_no, doc_type, doc_status, occurred_at in db.execute(
            select(Requisition.document_no, literal("REQ"), Requisition.status, Requisition.created_at)
            .join(RequisitionLine, RequisitionLine.requisition_id == Requisition.id)
            .where(RequisitionLine.item_id == item_id)
            .order_by(Requisition.created_at.desc())
            .limit(10)
        ):
            related.append(
                {"document_no": document_no, "document_type": doc_type, "status": doc_status, "occurred_at": occurred_at}
            )
        for document_no, doc_type, doc_status, occurred_at in db.execute(
            select(PurchaseOrder.document_no, literal("OC"), PurchaseOrder.status, PurchaseOrder.created_at)
            .join(PurchaseOrderLine, PurchaseOrderLine.purchase_order_id == PurchaseOrder.id)
            .where(PurchaseOrderLine.item_id == item_id)
            .order_by(PurchaseOrder.created_at.desc())
            .limit(10)
        ):
            related.append(
                {"document_no": document_no, "document_type": doc_type, "status": doc_status, "occurred_at": occurred_at}
            )
        related.sort(key=lambda entry: entry["occurred_at"], reverse=True)

        return {
            "id": item.id,
            "code": item.code,
            "description": item.description,
            "family_id": item.family_id,
            "family_name": family_name,
            "manufacturer": item.manufacturer,
            "manufacturer_part_no": item.manufacturer_part_no,
            "barcode": item.barcode,
            "uom_id": item.uom_id,
            "uom_code": uom_code,
            "standard_cost": item.standard_cost,
            "lot_tracked": item.lot_tracked,
            "serial_tracked": item.serial_tracked,
            "is_consumable": item.is_consumable,
            "is_returnable": item.is_returnable,
            "is_tool": item.is_tool,
            "is_active": item.is_active,
            "on_hand_qty": on_hand,
            "reserved_qty": reserved,
            "available_qty": on_hand - reserved,
            "location_count": len(locations),
            "image_url": f"/api/v1/wms/items/{item.id}/photo" if item.image_path else None,
            "supplier_name": supplier_name,
            "default_supplier_id": item.default_supplier_id,
            "reorder_point": item.reorder_point,
            "safety_stock": item.safety_stock,
            "max_stock": item.max_stock,
            "weight_kg": item.weight_kg,
            "volume_m3": item.volume_m3,
            "storage_temperature_min": item.storage_temperature_min,
            "storage_temperature_max": item.storage_temperature_max,
            "locations": locations,
            "lots": lots,
            "serials": serials,
            "cross_references": xrefs,
            "suppliers": suppliers,
            "movements": movements,
            "related_documents": related[:10],
        }

    @staticmethod
    def locations(
        db: Session,
        *,
        warehouse_ids: list[uuid.UUID] | None,
        warehouse_id: uuid.UUID | None = None,
        location_type: str | None = None,
        status: str | None = None,
        query: str | None = None,
    ) -> list[dict]:
        if warehouse_ids is not None and not warehouse_ids:
            return []
        occupancy = (
            select(
                StockBalance.location_ref_id.label("location_id"),
                func.coalesce(func.sum(StockBalance.on_hand_qty), 0).label("occupied_qty"),
                func.count(func.distinct(StockBalance.item_id)).label("item_count"),
            )
            .where(StockBalance.location_ref_id.is_not(None))
            .group_by(StockBalance.location_ref_id)
            .subquery()
        )
        stmt = (
            select(
                StorageLocation,
                Warehouse.code.label("warehouse_code"),
                func.coalesce(occupancy.c.occupied_qty, 0).label("occupied_qty"),
                func.coalesce(occupancy.c.item_count, 0).label("item_count"),
            )
            .join(Warehouse, Warehouse.id == StorageLocation.warehouse_id)
            .outerjoin(occupancy, occupancy.c.location_id == StorageLocation.id)
        )
        allowed = _warehouse_condition(warehouse_ids, StorageLocation.warehouse_id)
        if allowed is not None:
            stmt = stmt.where(allowed)
        if warehouse_id is not None:
            stmt = stmt.where(StorageLocation.warehouse_id == warehouse_id)
        if location_type:
            stmt = stmt.where(StorageLocation.location_type == location_type)
        if status:
            stmt = stmt.where(StorageLocation.status == status)
        needle = query.strip() if query else ""
        if needle:
            pattern = f"%{needle}%"
            stmt = stmt.where(
                or_(
                    StorageLocation.code.ilike(pattern),
                    Warehouse.code.ilike(pattern),
                    StorageLocation.zone.ilike(pattern),
                    StorageLocation.aisle.ilike(pattern),
                    StorageLocation.rack.ilike(pattern),
                )
            )
        stmt = stmt.order_by(Warehouse.code, StorageLocation.code)
        return [
            {
                "id": location.id,
                "warehouse_id": location.warehouse_id,
                "warehouse_code": warehouse_code,
                "code": location.code,
                "zone": location.zone,
                "aisle": location.aisle,
                "rack": location.rack,
                "level": location.level,
                "position": location.position,
                "location_type": location.location_type,
                "qr_token": location.qr_token,
                "capacity_qty": location.capacity_qty,
                "status": location.status,
                "is_pickable": location.is_pickable,
                "is_receivable": location.is_receivable,
                "occupied_qty": _dec(occupied_qty),
                "item_count": int(item_count or 0),
            }
            for location, warehouse_code, occupied_qty, item_count in db.execute(stmt)
        ]

    @staticmethod
    def location_detail(db: Session, location_id: uuid.UUID, warehouse_ids: list[uuid.UUID] | None) -> dict:
        base = next((row for row in WmsCatalogService.locations(db, warehouse_ids=warehouse_ids) if row["id"] == location_id), None)
        if base is None:
            _fail("Ubicación inexistente o fuera de su alcance.", status.HTTP_404_NOT_FOUND)
        restrictions = [
            {
                "item_family_id": row.item_family_id,
                "item_id": row.item_id,
                "max_qty": row.max_qty,
                "allows_lot_mix": row.allows_lot_mix,
                "allows_serial_mix": row.allows_serial_mix,
            }
            for row in db.execute(
                select(LocationRestriction).where(LocationRestriction.location_id == location_id)
            ).scalars()
        ]
        items = [
            {
                "location_id": row.location_id,
                "location_code": row.location_code,
                "warehouse_code": row.warehouse_code,
                "zone": row.zone,
                "aisle": row.aisle,
                "lot_number": row.lot_number,
                "on_hand_qty": row.on_hand_qty,
                "reserved_qty": row.reserved_qty,
                "available_qty": row.available_qty,
            }
            for row in WmsCatalogService._stock_at_location(db, location_id)
        ]
        return {**base, "restrictions": restrictions, "items": items}

    @staticmethod
    def _stock_at_location(db: Session, location_id: uuid.UUID) -> list:
        return list(
            db.execute(
                select(
                    StorageLocation.id.label("location_id"),
                    StorageLocation.code.label("location_code"),
                    Warehouse.code.label("warehouse_code"),
                    StorageLocation.zone,
                    StorageLocation.aisle,
                    Lot.lot_number,
                    StockBalance.on_hand_qty,
                    StockBalance.reserved_qty,
                    (StockBalance.on_hand_qty - StockBalance.reserved_qty).label("available_qty"),
                )
                .join(StockBalance, StockBalance.location_ref_id == StorageLocation.id)
                .join(Warehouse, Warehouse.id == StockBalance.warehouse_id)
                .outerjoin(Lot, Lot.id == StockBalance.lot_ref_id)
                .where(StorageLocation.id == location_id)
                .order_by(StockBalance.item_id)
            )
        )

    @staticmethod
    def create_location(
        db: Session,
        actor_id: uuid.UUID,
        warehouse_ids: list[uuid.UUID] | None,
        payload: LocationIn,
    ) -> dict:
        allowed = _warehouse_condition(warehouse_ids, Warehouse.id)
        if allowed is not None:
            warehouse = db.execute(
                select(Warehouse).where(Warehouse.id == payload.warehouse_id, allowed)
            ).scalar_one_or_none()
        else:
            warehouse = db.get(Warehouse, payload.warehouse_id)
        if warehouse is None:
            _fail("Almacén inexistente o fuera de su alcance.", status.HTTP_404_NOT_FOUND)
        code = payload.code.strip().upper()
        exists = db.execute(
            select(StorageLocation.id).where(
                StorageLocation.warehouse_id == payload.warehouse_id, StorageLocation.code == code
            )
        ).scalar_one_or_none()
        if exists is not None:
            _fail("Ya existe una ubicación con ese código en el almacén.")
        location = StorageLocation(
            warehouse_id=payload.warehouse_id,
            code=code,
            zone=payload.zone.strip().upper() if payload.zone else None,
            aisle=payload.aisle.strip().upper() if payload.aisle else None,
            rack=payload.rack.strip().upper() if payload.rack else None,
            level=payload.level.strip().upper() if payload.level else None,
            position=payload.position.strip().upper() if payload.position else None,
            location_type=payload.location_type,
            qr_token=f"WMS:{warehouse.code}:{code}",
            capacity_qty=payload.capacity_qty,
            status=payload.status,
            is_pickable=payload.is_pickable,
            is_receivable=payload.is_receivable,
            created_by=actor_id,
        )
        db.add(location)
        db.flush()
        AuditService.record(
            db,
            action="WMS_LOCATION_CREATED",
            entity_type="StorageLocation",
            entity_id=location.id,
            actor_id=actor_id,
            after={"warehouse": warehouse.code, "code": location.code, "qr_token": location.qr_token},
        )
        base = WmsCatalogService.locations(
            db, warehouse_ids=[payload.warehouse_id], warehouse_id=payload.warehouse_id
        )
        return next(row for row in base if row["id"] == location.id)

    @staticmethod
    def save_photo(
        db: Session,
        actor_id: uuid.UUID,
        item_id: uuid.UUID,
        *,
        file_name: str,
        content_type: str,
        content: bytes,
    ) -> dict:
        """Guarda una fotografía validada fuera de la base y registra su SHA-256."""
        item = db.get(Item, item_id)
        if item is None:
            _fail("Artículo inexistente.", status.HTTP_404_NOT_FOUND)
        mime = content_type.lower().split(";")[0].strip()
        suffix = Path(file_name).suffix.lower()
        if mime not in _PHOTO_SUFFIXES.values() or _PHOTO_SUFFIXES.get(suffix) != mime:
            _fail("Solo se admiten fotografías JPG, PNG o WEBP.", status.HTTP_422_UNPROCESSABLE_ENTITY)
        if not content or len(content) > _PHOTO_MAX_BYTES or not content.startswith(_PHOTO_MAGIC[mime]):
            _fail("La fotografía está vacía, excede 2 MB o no corresponde al formato.", status.HTTP_422_UNPROCESSABLE_ENTITY)

        directory = settings.ATTACHMENT_STORAGE_DIR.parent / "item_photos" / str(item_id)
        directory.mkdir(parents=True, exist_ok=True)
        stored_name = f"{uuid.uuid4().hex}{suffix}"
        path = directory / stored_name
        digest = hashlib.sha256(content).hexdigest()
        with path.open("xb") as handle:
            handle.write(content)
        try:
            previous_path = WmsCatalogService._photo_path(item.image_path)
            item.image_path = f"item_photos/{item_id}/{stored_name}"
            item.image_sha256 = digest
            item.updated_by = actor_id
            item.updated_at = datetime.now(timezone.utc)
            item.version += 1
            db.flush()
            AuditService.record(
                db,
                action="WMS_ITEM_PHOTO_UPLOAD",
                entity_type="Item",
                entity_id=item.id,
                actor_id=actor_id,
                after={"sha256": digest, "size_bytes": len(content)},
            )
        except Exception:
            path.unlink(missing_ok=True)
            raise
        if previous_path is not None:
            previous_path.unlink(missing_ok=True)
        return {
            "item_id": item.id,
            "image_path": item.image_path,
            "image_sha256": item.image_sha256,
            "image_url": f"/api/v1/wms/items/{item.id}/photo",
        }

    @staticmethod
    def _photo_path(image_path: str | None) -> Path | None:
        if not image_path:
            return None
        base = (settings.ATTACHMENT_STORAGE_DIR.parent).resolve()
        candidate = (base / image_path).resolve()
        if not candidate.is_relative_to(base) or ".." in Path(image_path).parts:
            _fail("Ruta de fotografía no válida.", status.HTTP_422_UNPROCESSABLE_ENTITY)
        return candidate

    @staticmethod
    def photo_path(db: Session, item_id: uuid.UUID) -> tuple[Path, str]:
        item = db.get(Item, item_id)
        if item is None or not item.image_path:
            _fail("El artículo no tiene fotografía registrada.", status.HTTP_404_NOT_FOUND)
        path = WmsCatalogService._photo_path(item.image_path)
        if path is None or not path.is_file():
            _fail("La fotografía no está disponible.", status.HTTP_404_NOT_FOUND)
        mime = _PHOTO_SUFFIXES.get(path.suffix.lower(), "application/octet-stream")
        return path, mime
