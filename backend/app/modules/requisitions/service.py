from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import NoReturn

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.audit.service import AuditService
from app.modules.costing.models import CostCenter
from app.modules.documentation.models import DocumentEvent, DocumentRegistry
from app.modules.inventory.service import InventoryService
from app.modules.master_data.models import Item, Uom
from app.modules.organization.models import Department, MiningUnit, Warehouse
from app.modules.purchasing.service import PurchasingService
from app.modules.requisitions.models import Requisition, RequisitionLine
from app.modules.workflow.models import ApprovalDecision, ApprovalRequest, ApprovalStep
from app.shared.events import emit
from app.shared.numbering import next_document_number, record_document_event


class RequisitionError(HTTPException):
    pass


def _fail(detail: str, code: int = status.HTTP_409_CONFLICT) -> NoReturn:
    raise RequisitionError(status_code=code, detail=detail)


class RequisitionService:
    @staticmethod
    def create(db: Session, actor_id: uuid.UUID, payload) -> Requisition:
        for model, entity_id, label in (
            (Department, payload.department_id, "Departamento"),
            (CostCenter, payload.cost_center_id, "Centro de costo"),
            (MiningUnit, None, "Unidad minera"),
        ):
            if entity_id is not None and db.get(model, entity_id) is None:
                _fail(f"{label} inexistente.", status.HTTP_404_NOT_FOUND)
        unit = db.execute(select(MiningUnit).where(MiningUnit.code == "LAG_DEMO")).scalar_one_or_none()
        if unit is None:
            _fail("Unidad minera demo no configurada.", status.HTTP_404_NOT_FOUND)
        if payload.warehouse_id is not None and db.get(Warehouse, payload.warehouse_id) is None:
            _fail("Almacén inexistente.", status.HTTP_404_NOT_FOUND)
        if payload.requisition_type == "STOCK" and payload.warehouse_id is None:
            _fail("Las requisiciones de almacén requieren un almacén.", status.HTTP_422_UNPROCESSABLE_ENTITY)

        for line in payload.lines:
            if db.get(Uom, line.uom_id) is None:
                _fail(f"Unidad de medida inexistente en partida {line.description}.")
            if line.item_id is not None and db.get(Item, line.item_id) is None:
                _fail(f"Artículo inexistente en partida {line.description}.")

        registry, document_no = next_document_number(
            db,
            "REQ",
            unit.company_id,
            series="LAG",
            mining_unit_id=unit.id,
        )
        req = Requisition(
            document_no=document_no,
            document_registry_id=registry.id,
            company_id=unit.company_id,
            mining_unit_id=unit.id,
            department_id=payload.department_id,
            warehouse_id=payload.warehouse_id,
            equipment_id=payload.equipment_id,
            cost_center_id=payload.cost_center_id,
            requester_id=actor_id,
            requisition_type=payload.requisition_type,
            priority=payload.priority,
            status="DRAFT",
            justification=payload.justification,
            observations=payload.observations,
            needed_at=payload.needed_at,
        )
        db.add(req)
        db.flush()
        for index, line in enumerate(payload.lines, start=1):
            db.add(
                RequisitionLine(
                    requisition_id=req.id,
                    line_no=index,
                    item_id=line.item_id,
                    description=line.description,
                    uom_id=line.uom_id,
                    requested_qty=line.requested_qty,
                    authorised_qty=Decimal("0"),
                    cancelled_qty=Decimal("0"),
                    status="OPEN",
                    notes=line.notes,
                )
            )
        db.flush()
        registry.entity_type = "Requisition"
        registry.entity_id = req.id
        record_document_event(db, registry, "REQUISITION_CREATED", None, "DRAFT", actor_id)
        AuditService.record(
            db,
            action="REQUISITION_CREATE",
            entity_type="Requisition",
            entity_id=req.id,
            actor_id=actor_id,
            after={"document_no": document_no, "lines": len(payload.lines)},
        )
        emit(db, "Requisition", req.id, "REQUISITION_CREATED", {"document_no": document_no})
        return req

    @staticmethod
    def update_draft(db: Session, actor_id: uuid.UUID, requisition_id: uuid.UUID, payload) -> Requisition:
        req = db.execute(
            select(Requisition).where(Requisition.id == requisition_id).with_for_update()
        ).scalar_one_or_none()
        if req is None:
            _fail("Requisición inexistente.", status.HTTP_404_NOT_FOUND)
        if req.status != "DRAFT":
            _fail("Solo se pueden modificar requisiciones en borrador.")
        before = {
            "justification": req.justification,
            "observations": req.observations,
            "priority": req.priority,
        }
        req.justification = payload.justification
        req.observations = payload.observations
        req.priority = payload.priority
        req.needed_at = payload.needed_at
        AuditService.record(
            db,
            action="REQUISITION_DRAFT_UPDATE",
            entity_type="Requisition",
            entity_id=req.id,
            actor_id=actor_id,
            before=before,
            after={
                "justification": req.justification,
                "observations": req.observations,
                "priority": req.priority,
            },
        )
        return req

    @staticmethod
    def submit(db: Session, actor_id: uuid.UUID, requisition_id: uuid.UUID) -> Requisition:
        req = db.execute(
            select(Requisition).where(Requisition.id == requisition_id).with_for_update()
        ).scalar_one_or_none()
        if req is None:
            _fail("Requisición inexistente.", status.HTTP_404_NOT_FOUND)
        if req.status != "DRAFT":
            _fail("Solo se puede enviar una requisición en borrador.")
        line_count = db.execute(
            select(func.count()).select_from(RequisitionLine).where(RequisitionLine.requisition_id == req.id)
        ).scalar_one()
        if line_count == 0:
            _fail("La requisición no tiene partidas.")

        req.status = "SUBMITTED"
        req.submitted_at = datetime.now(timezone.utc)
        approval = ApprovalRequest(
            document_type="REQUISITION",
            document_id=req.id,
            requisition_id=req.id,
            status="PENDING",
            current_step_no=1,
            requested_at=req.submitted_at,
        )
        db.add(approval)
        db.flush()
        db.add(
            ApprovalStep(
                approval_request_id=approval.id,
                step_no=1,
                role_code="APROBADOR",
                status="PENDING",
            )
        )
        registry = db.get(DocumentRegistry, req.document_registry_id)
        if registry is not None:
            record_document_event(db, registry, "REQUISITION_SUBMITTED", "DRAFT", "SUBMITTED", actor_id)
        AuditService.record(
            db,
            action="REQUISITION_SUBMIT",
            entity_type="Requisition",
            entity_id=req.id,
            actor_id=actor_id,
            after={"status": "SUBMITTED"},
        )
        emit(db, "Requisition", req.id, "REQUISITION_SUBMITTED", {})
        return req

    @staticmethod
    def decide(db: Session, actor_id: uuid.UUID, requisition_id: uuid.UUID, payload) -> Requisition:
        req = db.execute(
            select(Requisition).where(Requisition.id == requisition_id).with_for_update()
        ).scalar_one_or_none()
        if req is None:
            _fail("Requisición inexistente.", status.HTTP_404_NOT_FOUND)
        if req.status != "SUBMITTED":
            _fail("La requisición no está pendiente de autorización.")

        approval = db.execute(
            select(ApprovalRequest)
            .where(ApprovalRequest.requisition_id == req.id, ApprovalRequest.status == "PENDING")
            .with_for_update()
        ).scalar_one_or_none()
        if approval is None:
            _fail("No hay solicitud de aprobación activa.")
        step = db.execute(
            select(ApprovalStep)
            .where(
                ApprovalStep.approval_request_id == approval.id,
                ApprovalStep.step_no == approval.current_step_no,
                ApprovalStep.status == "PENDING",
            )
            .with_for_update()
        ).scalar_one_or_none()
        if step is None:
            _fail("No hay paso de aprobación pendiente.")

        lines = {
            line.id: line
            for line in db.execute(
                select(RequisitionLine)
                .where(RequisitionLine.requisition_id == req.id)
                .with_for_update()
            ).scalars()
        }
        if not payload.decisions:
            _fail("Debe enviar al menos una decisión.")
        seen: set[uuid.UUID] = set()
        approved_by_line: dict[uuid.UUID, Decimal] = {}
        has_reject = False
        for decision in payload.decisions:
            if decision.requisition_line_id in seen:
                _fail("Partida duplicada en la decisión.")
            seen.add(decision.requisition_line_id)
            line = lines.get(decision.requisition_line_id)
            if line is None:
                _fail("La partida no pertenece a la requisición.")
            if decision.decision == "REJECT":
                has_reject = True
                if not decision.reason and not payload.reason:
                    _fail("El rechazo requiere motivo.", 422)
                qty = Decimal("0")
            else:
                qty = decision.approved_qty
                if qty > line.requested_qty - line.cancelled_qty:
                    _fail("La cantidad autorizada excede la solicitada.")
            approved_by_line[line.id] = approved_by_line.get(line.id, Decimal("0")) + qty
            db.add(
                ApprovalDecision(
                    approval_step_id=step.id,
                    requisition_line_id=line.id,
                    decision=decision.decision,
                    approved_qty=qty,
                    reason=decision.reason or payload.reason,
                    decided_by=actor_id,
                    decided_at=datetime.now(timezone.utc),
                )
            )

        for line_id, qty in approved_by_line.items():
            line = lines[line_id]
            line.authorised_qty = qty
            if qty <= Decimal("0"):
                line.status = "CANCELLED"
            elif qty < line.requested_qty - line.cancelled_qty:
                line.status = "PARTIAL"
            else:
                line.status = "AUTHORISED"

        total_requested = sum((line.requested_qty - line.cancelled_qty for line in lines.values()), Decimal("0"))
        total_approved = sum(approved_by_line.values(), Decimal("0"))
        now = datetime.now(timezone.utc)
        if has_reject and total_approved == Decimal("0"):
            req.status = "REJECTED"
            req.rejected_at = now
            req.rejection_reason = payload.reason or "Rechazo parcial sin autorización"
            approval.status = "REJECTED"
            step.status = "REJECTED"
            new_status = "REJECTED"
        elif total_approved >= total_requested:
            req.status = "APPROVED"
            req.approved_at = now
            approval.status = "APPROVED"
            step.status = "APPROVED"
            new_status = "APPROVED"
        else:
            req.status = "PARTIALLY_APPROVED"
            req.approved_at = now
            approval.status = "PARTIAL"
            step.status = "APPROVED"
            new_status = "PARTIALLY_APPROVED"
        approval.completed_at = now
        step.acted_at = now

        registry = db.get(DocumentRegistry, req.document_registry_id)
        if registry is not None:
            record_document_event(
                db,
                registry,
                "REQUISITION_DECIDED",
                "SUBMITTED",
                new_status,
                actor_id,
                {"reason": payload.reason},
            )
        AuditService.record(
            db,
            action="REQUISITION_DECIDE",
            entity_type="Requisition",
            entity_id=req.id,
            actor_id=actor_id,
            after={"status": new_status, "approved_qty": str(total_approved)},
            detail=payload.reason,
        )
        emit(db, "Requisition", req.id, "REQUISITION_DECIDED", {"status": new_status})
        return req

    @staticmethod
    def to_out(db: Session, req: Requisition) -> dict:
        lines = []
        for line in sorted(req.lines, key=lambda item: item.line_no):
            reserved = InventoryService.line_reserved_qty(db, line.id)
            delivered = InventoryService.line_delivered_qty(db, line.id)
            purchased = PurchasingService.line_purchased_qty(db, line.id)
            received = PurchasingService.line_received_qty(db, line.id)
            lines.append(
                {
                    "id": line.id,
                    "line_no": line.line_no,
                    "item_id": line.item_id,
                    "description": line.description,
                    "uom_id": line.uom_id,
                    "requested_qty": line.requested_qty,
                    "authorised_qty": line.authorised_qty,
                    "cancelled_qty": line.cancelled_qty,
                    "status": line.status,
                    "notes": line.notes,
                    "reserved_qty": reserved,
                    "purchased_qty": purchased,
                    "received_qty": received,
                    "delivered_qty": delivered,
                    "pending_qty": line.requested_qty - line.cancelled_qty - delivered,
                }
            )
        return {
            "id": req.id,
            "document_no": req.document_no,
            "department_id": req.department_id,
            "warehouse_id": req.warehouse_id,
            "equipment_id": req.equipment_id,
            "cost_center_id": req.cost_center_id,
            "requisition_type": req.requisition_type,
            "priority": req.priority,
            "status": req.status,
            "justification": req.justification,
            "observations": req.observations,
            "needed_at": req.needed_at,
            "submitted_at": req.submitted_at,
            "approved_at": req.approved_at,
            "rejected_at": req.rejected_at,
            "rejection_reason": req.rejection_reason,
            "created_at": req.created_at,
            "lines": lines,
        }

    @staticmethod
    def history(db: Session, requisition_id: uuid.UUID) -> list[dict]:
        req = db.get(Requisition, requisition_id)
        if req is None:
            _fail("Requisición inexistente.", status.HTTP_404_NOT_FOUND)
        events = db.execute(
            select(DocumentEvent)
            .join(DocumentRegistry, DocumentEvent.document_registry_id == DocumentRegistry.id)
            .where(DocumentRegistry.entity_type == "Requisition", DocumentRegistry.entity_id == req.id)
            .order_by(DocumentEvent.occurred_at)
        ).scalars()
        return [
            {
                "event_type": event.event_type,
                "from_status": event.from_status,
                "to_status": event.to_status,
                "occurred_at": event.occurred_at,
                "actor_id": event.actor_id,
                "metadata": event.metadata_json,
            }
            for event in events
        ]
