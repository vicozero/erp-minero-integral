from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import NoReturn

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.audit.service import AuditService
from app.modules.costing.models import CostLayer
from app.modules.documentation.models import DocumentRegistry
from app.modules.inventory.service import InventoryService
from app.modules.master_data.models import Item, Supplier
from app.modules.organization.models import Warehouse
from app.modules.purchasing.models import (
    GoodsReceipt,
    GoodsReceiptLine,
    PurchaseOrder,
    PurchaseOrderLine,
)
from app.modules.requisitions.models import Requisition, RequisitionLine
from app.shared.constants import APPROVABLE_STATUSES
from app.shared.events import emit
from app.shared.idempotency import acquire, complete
from app.shared.numbering import attach_entity, next_document_number, record_document_event


class PurchasingError(HTTPException):
    pass


def _fail(detail: str, code: int = status.HTTP_409_CONFLICT) -> NoReturn:
    raise PurchasingError(status_code=code, detail=detail)


class PurchasingService:
    @staticmethod
    def line_purchased_qty(db: Session, requisition_line_id: uuid.UUID) -> Decimal:
        # Las órdenes canceladas o cerradas no deben seguir descontando el
        # faltante de la requisición original.
        value = db.execute(
            select(func.coalesce(func.sum(PurchaseOrderLine.ordered_qty - PurchaseOrderLine.cancelled_qty), 0))
            .join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderLine.purchase_order_id)
            .where(
                PurchaseOrderLine.requisition_line_id == requisition_line_id,
                PurchaseOrder.status.notin_(("CANCELLED", "CLOSED")),
            )
        ).scalar_one()
        return Decimal(str(value))

    @staticmethod
    def line_received_qty(db: Session, requisition_line_id: uuid.UUID) -> Decimal:
        value = db.execute(
            select(func.coalesce(func.sum(GoodsReceiptLine.quantity), 0))
            .join(
                PurchaseOrderLine,
                PurchaseOrderLine.id == GoodsReceiptLine.purchase_order_line_id,
            )
            .where(PurchaseOrderLine.requisition_line_id == requisition_line_id)
        ).scalar_one()
        return Decimal(str(value))

    @staticmethod
    def create_from_shortages(db: Session, actor_id: uuid.UUID, payload) -> PurchaseOrder:
        req = db.get(Requisition, payload.requisition_id)
        if req is None:
            _fail("Requisición inexistente.", status.HTTP_404_NOT_FOUND)
        if req.status not in APPROVABLE_STATUSES:
            _fail("Solo se pueden comprar partidas de requisiciones autorizadas.")
        supplier = db.get(Supplier, payload.supplier_id)
        warehouse = db.get(Warehouse, payload.warehouse_id)
        if supplier is None or warehouse is None:
            _fail("Proveedor o almacén inexistente.", status.HTTP_404_NOT_FOUND)
        if supplier.company_id != req.company_id:
            _fail("El proveedor pertenece a otra compañía.", status.HTTP_422_UNPROCESSABLE_ENTITY)
        if warehouse.company_id != req.company_id:
            _fail("El almacén pertenece a otra compañía.", status.HTTP_422_UNPROCESSABLE_ENTITY)
        if warehouse.mining_unit_id is not None and warehouse.mining_unit_id != req.mining_unit_id:
            _fail("El almacén pertenece a otra unidad minera.", status.HTTP_422_UNPROCESSABLE_ENTITY)

        idem = payload.idempotency_key or (
            f"po:{payload.requisition_id}:{payload.supplier_id}:{payload.warehouse_id}"
        )
        record, created = acquire(
            db,
            idem,
            operation="purchasing.create_from_shortages",
            entity_type="PurchaseOrder",
        )
        if not created:
            if record.entity_id is not None:
                existing = db.get(PurchaseOrder, record.entity_id)
                if existing is not None:
                    return existing
            _fail("La clave de idempotencia ya fue utilizada por otra operación.")

        lines = list(
            db.execute(
                select(RequisitionLine)
                .where(RequisitionLine.requisition_id == req.id)
                .order_by(RequisitionLine.line_no)
                .with_for_update()
            ).scalars()
        )
        selected: list[tuple[RequisitionLine, Decimal]] = []
        for line in lines:
            if line.item_id is None or line.status == "CANCELLED":
                continue
            delivered = InventoryService.line_delivered_qty(db, line.id)
            reserved = InventoryService.line_reserved_qty(db, line.id)
            purchased = PurchasingService.line_purchased_qty(db, line.id)
            shortage = line.authorised_qty - delivered - reserved - purchased
            if shortage > Decimal("0"):
                selected.append((line, shortage))
        if not selected:
            _fail("No hay faltantes para generar orden de compra.")

        registry, po_no = next_document_number(
            db,
            "OC",
            req.company_id,
            series="LAG",
            mining_unit_id=req.mining_unit_id,
        )
        po = PurchaseOrder(
            document_no=po_no,
            document_registry_id=registry.id,
            company_id=req.company_id,
            mining_unit_id=req.mining_unit_id,
            supplier_id=supplier.id,
            warehouse_id=warehouse.id,
            buyer_id=actor_id,
            requisition_id=req.id,
            status="DRAFT",
            notes=payload.notes,
        )
        db.add(po)
        db.flush()
        for index, (line, shortage) in enumerate(selected, start=1):
            item = db.get(Item, line.item_id)
            po_line = PurchaseOrderLine(
                purchase_order_id=po.id,
                line_no=index,
                requisition_line_id=line.id,
                item_id=line.item_id,
                uom_id=line.uom_id,
                ordered_qty=shortage,
                received_qty=Decimal("0"),
                cancelled_qty=Decimal("0"),
                unit_price=item.standard_cost if item else Decimal("0"),
            )
            db.add(po_line)
        db.flush()
        attach_entity(db, registry, "PurchaseOrder", po.id)
        record_document_event(db, registry, "PURCHASE_ORDER_CREATED", None, "DRAFT", actor_id)
        AuditService.record(
            db,
            action="PURCHASE_ORDER_CREATE",
            entity_type="PurchaseOrder",
            entity_id=po.id,
            actor_id=actor_id,
            after={"document_no": po_no, "requisition_id": str(req.id), "lines": len(selected)},
        )
        emit(db, "PurchaseOrder", po.id, "PURCHASE_ORDER_CREATED", {"document_no": po_no})
        complete(db, record, po.id)
        return po

    @staticmethod
    def approve(db: Session, actor_id: uuid.UUID, purchase_order_id: uuid.UUID) -> PurchaseOrder:
        po = db.execute(
            select(PurchaseOrder).where(PurchaseOrder.id == purchase_order_id).with_for_update()
        ).scalar_one_or_none()
        if po is None:
            _fail("Orden de compra inexistente.", status.HTTP_404_NOT_FOUND)
        if po.status != "DRAFT":
            _fail("Solo se puede aprobar una orden en borrador.")
        po.status = "APPROVED"
        po.approved_at = datetime.now(timezone.utc)
        registry = db.get(DocumentRegistry, po.document_registry_id)
        if registry is not None:
            record_document_event(db, registry, "PURCHASE_ORDER_APPROVED", "DRAFT", "APPROVED", actor_id)
        AuditService.record(
            db,
            action="PURCHASE_ORDER_APPROVE",
            entity_type="PurchaseOrder",
            entity_id=po.id,
            actor_id=actor_id,
            after={"status": "APPROVED"},
        )
        emit(db, "PurchaseOrder", po.id, "PURCHASE_ORDER_APPROVED", {})
        return po

    @staticmethod
    def cancel(db: Session, actor_id: uuid.UUID, purchase_order_id: uuid.UUID, reason: str) -> PurchaseOrder:
        po = db.execute(
            select(PurchaseOrder).where(PurchaseOrder.id == purchase_order_id).with_for_update()
        ).scalar_one_or_none()
        if po is None:
            _fail("Orden de compra inexistente.", status.HTTP_404_NOT_FOUND)
        if po.status in ("RECEIVED", "PARTIALLY_RECEIVED", "CANCELLED", "CLOSED"):
            _fail("La orden ya fue recibida, cancelada o cerrada.")
        old_status = po.status
        po.status = "CANCELLED"
        po.notes = f"{po.notes or ''}\nCancelación: {reason}".strip()
        for line in db.execute(
            select(PurchaseOrderLine).where(PurchaseOrderLine.purchase_order_id == po.id).with_for_update()
        ).scalars():
            line.cancelled_qty = line.ordered_qty - line.received_qty
        registry = db.get(DocumentRegistry, po.document_registry_id)
        if registry is not None:
            record_document_event(db, registry, "PURCHASE_ORDER_CANCELLED", old_status, "CANCELLED", actor_id, {"reason": reason})
        AuditService.record(
            db,
            action="PURCHASE_ORDER_CANCEL",
            entity_type="PurchaseOrder",
            entity_id=po.id,
            actor_id=actor_id,
            before={"status": old_status},
            after={"status": "CANCELLED"},
            detail=reason,
        )
        emit(db, "PurchaseOrder", po.id, "PURCHASE_ORDER_CANCELLED", {"reason": reason})
        return po

    @staticmethod
    def receive(db: Session, actor_id: uuid.UUID, purchase_order_id: uuid.UUID, payload) -> GoodsReceipt:
        record, created = acquire(
            db,
            payload.idempotency_key,
            operation="purchasing.receive",
            entity_type="GoodsReceipt",
        )
        if not created:
            if record.entity_id is not None:
                existing = db.get(GoodsReceipt, record.entity_id)
                if existing is not None:
                    return existing
            existing_receipt = db.execute(
                select(GoodsReceipt).where(GoodsReceipt.idempotency_key == payload.idempotency_key)
            ).scalar_one_or_none()
            if existing_receipt is not None:
                return existing_receipt
            _fail("La clave de idempotencia ya fue utilizada por otra operación.")

        po = db.execute(
            select(PurchaseOrder).where(PurchaseOrder.id == purchase_order_id).with_for_update()
        ).scalar_one_or_none()
        if po is None:
            _fail("Orden de compra inexistente.", status.HTTP_404_NOT_FOUND)
        if po.status not in ("APPROVED", "SENT", "PARTIALLY_RECEIVED"):
            _fail("La orden no está disponible para recepción.")

        requested: dict[uuid.UUID, Decimal] = {}
        for item in payload.lines:
            requested[item.purchase_order_line_id] = (
                requested.get(item.purchase_order_line_id, Decimal("0")) + item.quantity
            )

        po_lines = list(
            db.execute(
                select(PurchaseOrderLine).where(
                    PurchaseOrderLine.purchase_order_id == po.id,
                    PurchaseOrderLine.id.in_(requested.keys()),
                ).with_for_update()
            ).scalars()
        )
        if len(po_lines) != len(requested):
            _fail("Una o más partidas no pertenecen a la orden.")
        for line in po_lines:
            pending = line.ordered_qty - line.received_qty - line.cancelled_qty
            if requested[line.id] > pending:
                _fail(f"Sobre-recepción en partida {line.line_no}.")

        registry, grn_no = next_document_number(
            db,
            "GRN",
            po.company_id,
            series="LAG",
            mining_unit_id=po.mining_unit_id,
        )
        grn = GoodsReceipt(
            document_no=grn_no,
            document_registry_id=registry.id,
            purchase_order_id=po.id,
            warehouse_id=po.warehouse_id,
            received_by=actor_id,
            idempotency_key=payload.idempotency_key,
        )
        db.add(grn)
        db.flush()

        for line in po_lines:
            qty = requested[line.id]
            movement_key = f"{payload.idempotency_key}:{line.id}"
            movement = InventoryService.receive_stock(
                db,
                actor_id=actor_id,
                company_id=po.company_id,
                mining_unit_id=po.mining_unit_id,
                warehouse_id=po.warehouse_id,
                item_id=line.item_id,
                quantity=qty,
                idempotency_key=movement_key,
                source_document_type="GOODS_RECEIPT",
                source_document_id=grn.id,
                purchase_order_line_id=line.id,
            )
            line.received_qty += qty
            db.add(
                GoodsReceiptLine(
                    goods_receipt_id=grn.id,
                    purchase_order_line_id=line.id,
                    quantity=qty,
                    stock_movement_id=movement.id,
                )
            )
            db.add(
                CostLayer(
                    item_id=line.item_id,
                    warehouse_id=po.warehouse_id,
                    quantity=qty,
                    remaining_qty=qty,
                    unit_cost=line.unit_price,
                    source_document_type="GOODS_RECEIPT",
                    source_document_id=grn.id,
                )
            )

        all_lines = list(
            db.execute(select(PurchaseOrderLine).where(PurchaseOrderLine.purchase_order_id == po.id)).scalars()
        )
        if all(line.received_qty + line.cancelled_qty >= line.ordered_qty for line in all_lines):
            po.status = "RECEIVED"
        else:
            po.status = "PARTIALLY_RECEIVED"

        attach_entity(db, registry, "GoodsReceipt", grn.id)
        record_document_event(db, registry, "GOODS_RECEIPT_POSTED", None, "POSTED", actor_id)
        AuditService.record(
            db,
            action="PURCHASE_RECEIVE",
            entity_type="GoodsReceipt",
            entity_id=grn.id,
            actor_id=actor_id,
            after={"document_no": grn_no, "purchase_order_id": str(po.id), "lines": len(po_lines)},
        )
        emit(db, "GoodsReceipt", grn.id, "GOODS_RECEIPT_POSTED", {"document_no": grn_no})
        complete(db, record, grn.id)
        return grn
