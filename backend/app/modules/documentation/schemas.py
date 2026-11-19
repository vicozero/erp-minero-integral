from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class VoucherLineIn(BaseModel):
    requisition_line_id: uuid.UUID | None = None
    item_id: uuid.UUID | None = None
    item_code: str = Field(min_length=1, max_length=60)
    uom_code: str = Field(min_length=1, max_length=20)
    description: str = Field(min_length=1, max_length=255)
    requested_qty: Decimal = Field(ge=0, max_digits=18, decimal_places=6)
    dispatched_qty: Decimal = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=6)


class VoucherCreate(BaseModel):
    department_id: uuid.UUID
    warehouse_id: uuid.UUID | None = None
    requisition_id: uuid.UUID | None = None
    mode: Literal["DRAFT", "DELIVERY"] = "DRAFT"
    cost_center_code: str | None = Field(default=None, max_length=60)
    area: str | None = Field(default=None, max_length=120)
    usage_equipment: str | None = Field(default=None, max_length=255)
    issue_date: date | None = None
    lines: list[VoucherLineIn] | None = None
    idempotency_key: str | None = Field(default=None, max_length=160)


class VoucherLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    line_no: int
    requisition_line_id: uuid.UUID | None
    stock_movement_id: uuid.UUID | None
    item_id: uuid.UUID | None
    item_code: str
    uom_code: str
    description: str
    requested_qty: Decimal
    dispatched_qty: Decimal


class VoucherOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_no: str
    department_id: uuid.UUID
    warehouse_id: uuid.UUID | None
    source_requisition_id: uuid.UUID | None
    cost_center_code: str | None
    area: str | None
    usage_equipment: str | None
    issue_date: date
    status: str
    template_code: str
    template_version: int
    issued_at: datetime | None
    created_at: datetime
    lines: list[VoucherLineOut] = []


class RenderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_no: str
    document_format: str
    sha256: str
    size_bytes: int
    is_reprint: bool
    rendered_at: datetime
    source_render_id: uuid.UUID | None
