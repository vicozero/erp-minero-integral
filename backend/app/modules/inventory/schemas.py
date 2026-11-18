from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, ConfigDict


class AvailabilityOut(BaseModel):
    item_id: uuid.UUID
    item_code: str
    warehouse_id: uuid.UUID
    warehouse_code: str
    on_hand_qty: Decimal
    reserved_qty: Decimal
    available_qty: Decimal


class ReserveIn(BaseModel):
    requisition_line_id: uuid.UUID
    quantity: Decimal = Field(gt=0)
    idempotency_key: str | None = Field(default=None, max_length=160)


class ReservationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    reservation_no: str
    requisition_line_id: uuid.UUID
    item_id: uuid.UUID
    warehouse_id: uuid.UUID
    quantity: Decimal
    consumed_qty: Decimal
    status: str
    expires_at: datetime


class IssueIn(BaseModel):
    requisition_line_id: uuid.UUID
    quantity: Decimal = Field(gt=0)
    reservation_id: uuid.UUID | None = None
    idempotency_key: str | None = Field(default=None, max_length=160)


class MovementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    movement_no: str
    movement_type: str
    direction: str
    quantity: Decimal
    item_id: uuid.UUID
    warehouse_id: uuid.UUID
    balance_after_qty: Decimal
    requisition_line_id: uuid.UUID | None
    source_document_type: str
    posted_at: datetime
