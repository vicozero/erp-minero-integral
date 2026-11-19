from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class PurchaseFromShortagesIn(BaseModel):
    requisition_id: uuid.UUID
    supplier_id: uuid.UUID
    warehouse_id: uuid.UUID
    notes: str | None = None
    idempotency_key: str | None = Field(default=None, min_length=3, max_length=160)


class PurchaseOrderLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    line_no: int
    requisition_line_id: uuid.UUID
    item_id: uuid.UUID
    ordered_qty: Decimal
    received_qty: Decimal
    cancelled_qty: Decimal
    unit_price: Decimal


class PurchaseOrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_no: str
    requisition_id: uuid.UUID
    supplier_id: uuid.UUID
    warehouse_id: uuid.UUID
    status: str
    lines: list[PurchaseOrderLineOut] = []


class PurchaseOrderCancelIn(BaseModel):
    reason: str = Field(min_length=4, max_length=500)


class ReceiptLineIn(BaseModel):
    purchase_order_line_id: uuid.UUID
    quantity: Decimal = Field(gt=0)


class ReceiptIn(BaseModel):
    lines: list[ReceiptLineIn] = Field(min_length=1)
    idempotency_key: str = Field(min_length=3, max_length=160)
