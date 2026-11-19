from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal, NoReturn

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.audit.service import AuditService
from app.modules.identity.service import IdentityService
from app.modules.organization.models import Department
from app.modules.requisitions.models import Requisition
from app.modules.sla.models import RequisitionSlaEvent, SlaPolicy
from app.shared.constants import SLA_TERMINAL_STATUSES
from app.shared.events import emit

_LABELS = {
    "GREEN": "En plazo",
    "YELLOW": "En riesgo",
    "RED": "Fuera de plazo",
    "NONE": "Sin medición",
}

_ACTIVE_STATUSES = ("SUBMITTED", "APPROVED", "PARTIALLY_APPROVED", "IN_PROGRESS")


class SlaError(HTTPException):
    pass


def _fail(detail: str, code: int = status.HTTP_409_CONFLICT) -> NoReturn:
    raise SlaError(status_code=code, detail=detail)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _scope(department_id: uuid.UUID | None, requisition_type: str) -> str:
    if department_id is None and requisition_type == "ALL":
        return "GLOBAL"
    if department_id is not None and requisition_type == "ALL":
        return "DEPARTMENT"
    if department_id is None:
        return "TYPE"
    return "DEPARTMENT+TYPE"


class SlaService:
    @staticmethod
    def resolve_policy(
        db: Session,
        priority: str,
        department_id: uuid.UUID,
        requisition_type: str,
    ) -> SlaPolicy | None:
        """Devuelve la política activa más específica para la requisición."""
        rows = list(
            db.execute(
                select(SlaPolicy).where(
                    SlaPolicy.priority == priority,
                    SlaPolicy.is_active.is_(True),
                    SlaPolicy.requisition_type.in_((requisition_type, "ALL")),
                    SlaPolicy.department_key.in_((str(department_id), "ALL")),
                )
            ).scalars()
        )
        if not rows:
            return None
        rows.sort(
            key=lambda policy: (
                policy.department_id is not None,
                policy.requisition_type != "ALL",
            ),
            reverse=True,
        )
        return rows[0]

    @staticmethod
    def evaluate(
        db: Session,
        req: Requisition,
        *,
        now: datetime | None = None,
    ) -> dict:
        """Calcula el color sin persistir; nunca modifica el estado administrativo."""
        current = now or _now()
        base: dict = {
            "color": "NONE",
            "label": _LABELS["NONE"],
            "measured": False,
            "administrative_status": req.status,
            "policy_scope": "SIN_POLITICA",
            "emergency_active": False,
        }
        if req.status in ("DRAFT",) + SLA_TERMINAL_STATUSES:
            base["message"] = "El semáforo no aplica a borradores ni a documentos cerrados."
            return base

        policy = SlaService.resolve_policy(db, req.priority, req.department_id, req.requisition_type)
        if policy is None:
            base["message"] = "No hay una política SLA activa para esta combinación."
            return base

        emergency_active = bool(policy.emergency_enabled and req.priority == "URGENT")
        if emergency_active:
            green_hours = policy.emergency_green_hours
            yellow_hours = policy.emergency_yellow_hours
        else:
            green_hours = policy.green_hours
            yellow_hours = policy.yellow_hours

        start = req.submitted_at or req.created_at
        elapsed = Decimal((current - start).total_seconds()) / Decimal("3600")
        elapsed = elapsed.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        color: Literal["GREEN", "YELLOW", "RED"] = (
            "GREEN" if elapsed <= Decimal(green_hours)
            else "YELLOW" if elapsed <= Decimal(yellow_hours)
            else "RED"
        )
        return {
            "color": color,
            "label": _LABELS[color],
            "measured": True,
            "administrative_status": req.status,
            "base_at": start,
            "elapsed_hours": elapsed,
            "green_deadline": start + timedelta(hours=green_hours),
            "yellow_deadline": start + timedelta(hours=yellow_hours),
            "policy_id": policy.id,
            "policy_scope": policy.scope,
            "emergency_active": emergency_active,
            "message": None,
        }

    @staticmethod
    def record_snapshot(
        db: Session,
        req: Requisition,
        *,
        trigger: str,
        actor_id: uuid.UUID | None = None,
        now: datetime | None = None,
    ) -> dict:
        """Guarda una instantánea inmutable del color calculado."""
        result = SlaService.evaluate(db, req, now=now)
        event = RequisitionSlaEvent(
            requisition_id=req.id,
            base_at=result.get("base_at"),
            elapsed_hours=result.get("elapsed_hours"),
            color=result["color"],
            policy_id=result.get("policy_id"),
            policy_scope=result["policy_scope"],
            trigger=trigger,
            actor_id=actor_id,
            metadata_json={
                "administrative_status": req.status,
                "emergency_active": result["emergency_active"],
                "priority": req.priority,
                "requisition_type": req.requisition_type,
            },
        )
        db.add(event)
        emit(
            db,
            "Requisition",
            req.id,
            "REQUISITION_SLA_EVALUATED",
            {"color": result["color"], "trigger": trigger},
        )
        return result

    @staticmethod
    def history(
        db: Session,
        actor_id: uuid.UUID,
        requisition_id: uuid.UUID,
    ) -> list[dict]:
        req = db.get(Requisition, requisition_id)
        if req is None:
            _fail("Requisición inexistente.", status.HTTP_404_NOT_FOUND)
        IdentityService.assert_department_access(db, actor_id, req.department_id)
        rows = db.execute(
            select(RequisitionSlaEvent)
            .where(RequisitionSlaEvent.requisition_id == requisition_id)
            .order_by(RequisitionSlaEvent.occurred_at)
        ).scalars()
        return [
            {
                "id": event.id,
                "requisition_id": event.requisition_id,
                "occurred_at": event.occurred_at,
                "base_at": event.base_at,
                "elapsed_hours": event.elapsed_hours,
                "color": event.color,
                "label": _LABELS[event.color],
                "policy_id": event.policy_id,
                "policy_scope": event.policy_scope,
                "trigger": event.trigger,
                "actor_id": event.actor_id,
                "metadata_json": event.metadata_json,
            }
            for event in rows
        ]

    @staticmethod
    def _requisition_out(db: Session, req: Requisition) -> dict:
        return {
            "id": req.id,
            "document_no": req.document_no,
            "department_id": req.department_id,
            "status": req.status,
            "priority": req.priority,
            "requisition_type": req.requisition_type,
            "submitted_at": req.submitted_at,
            "needed_at": req.needed_at,
            "sla": SlaService.evaluate(db, req),
        }

    @staticmethod
    def list_requisitions(
        db: Session,
        actor_id: uuid.UUID,
        *,
        color: str | None = None,
        status_filter: str | None = None,
        priority: str | None = None,
        department_id: uuid.UUID | None = None,
    ) -> list[dict]:
        stmt = select(Requisition)
        if not IdentityService.is_admin(db, actor_id):
            stmt = stmt.where(Requisition.department_id.in_(IdentityService.department_ids(db, actor_id)))
        if status_filter:
            stmt = stmt.where(Requisition.status == status_filter)
        if priority:
            stmt = stmt.where(Requisition.priority == priority)
        if department_id is not None:
            stmt = stmt.where(Requisition.department_id == department_id)
        rows = db.execute(stmt.order_by(Requisition.created_at.desc())).scalars()
        result = [SlaService._requisition_out(db, req) for req in rows]
        if color:
            result = [item for item in result if item["sla"]["color"] == color]
        return result

    @staticmethod
    def get_requisition(db: Session, actor_id: uuid.UUID, requisition_id: uuid.UUID) -> dict:
        req = db.get(Requisition, requisition_id)
        if req is None:
            _fail("Requisición inexistente.", status.HTTP_404_NOT_FOUND)
        IdentityService.assert_department_access(db, actor_id, req.department_id)
        return SlaService._requisition_out(db, req)

    @staticmethod
    def evaluate_active(
        db: Session,
        actor_id: uuid.UUID,
        *,
        department_id: uuid.UUID | None = None,
    ) -> list[dict]:
        """Evalúa de forma explícita las requisiciones medibles y guarda historial."""
        stmt = select(Requisition).where(Requisition.status.in_(_ACTIVE_STATUSES))
        if not IdentityService.is_admin(db, actor_id):
            stmt = stmt.where(Requisition.department_id.in_(IdentityService.department_ids(db, actor_id)))
        if department_id is not None:
            stmt = stmt.where(Requisition.department_id == department_id)
        rows = db.execute(stmt.order_by(Requisition.created_at)).scalars()
        return [
            SlaService.record_snapshot(db, req, trigger="MANUAL", actor_id=actor_id)
            for req in rows
        ]

    @staticmethod
    def list_policies(db: Session) -> list[SlaPolicy]:
        return list(
            db.execute(
                select(SlaPolicy).order_by(SlaPolicy.priority, SlaPolicy.department_key, SlaPolicy.requisition_type)
            ).scalars()
        )

    @staticmethod
    def create_policy(db: Session, actor_id: uuid.UUID, payload) -> SlaPolicy:
        if payload.department_id is not None and db.get(Department, payload.department_id) is None:
            _fail("Departamento inexistente.", status.HTTP_404_NOT_FOUND)
        department_key = str(payload.department_id) if payload.department_id else "ALL"
        exists = db.execute(
            select(SlaPolicy.id).where(
                SlaPolicy.priority == payload.priority,
                SlaPolicy.department_key == department_key,
                SlaPolicy.requisition_type == payload.requisition_type,
            )
        ).first()
        if exists is not None:
            _fail("Ya existe una política para ese alcance.")
        policy = SlaPolicy(
            priority=payload.priority,
            department_key=department_key,
            department_id=payload.department_id,
            requisition_type=payload.requisition_type,
            green_hours=payload.green_hours,
            yellow_hours=payload.yellow_hours,
            is_active=payload.is_active,
            scope=_scope(payload.department_id, payload.requisition_type),
            evidence=payload.evidence,
            notes=payload.notes,
            created_by=actor_id,
        )
        db.add(policy)
        db.flush()
        AuditService.record(
            db,
            action="SLA_POLICY_CREATE",
            entity_type="SlaPolicy",
            entity_id=policy.id,
            actor_id=actor_id,
            after={
                "priority": policy.priority,
                "scope": policy.scope,
                "green_hours": policy.green_hours,
                "yellow_hours": policy.yellow_hours,
            },
            detail=payload.evidence,
        )
        emit(db, "SlaPolicy", policy.id, "SLA_POLICY_CREATED", {"scope": policy.scope})
        return policy

    @staticmethod
    def update_policy(db: Session, actor_id: uuid.UUID, policy_id: uuid.UUID, payload) -> SlaPolicy:
        policy = db.execute(
            select(SlaPolicy).where(SlaPolicy.id == policy_id).with_for_update()
        ).scalar_one_or_none()
        if policy is None:
            _fail("Política SLA inexistente.", status.HTTP_404_NOT_FOUND)
        before = {
            "green_hours": policy.green_hours,
            "yellow_hours": policy.yellow_hours,
            "is_active": policy.is_active,
            "evidence": policy.evidence,
            "notes": policy.notes,
        }
        green = payload.green_hours if payload.green_hours is not None else policy.green_hours
        yellow = payload.yellow_hours if payload.yellow_hours is not None else policy.yellow_hours
        if yellow <= green:
            _fail("El plazo amarillo debe ser mayor al verde.", status.HTTP_422_UNPROCESSABLE_ENTITY)
        policy.green_hours = green
        policy.yellow_hours = yellow
        if payload.is_active is not None:
            policy.is_active = payload.is_active
        if payload.evidence is not None:
            policy.evidence = payload.evidence
        if payload.notes is not None:
            policy.notes = payload.notes
        policy.updated_by = actor_id
        policy.version += 1
        AuditService.record(
            db,
            action="SLA_POLICY_UPDATE",
            entity_type="SlaPolicy",
            entity_id=policy.id,
            actor_id=actor_id,
            before=before,
            after={
                "green_hours": policy.green_hours,
                "yellow_hours": policy.yellow_hours,
                "is_active": policy.is_active,
                "evidence": policy.evidence,
                "notes": policy.notes,
            },
        )
        emit(db, "SlaPolicy", policy.id, "SLA_POLICY_UPDATED", {"scope": policy.scope})
        return policy

    @staticmethod
    def set_emergency(db: Session, actor_id: uuid.UUID, policy_id: uuid.UUID, payload) -> SlaPolicy:
        """Activa o desactiva emergencia con aprobación explícita y auditada."""
        policy = db.execute(
            select(SlaPolicy).where(SlaPolicy.id == policy_id).with_for_update()
        ).scalar_one_or_none()
        if policy is None:
            _fail("Política SLA inexistente.", status.HTTP_404_NOT_FOUND)
        before = {
            "emergency_enabled": policy.emergency_enabled,
            "emergency_green_hours": policy.emergency_green_hours,
            "emergency_yellow_hours": policy.emergency_yellow_hours,
            "emergency_approved_at": str(policy.emergency_approved_at),
        }
        if payload.enabled:
            green = payload.green_hours or policy.emergency_green_hours
            yellow = payload.yellow_hours or policy.emergency_yellow_hours
            if yellow <= green:
                _fail(
                    "El plazo amarillo de emergencia debe ser mayor al verde.",
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                )
            policy.emergency_green_hours = green
            policy.emergency_yellow_hours = yellow
            policy.emergency_enabled = True
            policy.emergency_approved_by = actor_id
            policy.emergency_approved_at = _now()
        else:
            policy.emergency_enabled = False
            policy.emergency_approved_by = None
            policy.emergency_approved_at = None
        policy.evidence = payload.reason
        policy.updated_by = actor_id
        policy.version += 1
        AuditService.record(
            db,
            action="SLA_EMERGENCY_APPROVE" if payload.enabled else "SLA_EMERGENCY_DISABLE",
            entity_type="SlaPolicy",
            entity_id=policy.id,
            actor_id=actor_id,
            before=before,
            after={
                "emergency_enabled": policy.emergency_enabled,
                "emergency_green_hours": policy.emergency_green_hours,
                "emergency_yellow_hours": policy.emergency_yellow_hours,
                "emergency_approved_at": str(policy.emergency_approved_at),
            },
            detail=payload.reason,
        )
        emit(
            db,
            "SlaPolicy",
            policy.id,
            "SLA_EMERGENCY_ENABLED" if payload.enabled else "SLA_EMERGENCY_DISABLED",
            {"reason": payload.reason},
        )
        return policy
