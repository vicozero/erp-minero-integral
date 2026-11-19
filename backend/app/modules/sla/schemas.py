from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SlaPolicyIn(BaseModel):
    priority: Literal["LOW", "NORMAL", "HIGH", "URGENT"]
    department_id: uuid.UUID | None = None
    requisition_type: Literal["ALL", "STOCK", "PURCHASE", "SERVICE"] = "ALL"
    green_hours: int = Field(gt=0, le=8760)
    yellow_hours: int = Field(gt=0, le=8760)
    is_active: bool = True
    evidence: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def _orden_de_umbrales(self) -> "SlaPolicyIn":
        if self.yellow_hours <= self.green_hours:
            raise ValueError("yellow_hours debe ser mayor que green_hours")
        return self


class SlaPolicyUpdate(BaseModel):
    green_hours: int | None = Field(default=None, gt=0, le=8760)
    yellow_hours: int | None = Field(default=None, gt=0, le=8760)
    is_active: bool | None = None
    evidence: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=1000)


class EmergencyApprovalIn(BaseModel):
    enabled: bool
    reason: str = Field(min_length=8, max_length=500)
    green_hours: int | None = Field(default=None, gt=0, le=8760)
    yellow_hours: int | None = Field(default=None, gt=0, le=8760)

    @model_validator(mode="after")
    def _orden_de_emergencia(self) -> "EmergencyApprovalIn":
        if not self.enabled:
            return self
        green = self.green_hours or 4
        yellow = self.yellow_hours or 8
        if yellow <= green:
            raise ValueError("El plazo amarillo de emergencia debe ser mayor al verde")
        return self


class SlaPolicyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    priority: str
    department_id: uuid.UUID | None
    requisition_type: str
    scope: str
    green_hours: int
    yellow_hours: int
    is_active: bool
    emergency_enabled: bool
    emergency_green_hours: int
    emergency_yellow_hours: int
    emergency_approved_by: uuid.UUID | None
    emergency_approved_at: datetime | None
    evidence: str | None
    notes: str | None
    created_at: datetime


class SlaResult(BaseModel):
    color: Literal["GREEN", "YELLOW", "RED", "NONE"]
    label: str
    measured: bool
    administrative_status: str
    base_at: datetime | None = None
    elapsed_hours: Decimal | None = None
    green_deadline: datetime | None = None
    yellow_deadline: datetime | None = None
    policy_id: uuid.UUID | None = None
    policy_scope: str = "SIN_POLITICA"
    emergency_active: bool = False
    message: str | None = None


class SlaEvaluationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    requisition_id: uuid.UUID
    occurred_at: datetime
    base_at: datetime | None
    elapsed_hours: Decimal | None
    color: str
    label: str
    policy_id: uuid.UUID | None
    policy_scope: str
    trigger: str
    actor_id: uuid.UUID | None
    metadata_json: dict | None = None


class SlaRequisitionOut(BaseModel):
    id: uuid.UUID
    document_no: str
    department_id: uuid.UUID
    status: str
    priority: str
    requisition_type: str
    submitted_at: datetime | None
    needed_at: datetime | None
    sla: SlaResult
