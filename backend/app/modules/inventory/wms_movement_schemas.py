"""Contratos Pydantic del Lote B WMS.

B.0 define únicamente la forma de entrada/salida de los movimientos. No hay
servicios, endpoints ni reglas de negocio asociadas: las operaciones que
dependen de decisiones pendientes (devolución vs ``line_delivered_qty``,
autorizador de cuarentena, vencimientos y política FEFO/FIFO) no se
implementan aquí.

Cantidades e importes usan siempre ``Decimal``; nunca ``float``.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

class MovementDirection(str, Enum):
    IN = "IN"
    OUT = "OUT"


class StockState(str, Enum):
    AVAILABLE = "AVAILABLE"
    QUARANTINE = "QUARANTINE"
    INSPECTION = "INSPECTION"
    BLOCKED = "BLOCKED"
    DAMAGED = "DAMAGED"
    IN_TRANSIT = "IN_TRANSIT"
    SCRAP = "SCRAP"


class ReceiptSource(str, Enum):
    GOODS_RECEIPT = "GOODS_RECEIPT"
    RETURN = "RETURN"
    ADJUSTMENT_IN = "ADJUSTMENT_IN"
    INITIAL = "INITIAL"


class WmsMovementBaseIn(BaseModel):
    """Campos compartidos por toda operación de movimiento WMS."""

    warehouse_id: uuid.UUID
    item_id: uuid.UUID
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=6)
    lot_ref_id: uuid.UUID | None = None
    serial_id: uuid.UUID | None = None
    location_ref_id: uuid.UUID | None = None
    occurred_at: datetime | None = None
    idempotency_key: str = Field(min_length=3, max_length=160)


class ReceiptIn(WmsMovementBaseIn):
    """Entrada de mercado, devolución o ajuste controlado."""

    source_document_type: ReceiptSource = ReceiptSource.GOODS_RECEIPT
    source_document_id: uuid.UUID | None = None
    source_line_id: uuid.UUID | None = None
    stock_state: StockState = StockState.AVAILABLE
    unit_cost: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=4)
    movement_order_line_id: uuid.UUID | None = None


class IssueInWms(WmsMovementBaseIn):
    """Salida enriquecida desde una partida de requisición autorizada."""

    requisition_line_id: uuid.UUID
    stock_state: StockState = StockState.AVAILABLE
    delivery_seq: int | None = Field(default=None, gt=0)
    movement_order_line_id: uuid.UUID | None = None


class ReturnIn(WmsMovementBaseIn):
    """Devolución enlazada a un ISSUE existente.

    La devolución no revierte la entrega: es una entrada nueva con documento
    propio. El efecto sobre ``line_delivered_qty`` queda pendiente de decisión
    empresarial y no se expresa en este contrato.
    """

    return_of_movement_id: uuid.UUID
    stock_state: StockState = StockState.INSPECTION
    return_seq: int | None = Field(default=None, gt=0)


class ReversalIn(BaseModel):
    """Reverso completo de un movimiento ya confirmado.

    La aprobación es opcional en el contrato porque depende del tipo de
    movimiento y del autorizador formal, aún no definido para cuarentena.
    """

    movement_id: uuid.UUID
    reason: str = Field(min_length=3, max_length=500)
    idempotency_key: str = Field(min_length=3, max_length=160)
    approved_by: uuid.UUID | None = None


class MovementOrderLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    line_no: int
    item_id: uuid.UUID
    warehouse_id: uuid.UUID
    quantity: Decimal
    issued_qty: Decimal
    received_qty: Decimal
    status: str
    idempotency_key: str | None = None


class MovementOrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_no: str
    order_type: str
    status: str
    warehouse_id: uuid.UUID
    source_document_type: str | None = None
    source_document_id: uuid.UUID | None = None
    created_at: datetime
    lines: tuple[MovementOrderLineOut, ...] = ()


class KardexEntryOut(BaseModel):
    """Fila de kardex derivada de ``inv.stock_movement`` (sin tabla duplicada)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    movement_no: str
    posted_at: datetime
    occurred_at: datetime
    movement_type: str
    direction: str
    quantity: Decimal
    item_id: uuid.UUID
    item_code: str | None = None
    warehouse_id: uuid.UUID
    warehouse_code: str | None = None
    location_ref_id: uuid.UUID | None = None
    location_code: str | None = None
    zone: str | None = None
    lot_ref_id: uuid.UUID | None = None
    lot_number: str | None = None
    serial_id: uuid.UUID | None = None
    serial_number: str | None = None
    stock_state: str | None = None
    balance_after_qty: Decimal
    scope_balance_after_qty: Decimal | None = None
    signed_running_qty: Decimal | None = None
    source_document_type: str | None = None
    source_document_id: uuid.UUID | None = None
    document_no: str | None = None
    requisition_line_id: uuid.UUID | None = None
    equipment_id: uuid.UUID | None = None
    cost_center_id: uuid.UUID | None = None
    work_order_no: str | None = None
    requester_id: uuid.UUID | None = None
    created_by: uuid.UUID | None = None
    reversal_of_id: uuid.UUID | None = None
    return_of_movement_id: uuid.UUID | None = None
    movement_group_id: uuid.UUID | None = None
    unit_cost: Decimal | None = None
    total_cost: Decimal | None = None
