from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import NoReturn

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.audit.models import AuditLog
from app.modules.audit.service import AuditService
from app.modules.costing.models import CostCenter
from app.modules.documentation.models import (
    DocumentEvent,
    DocumentRegistry,
    DocumentRender,
    WarehouseVoucher,
)
from app.modules.identity.models import AppUser
from app.modules.identity.service import IdentityService
from app.modules.inventory.models import StockMovement, StockReservation
from app.modules.inventory.service import InventoryService
from app.modules.master_data.models import Item, Uom
from app.modules.organization.models import Department, MiningUnit, Warehouse
from app.modules.purchasing.service import PurchasingService
from app.modules.requisitions.models import Requisition, RequisitionAttachment, RequisitionLine
from app.modules.sla.service import SlaService
from app.modules.workflow.models import ApprovalDecision, ApprovalRequest, ApprovalStep
from app.shared.constants import APPROVER_ROLE_CODES
from app.shared.events import emit
from app.shared.numbering import next_document_number, record_document_event


class RequisitionError(HTTPException):
    pass


def _fail(detail: str, code: int = status.HTTP_409_CONFLICT) -> NoReturn:
    raise RequisitionError(status_code=code, detail=detail)


_ALLOWED_ATTACHMENTS: dict[str, set[str]] = {
    "image/jpeg": {".jpg", ".jpeg"},
    "image/png": {".png"},
    "application/pdf": {".pdf"},
}


class RequisitionService:
    @staticmethod
    def _context(
        db: Session,
        actor_id: uuid.UUID,
        department_id: uuid.UUID,
        warehouse_id: uuid.UUID | None,
        cost_center_id: uuid.UUID,
        equipment_id: uuid.UUID | None,
    ) -> tuple[uuid.UUID, uuid.UUID]:
        """Resuelve compañía/unidad desde el departamento y valida referencias."""
        IdentityService.assert_department_access(db, actor_id, department_id)
        department = db.get(Department, department_id)
        if department is None:
            _fail("Departamento inexistente.", status.HTTP_404_NOT_FOUND)
        if department.mining_unit_id is None:
            _fail("El departamento no tiene una unidad minera asignada.", status.HTTP_422_UNPROCESSABLE_ENTITY)
        unit = db.get(MiningUnit, department.mining_unit_id)
        if unit is None:
            _fail("Unidad minera inexistente.", status.HTTP_404_NOT_FOUND)
        company_id = department.company_id

        def check(model, entity_id: uuid.UUID | None, label: str):
            if entity_id is None:
                return None
            entity = db.get(model, entity_id)
            if entity is None:
                _fail(f"{label} inexistente.", status.HTTP_404_NOT_FOUND)
            if getattr(entity, "company_id", None) != company_id:
                _fail(f"{label} pertenece a otra compañía.", status.HTTP_422_UNPROCESSABLE_ENTITY)
            return entity

        cost_center = db.get(CostCenter, cost_center_id)
        if cost_center is None:
            _fail("Centro de costo inexistente.", status.HTTP_404_NOT_FOUND)
        if cost_center.company_id != company_id:
            _fail("El centro de costo pertenece a otra compañía.", status.HTTP_422_UNPROCESSABLE_ENTITY)
        check(Warehouse, warehouse_id, "Almacén")
        if equipment_id is not None:
            from app.modules.maintenance.models import Equipment

            check(Equipment, equipment_id, "Equipo")
        return company_id, unit.id

    @staticmethod
    def _assert_lines(db: Session, lines, company_id: uuid.UUID) -> None:
        if not lines:
            _fail("La requisición debe tener al menos una partida.", status.HTTP_422_UNPROCESSABLE_ENTITY)
        for line in lines:
            if not line.description.strip():
                _fail("Las partidas requieren descripción.", status.HTTP_422_UNPROCESSABLE_ENTITY)
            if line.requested_qty <= Decimal("0"):
                _fail("La cantidad solicitada debe ser positiva.", status.HTTP_422_UNPROCESSABLE_ENTITY)
            if db.get(Uom, line.uom_id) is None:
                _fail(f"Unidad de medida inexistente en partida {line.description}.")
            if line.item_id is not None:
                item = db.get(Item, line.item_id)
                if item is None:
                    _fail(f"Artículo inexistente en partida {line.description}.")
                if item.company_id != company_id:
                    _fail(f"El artículo de la partida {line.description} pertenece a otra compañía.")

    @staticmethod
    def _is_owner_or_admin(db: Session, req: Requisition, actor_id: uuid.UUID) -> bool:
        return req.requester_id == actor_id or IdentityService.is_admin(db, actor_id)

    @staticmethod
    def create(db: Session, actor_id: uuid.UUID, payload) -> Requisition:
        company_id, unit_id = RequisitionService._context(
            db,
            actor_id,
            payload.department_id,
            payload.warehouse_id,
            payload.cost_center_id,
            payload.equipment_id,
        )
        RequisitionService._assert_lines(db, payload.lines, company_id)
        if payload.requisition_type == "STOCK" and payload.warehouse_id is None:
            _fail("Las requisiciones de almacén requieren un almacén.", status.HTTP_422_UNPROCESSABLE_ENTITY)

        registry, document_no = next_document_number(
            db,
            "REQ",
            company_id,
            series="LAG",
            mining_unit_id=unit_id,
        )
        req = Requisition(
            document_no=document_no,
            document_registry_id=registry.id,
            company_id=company_id,
            mining_unit_id=unit_id,
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
            work_order_no=payload.work_order_no,
            created_by=actor_id,
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
                    created_by=actor_id,
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
            before=None,
            after={"document_no": document_no, "lines": len(payload.lines), "work_order_no": payload.work_order_no},
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
        if not RequisitionService._is_owner_or_admin(db, req, actor_id):
            _fail("Solo el solicitante puede editar esta requisición.", status.HTTP_403_FORBIDDEN)
        if req.status != "DRAFT":
            _fail("Solo se pueden modificar requisiciones en borrador.")
        RequisitionService._context(
            db,
            actor_id,
            req.department_id,
            req.warehouse_id,
            req.cost_center_id,
            req.equipment_id,
        )
        before = {
            "justification": req.justification,
            "observations": req.observations,
            "priority": req.priority,
            "needed_at": str(req.needed_at),
            "work_order_no": req.work_order_no,
        }
        req.justification = payload.justification
        req.observations = payload.observations
        req.priority = payload.priority
        req.needed_at = payload.needed_at
        req.work_order_no = payload.work_order_no
        req.updated_by = actor_id

        if payload.lines is not None:
            company_id, _unit_id = RequisitionService._context(
                db,
                actor_id,
                req.department_id,
                req.warehouse_id,
                req.cost_center_id,
                req.equipment_id,
            )
            RequisitionService._assert_lines(db, payload.lines, company_id)
            existing = {
                line.id: line
                for line in db.execute(
                    select(RequisitionLine).where(RequisitionLine.requisition_id == req.id).with_for_update()
                ).scalars()
            }
            kept: set[uuid.UUID] = set()
            next_no = max((line.line_no for line in existing.values()), default=0) + 1
            for incoming in payload.lines:
                line = existing.get(incoming.id) if incoming.id else None
                if line is not None:
                    if line.requisition_id != req.id:
                        _fail("La partida no pertenece a la requisición.")
                    kept.add(line.id)
                else:
                    line = RequisitionLine(
                        requisition_id=req.id,
                        line_no=next_no,
                        authorised_qty=Decimal("0"),
                        cancelled_qty=Decimal("0"),
                        status="OPEN",
                        created_by=actor_id,
                    )
                    next_no += 1
                    db.add(line)
                line.item_id = incoming.item_id
                line.description = incoming.description
                line.uom_id = incoming.uom_id
                line.requested_qty = incoming.requested_qty
                line.notes = incoming.notes
                line.updated_by = actor_id
            for line_id, line in existing.items():
                if line_id in kept:
                    continue
                line.cancelled_qty = line.requested_qty
                line.authorised_qty = Decimal("0")
                line.status = "CANCELLED"
                line.updated_by = actor_id

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
                "needed_at": str(req.needed_at),
                "work_order_no": req.work_order_no,
                "lines": len(payload.lines) if payload.lines is not None else None,
            },
        )
        registry = db.get(DocumentRegistry, req.document_registry_id)
        if registry is not None:
            record_document_event(db, registry, "REQUISITION_DRAFT_UPDATED", "DRAFT", "DRAFT", actor_id)
        return req

    @staticmethod
    def submit(db: Session, actor_id: uuid.UUID, requisition_id: uuid.UUID) -> Requisition:
        req = db.execute(
            select(Requisition).where(Requisition.id == requisition_id).with_for_update()
        ).scalar_one_or_none()
        if req is None:
            _fail("Requisición inexistente.", status.HTTP_404_NOT_FOUND)
        if not RequisitionService._is_owner_or_admin(db, req, actor_id):
            _fail("Solo el solicitante puede enviar esta requisición.", status.HTTP_403_FORBIDDEN)
        if req.status != "DRAFT":
            _fail("Solo se puede enviar una requisición en borrador.")
        lines = list(
            db.execute(
                select(RequisitionLine).where(RequisitionLine.requisition_id == req.id).with_for_update()
            ).scalars()
        )
        if not any(line.status != "CANCELLED" and line.requested_qty > line.cancelled_qty for line in lines):
            _fail("La requisición no tiene partidas vigentes.")

        req.status = "SUBMITTED"
        req.submitted_at = datetime.now(timezone.utc)
        req.updated_by = actor_id
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
            before={"status": "DRAFT"},
            after={"status": "SUBMITTED"},
        )
        emit(db, "Requisition", req.id, "REQUISITION_SUBMITTED", {})
        SlaService.record_snapshot(db, req, trigger="ON_SUBMIT", actor_id=actor_id)
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
        if req.requester_id == actor_id:
            _fail("No puede autorizar su propia requisición.", status.HTTP_403_FORBIDDEN)
        if not IdentityService.can_access_department(db, actor_id, req.department_id):
            _fail("No tiene acceso a requisiciones de ese departamento.", status.HTTP_403_FORBIDDEN)
        actor_roles = set(IdentityService.role_codes(db, actor_id))
        if not actor_roles & APPROVER_ROLE_CODES:
            _fail("Su rol no corresponde al paso de aprobación.", status.HTTP_403_FORBIDDEN)

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
            reason = decision.reason or payload.reason
            if decision.decision == "REJECT":
                has_reject = True
                if not reason:
                    _fail("El rechazo requiere motivo.", status.HTTP_422_UNPROCESSABLE_ENTITY)
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
                    reason=reason,
                    decided_by=actor_id,
                    decided_at=datetime.now(timezone.utc),
                )
            )

        omitted = 0
        for line_id, line in lines.items():
            decided_qty = approved_by_line.get(line_id)
            if line.status == "CANCELLED":
                continue
            if decided_qty is None:
                omitted += 1
                line.authorised_qty = Decimal("0")
                line.cancelled_qty = line.requested_qty
                line.status = "CANCELLED"
                line.updated_by = actor_id
                continue
            line.authorised_qty = decided_qty
            if decided_qty <= Decimal("0"):
                line.status = "CANCELLED"
                line.cancelled_qty = line.requested_qty
            elif decided_qty < line.requested_qty - line.cancelled_qty:
                line.status = "PARTIAL"
            else:
                line.status = "AUTHORISED"
            line.updated_by = actor_id
            if decided_qty <= Decimal("0"):
                InventoryService.release_line_reservations(db, line.id, actor_id, "Partida rechazada")

        active_requested = sum(
            (line.requested_qty - line.cancelled_qty for line in lines.values()), Decimal("0")
        )
        total_approved = sum(
            (approved_by_line.get(line_id, Decimal("0")) for line_id in lines if lines[line_id].status != "CANCELLED"),
            Decimal("0"),
        )
        now = datetime.now(timezone.utc)
        if active_requested == Decimal("0") or (has_reject and total_approved == Decimal("0")):
            req.status = "REJECTED"
            req.rejected_at = now
            req.rejection_reason = payload.reason or "Todas las partidas fueron canceladas."
            approval.status = "REJECTED"
            step.status = "REJECTED"
            new_status = "REJECTED"
        elif total_approved >= active_requested:
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
        req.updated_by = actor_id

        registry = db.get(DocumentRegistry, req.document_registry_id)
        if registry is not None:
            record_document_event(
                db,
                registry,
                "REQUISITION_DECIDED",
                "SUBMITTED",
                new_status,
                actor_id,
                {"reason": payload.reason, "omitted_lines": omitted},
            )
        AuditService.record(
            db,
            action="REQUISITION_DECIDE",
            entity_type="Requisition",
            entity_id=req.id,
            actor_id=actor_id,
            before={"status": "SUBMITTED"},
            after={"status": new_status, "approved_qty": str(total_approved), "omitted_lines": omitted},
            detail=payload.reason,
        )
        emit(db, "Requisition", req.id, "REQUISITION_DECIDED", {"status": new_status})
        SlaService.record_snapshot(db, req, trigger="ON_DECIDE", actor_id=actor_id)
        return req

    @staticmethod
    def cancel(db: Session, actor_id: uuid.UUID, requisition_id: uuid.UUID, reason: str) -> Requisition:
        req = db.execute(
            select(Requisition).where(Requisition.id == requisition_id).with_for_update()
        ).scalar_one_or_none()
        if req is None:
            _fail("Requisición inexistente.", status.HTTP_404_NOT_FOUND)
        if req.status in ("CANCELLED", "CLOSED", "REJECTED"):
            _fail("La requisición ya está cerrada, cancelada o rechazada.")
        if req.requester_id == actor_id and not IdentityService.is_admin(db, actor_id):
            _fail("La cancelación debe ser autorizada por otro responsable.", status.HTTP_403_FORBIDDEN)
        if not IdentityService.can_access_department(db, actor_id, req.department_id):
            _fail("No tiene acceso a requisiciones de ese departamento.", status.HTTP_403_FORBIDDEN)

        old_status = req.status
        lines = list(
            db.execute(
                select(RequisitionLine).where(RequisitionLine.requisition_id == req.id).with_for_update()
            ).scalars()
        )
        for line in lines:
            InventoryService.release_line_reservations(db, line.id, actor_id, f"Cancelación: {reason}")
            delivered = InventoryService.line_delivered_qty(db, line.id)
            restante = max(Decimal("0"), line.requested_qty - delivered - line.cancelled_qty)
            line.cancelled_qty += restante
            line.authorised_qty = delivered
            line.status = "CLOSED" if delivered > Decimal("0") else "CANCELLED"
            line.updated_by = actor_id

        approval = db.execute(
            select(ApprovalRequest)
            .where(ApprovalRequest.requisition_id == req.id, ApprovalRequest.status == "PENDING")
            .with_for_update()
        ).scalar_one_or_none()
        if approval is not None:
            approval.status = "CANCELLED"
            approval.completed_at = datetime.now(timezone.utc)
            steps = db.execute(
                select(ApprovalStep)
                .where(ApprovalStep.approval_request_id == approval.id, ApprovalStep.status == "PENDING")
                .with_for_update()
            ).scalars()
            for step in steps:
                step.status = "SKIPPED"
                step.acted_at = datetime.now(timezone.utc)

        req.status = "CANCELLED"
        req.rejection_reason = reason
        req.closed_at = datetime.now(timezone.utc)
        req.updated_by = actor_id
        registry = db.get(DocumentRegistry, req.document_registry_id)
        if registry is not None:
            record_document_event(
                db, registry, "REQUISITION_CANCELLED", old_status, "CANCELLED", actor_id, {"reason": reason}
            )
        AuditService.record(
            db,
            action="REQUISITION_CANCEL",
            entity_type="Requisition",
            entity_id=req.id,
            actor_id=actor_id,
            before={"status": old_status},
            after={"status": "CANCELLED"},
            detail=reason,
        )
        emit(db, "Requisition", req.id, "REQUISITION_CANCELLED", {"reason": reason})
        SlaService.record_snapshot(db, req, trigger="ON_CANCEL", actor_id=actor_id)
        return req

    @staticmethod
    def to_out(db: Session, req: Requisition) -> dict:
        lines = []
        for line in sorted(req.lines, key=lambda item: item.line_no):
            reserved = InventoryService.line_reserved_qty(db, line.id)
            delivered = InventoryService.line_delivered_qty(db, line.id)
            purchased = PurchasingService.line_purchased_qty(db, line.id)
            received = PurchasingService.line_received_qty(db, line.id)
            pending = max(Decimal("0"), line.authorised_qty - delivered)
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
                    "pending_qty": pending,
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
            "work_order_no": req.work_order_no,
            "submitted_at": req.submitted_at,
            "approved_at": req.approved_at,
            "rejected_at": req.rejected_at,
            "rejection_reason": req.rejection_reason,
            "created_at": req.created_at,
            "sla": SlaService.evaluate(db, req),
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

    # ------------------------------------------------------------------
    # Adjuntos en almacenamiento controlado
    # ------------------------------------------------------------------
    @staticmethod
    def _attachment_requisition(db: Session, actor_id: uuid.UUID, requisition_id: uuid.UUID) -> Requisition:
        req = db.get(Requisition, requisition_id)
        if req is None:
            _fail("Requisición inexistente.", status.HTTP_404_NOT_FOUND)
        if not IdentityService.can_access_department(db, actor_id, req.department_id):
            _fail("No tiene acceso a los adjuntos de esa requisición.", status.HTTP_403_FORBIDDEN)
        return req

    @staticmethod
    def add_attachment(
        db: Session,
        actor_id: uuid.UUID,
        requisition_id: uuid.UUID,
        *,
        file_name: str,
        content_type: str,
        content: bytes,
    ) -> RequisitionAttachment:
        RequisitionService._attachment_requisition(db, actor_id, requisition_id)
        suffix = Path(file_name).suffix.lower()
        allowed = _ALLOWED_ATTACHMENTS.get(content_type.lower())
        if allowed is None or suffix not in allowed:
            _fail("Solo se admiten adjuntos PDF, JPG o PNG.", status.HTTP_422_UNPROCESSABLE_ENTITY)
        if not content or len(content) > settings.ATTACHMENT_MAX_BYTES:
            _fail("El adjunto está vacío o excede el tamaño permitido.", status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)

        stored_name = f"{uuid.uuid4()}{suffix}"
        directory = settings.ATTACHMENT_STORAGE_DIR / str(requisition_id)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / stored_name
        digest = hashlib.sha256(content).hexdigest()
        with path.open("xb") as handle:
            handle.write(content)
        try:
            attachment = RequisitionAttachment(
                requisition_id=requisition_id,
                file_name=Path(file_name).name[:255],
                stored_name=stored_name,
                content_type=content_type.lower(),
                size_bytes=len(content),
                sha256=digest,
                uploaded_by=actor_id,
            )
            db.add(attachment)
            db.flush()
            AuditService.record(
                db,
                action="REQUISITION_ATTACHMENT_UPLOAD",
                entity_type="RequisitionAttachment",
                entity_id=attachment.id,
                actor_id=actor_id,
                after={"requisition_id": str(requisition_id), "sha256": digest, "size_bytes": len(content)},
            )
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return attachment

    @staticmethod
    def list_attachments(db: Session, actor_id: uuid.UUID, requisition_id: uuid.UUID) -> list[RequisitionAttachment]:
        RequisitionService._attachment_requisition(db, actor_id, requisition_id)
        return list(
            db.execute(
                select(RequisitionAttachment)
                .where(RequisitionAttachment.requisition_id == requisition_id)
                .order_by(RequisitionAttachment.created_at)
            ).scalars()
        )

    @staticmethod
    def attachment_path(db: Session, actor_id: uuid.UUID, attachment_id: uuid.UUID) -> Path:
        attachment = db.get(RequisitionAttachment, attachment_id)
        if attachment is None:
            _fail("Adjunto inexistente.", status.HTTP_404_NOT_FOUND)
        RequisitionService._attachment_requisition(db, actor_id, attachment.requisition_id)
        path = settings.ATTACHMENT_STORAGE_DIR / str(attachment.requisition_id) / attachment.stored_name
        if not path.is_file():
            _fail("El archivo adjunto no está disponible.", status.HTTP_404_NOT_FOUND)
        return path

    @staticmethod
    def trace(db: Session, actor_id: uuid.UUID, requisition_id: uuid.UUID) -> dict:
        """Devuelve la cadena documental completa sin escribir ni generar movimientos."""
        req = db.get(Requisition, requisition_id)
        if req is None:
            _fail("Requisición inexistente.", status.HTTP_404_NOT_FOUND)
        IdentityService.assert_department_access(db, actor_id, req.department_id)
        line_ids = [
            row[0]
            for row in db.execute(
                select(RequisitionLine.id).where(RequisitionLine.requisition_id == req.id)
            ).all()
        ]
        tracking_full = SlaService._requisition_out(db, req)
        tracking = {
            key: tracking_full.get(key)
            for key in (
                "sla",
                "administrative_status",
                "pending_days",
                "fulfillment_percent",
                "needed_at",
            )
        }

        approvals: list[dict] = []
        for decision in db.execute(
            select(ApprovalDecision)
            .join(ApprovalStep, ApprovalDecision.approval_step_id == ApprovalStep.id)
            .join(ApprovalRequest, ApprovalStep.approval_request_id == ApprovalRequest.id)
            .where(ApprovalRequest.requisition_id == req.id)
            .order_by(ApprovalStep.step_no, ApprovalDecision.created_at)
        ).scalars():
            actor = db.get(AppUser, decision.decided_by) if decision.decided_by else None
            approvals.append(
                {
                    "id": decision.id,
                    "decision": decision.decision,
                    "approved_qty": decision.approved_qty,
                    "reason": decision.reason,
                    "decided_at": decision.decided_at,
                    "decided_by": actor.full_name if actor else None,
                }
            )

        reservations: list[dict] = []
        if line_ids:
            for reservation_row in db.execute(
                select(StockReservation).where(StockReservation.requisition_line_id.in_(line_ids))
            ).scalars():
                reservations.append(
                    {
                        "id": reservation_row.id,
                        "reservation_no": reservation_row.reservation_no,
                        "quantity": reservation_row.quantity,
                        "consumed_qty": reservation_row.consumed_qty,
                        "status": reservation_row.status,
                        "created_at": reservation_row.created_at,
                        "expires_at": reservation_row.expires_at,
                    }
                )

        deliveries: list[dict] = []
        if line_ids:
            for movement_row in db.execute(
                select(StockMovement).where(
                    StockMovement.requisition_line_id.in_(line_ids),
                    StockMovement.movement_type == "ISSUE",
                    StockMovement.status == "POSTED",
                )
            ).scalars():
                deliveries.append(
                    {
                        "id": movement_row.id,
                        "movement_no": movement_row.movement_no,
                        "quantity": movement_row.quantity,
                        "posted_at": movement_row.posted_at,
                        "source_document_type": movement_row.source_document_type,
                    }
                )

        vouchers: list[dict] = []
        voucher_rows = list(
            db.execute(
                select(WarehouseVoucher)
                .where(WarehouseVoucher.source_requisition_id == req.id)
                .order_by(WarehouseVoucher.created_at)
            ).scalars()
        )
        voucher_ids = [row.id for row in voucher_rows]
        renders_by_voucher: dict[uuid.UUID, list[dict]] = {key: [] for key in voucher_ids}
        if voucher_ids:
            for render in db.execute(
                select(DocumentRender).where(
                    DocumentRender.entity_type == "WarehouseVoucher",
                    DocumentRender.entity_id.in_(voucher_ids),
                )
            ).scalars():
                renders_by_voucher.setdefault(render.entity_id, []).append(
                    {
                        "id": render.id,
                        "document_format": render.document_format,
                        "sha256": render.sha256,
                        "is_reprint": render.is_reprint,
                        "rendered_at": render.rendered_at,
                    }
                )
        for voucher in voucher_rows:
            vouchers.append(
                {
                    "id": voucher.id,
                    "document_no": voucher.document_no,
                    "status": voucher.status,
                    "issued_at": voucher.issued_at,
                    "received_by_name": voucher.received_by_name,
                    "authorized_by_name": voucher.authorized_by_name,
                    "dispatched_by_name": voucher.dispatched_by_name,
                    "renders": sorted(
                        renders_by_voucher.get(voucher.id, []),
                        key=lambda item: item["rendered_at"],
                    ),
                }
            )

        registry_ids = [req.document_registry_id] if req.document_registry_id else []
        registry_ids.extend(
            voucher.document_registry_id for voucher in voucher_rows if voucher.document_registry_id
        )
        document_events: list[dict] = []
        if registry_ids:
            for document_event_row in db.execute(
                select(DocumentEvent)
                .where(DocumentEvent.document_registry_id.in_(registry_ids))
                .order_by(DocumentEvent.occurred_at)
            ).scalars():
                document_events.append(
                    {
                        "event_type": document_event_row.event_type,
                        "from_status": document_event_row.from_status,
                        "to_status": document_event_row.to_status,
                        "occurred_at": document_event_row.occurred_at,
                        "metadata": document_event_row.metadata_json,
                    }
                )

        audit_events: list[dict] = []
        entity_ids = [req.id, *voucher_ids]
        for audit_event_row in db.execute(
            select(AuditLog)
            .where(AuditLog.entity_id.in_(entity_ids))
            .order_by(AuditLog.occurred_at.desc())
        ).scalars():
            audit_events.append(
                {
                    "action": audit_event_row.action,
                    "entity_type": audit_event_row.entity_type,
                    "actor_username": audit_event_row.actor_username,
                    "occurred_at": audit_event_row.occurred_at,
                    "request_id": audit_event_row.request_id,
                }
            )

        sla_result = tracking["sla"] or {}
        stages = [
            {
                "stage": "REQUISICION",
                "label": "Requisición",
                "completed": True,
                "document_no": req.document_no,
                "occurred_at": req.created_at,
                "detail": req.status,
            },
            {
                "stage": "AUTORIZACION",
                "label": "Autorización",
                "completed": bool(approvals) or req.approved_at is not None,
                "document_no": req.document_no,
                "occurred_at": req.approved_at,
                "detail": f"{len(approvals)} decisión(es) registradas",
            },
            {
                "stage": "RESERVA",
                "label": "Reserva",
                "completed": bool(reservations),
                "occurred_at": min((item["created_at"] for item in reservations), default=None),
                "detail": f"{len(reservations)} reserva(s)",
            },
            {
                "stage": "ENTREGA",
                "label": "Entrega",
                "completed": bool(deliveries),
                "occurred_at": min((item["posted_at"] for item in deliveries), default=None),
                "detail": f"{len(deliveries)} movimiento(s) de salida",
            },
            {
                "stage": "VALE",
                "label": "Vale de almacén",
                "completed": bool(vouchers),
                "document_no": vouchers[0]["document_no"] if vouchers else None,
                "occurred_at": vouchers[0]["issued_at"] if vouchers else None,
                "detail": f"{len(vouchers)} vale(s)",
            },
            {
                "stage": "SEGUIMIENTO",
                "label": "Seguimiento SLA",
                "completed": bool(sla_result.get("measured")),
                "document_no": req.document_no,
                "occurred_at": sla_result.get("base_at"),
                "detail": (
                    f"{sla_result.get('label')} · surtido {tracking['fulfillment_percent']}%"
                ),
            },
        ]
        return {
            "requisition_id": req.id,
            "document_no": req.document_no,
            "administrative_status": req.status,
            "tracking": tracking,
            "stages": stages,
            "approvals": approvals,
            "reservations": reservations,
            "deliveries": deliveries,
            "vouchers": vouchers,
            "document_events": document_events,
            "audit_events": audit_events,
            "generated_at": datetime.now(timezone.utc),
        }
