"""Dominio del semáforo SLA de requisiciones.

El color es un indicador calculado en backend. No sustituye al estado
administrativo de la requisición ni dispara movimientos de inventario.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, JSON_DICT
from app.shared.constants import SLA_COLORS, SLA_POLICY_SCOPES

_DEPARTMENT_ALL = "ALL"
_TYPE_ALL = "ALL"


class SlaPolicy(AuditMixin, Base):
    """Política de plazos por prioridad, departamento y tipo de requisición.

    Los umbrales se guardan en horas de reloj. El modo emergencia se almacena
    pero no se aplica hasta que un actor con permiso ``sla.policy.approve``
    registre ``emergency_approved_by`` y ``emergency_approved_at``.
    """

    __tablename__ = "sla_policy"
    __table_args__ = (
        CheckConstraint(
            "priority IN ('LOW','NORMAL','HIGH','URGENT')", name="ck_sla_policy_priority"
        ),
        CheckConstraint(
            "requisition_type IN ('ALL','STOCK','PURCHASE','SERVICE')",
            name="ck_sla_policy_requisition_type",
        ),
        CheckConstraint("yellow_hours > green_hours", name="ck_sla_policy_horas"),
        CheckConstraint(
            "emergency_yellow_hours > emergency_green_hours",
            name="ck_sla_policy_horas_emergencia",
        ),
        CheckConstraint(
            "NOT emergency_enabled OR "
            "(emergency_approved_by IS NOT NULL AND emergency_approved_at IS NOT NULL)",
            name="ck_sla_policy_emergencia_aprobada",
        ),
        UniqueConstraint(
            "priority", "department_key", "requisition_type", name="uq_sla_policy_scope"
        ),
        {"schema": "req"},
    )

    priority: Mapped[str] = mapped_column(String(20), nullable=False)
    # 'ALL' representa ámbito global; la clave derivada hace única la combinación
    # aunque PostgreSQL trate NULL como distinto en restricciones de unicidad.
    department_key: Mapped[str] = mapped_column(String(36), nullable=False, default=_DEPARTMENT_ALL)
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("org.department.id", ondelete="RESTRICT"), nullable=True
    )
    requisition_type: Mapped[str] = mapped_column(String(20), nullable=False, default=_TYPE_ALL)
    green_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    yellow_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    emergency_enabled: Mapped[bool] = mapped_column(default=False, nullable=False)
    emergency_green_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    emergency_yellow_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=8)
    emergency_approved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("seg.app_user.id", ondelete="RESTRICT"), nullable=True
    )
    emergency_approved_at: Mapped[datetime | None] = mapped_column(nullable=True)
    scope: Mapped[str] = mapped_column(String(40), nullable=False, default="GLOBAL")
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class RequisitionSlaEvent(Base):
    """Instantánea append-only del semáforo de una requisición."""

    __tablename__ = "requisition_sla_event"
    __table_args__ = (
        CheckConstraint("color IN ('" + "','".join(SLA_COLORS) + "')", name="ck_sla_event_color"),
        Index("ix_requisition_sla_event_history", "requisition_id", "occurred_at"),
        Index("ix_requisition_sla_event_color", "occurred_at", "color"),
        {"schema": "req"},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    occurred_at: Mapped[datetime] = mapped_column(default=func.now(), nullable=False)
    requisition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("req.requisition.id", ondelete="RESTRICT"), nullable=False
    )
    base_at: Mapped[datetime | None] = mapped_column(nullable=True)
    elapsed_hours: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    color: Mapped[str] = mapped_column(String(10), nullable=False)
    policy_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("req.sla_policy.id", ondelete="RESTRICT"), nullable=True
    )
    policy_scope: Mapped[str] = mapped_column(String(120), nullable=False)
    trigger: Mapped[str] = mapped_column(String(30), nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("seg.app_user.id", ondelete="RESTRICT"), nullable=True
    )
    metadata_json: Mapped[dict | None] = mapped_column(JSON_DICT, nullable=True)


__all__ = [
    "SlaPolicy",
    "RequisitionSlaEvent",
    "SLA_POLICY_SCOPES",
]
