from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RequisitionDraftUpdate(BaseModel):
    priority: Literal["LOW", "NORMAL", "HIGH", "URGENT"] = "NORMAL"
    justification: str = Field(min_length=4, max_length=1000)
    observations: str | None = Field(default=None, max_length=1000)
    needed_at: datetime | None = None


class RequisitionLineIn(BaseModel):
    item_id: uuid.UUID | None = None
    description: str = Field(min_length=2, max_length=255)
    uom_id: uuid.UUID
    requested_qty: Decimal = Field(gt=0)
    notes: str | None = Field(default=None, max_length=500)


class RequisitionCreate(BaseModel):
    department_id: uuid.UUID
    warehouse_id: uuid.UUID | None = None
    equipment_id: uuid.UUID | None = None
    cost_center_id: uuid.UUID
    requisition_type: Literal["STOCK", "PURCHASE", "SERVICE"] = "STOCK"
    priority: Literal["LOW", "NORMAL", "HIGH", "URGENT"] = "NORMAL"
    justification: str = Field(min_length=4, max_length=1000)
    observations: str | None = Field(default=None, max_length=1000)
    needed_at: datetime | None = None
    lines: list[RequisitionLineIn] = Field(min_length=1)


class RequisitionLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    line_no: int
    item_id: uuid.UUID | None
    description: str
    uom_id: uuid.UUID
    requested_qty: Decimal
    authorised_qty: Decimal
    cancelled_qty: Decimal
    status: str
    notes: str | None
    reserved_qty: Decimal = Decimal("0")
    purchased_qty: Decimal = Decimal("0")
    received_qty: Decimal = Decimal("0")
    delivered_qty: Decimal = Decimal("0")
    pending_qty: Decimal = Decimal("0")


class RequisitionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_no: str
    department_id: uuid.UUID
    warehouse_id: uuid.UUID | None
    equipment_id: uuid.UUID | None
    cost_center_id: uuid.UUID
    requisition_type: str
    priority: str
    status: str
    justification: str
    observations: str | None
    needed_at: datetime | None
    submitted_at: datetime | None
    approved_at: datetime | None
    rejected_at: datetime | None
    rejection_reason: str | None
    created_at: datetime
    lines: list[RequisitionLineOut] = []


class DecisionIn(BaseModel):
    requisition_line_id: uuid.UUID
    decision: Literal["APPROVE", "REJECT"]
    approved_qty: Decimal = Field(default=Decimal("0"), ge=0)
    reason: str | None = Field(default=None, max_length=500)


class DecisionRequest(BaseModel):
    decisions: list[DecisionIn] = Field(min_length=1)
    reason: str | None = Field(default=None, max_length=500)
