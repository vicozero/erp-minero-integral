from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import NoReturn

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.context import current_request_id
from app.modules.documentation.models import IdempotencyRecord


class IdempotencyError(HTTPException):
    pass


def _fail(detail: str, code: int = status.HTTP_409_CONFLICT) -> NoReturn:
    raise IdempotencyError(status_code=code, detail=detail)


def acquire(
    db: Session,
    key: str,
    *,
    operation: str,
    entity_type: str,
    request_id: str | None = None,
) -> tuple[IdempotencyRecord, bool]:
    """Reclama una clave de idempotencia de forma atómica.

    Devuelve ``(registro, creado)``. La inserción con ``ON CONFLICT DO NOTHING
    RETURNING`` bloquea hasta que la transacción concurrente finalice: si la
    otra operación confirmó, se lee el registro existente; si revertió, esta
    inserción prevalece. No se usa el patrón SELECT-then-INSERT.
    """
    if not key or len(key) < 3 or len(key) > 160:
        _fail("La clave de idempotencia debe tener entre 3 y 160 caracteres.", status.HTTP_422_UNPROCESSABLE_ENTITY)

    stmt = (
        insert(IdempotencyRecord)
        .values(
            id=uuid.uuid4(),
            idempotency_key=key,
            operation=operation,
            entity_type=entity_type,
            request_id=(request_id or current_request_id())[:120],
            status="IN_PROGRESS",
            created_at=datetime.now(timezone.utc),
        )
        .on_conflict_do_nothing(index_elements=["idempotency_key"])
        .returning(IdempotencyRecord)
    )
    record = db.execute(stmt).scalar_one_or_none()
    if record is not None:
        return record, True

    existing = db.execute(
        select(IdempotencyRecord).where(IdempotencyRecord.idempotency_key == key)
    ).scalar_one_or_none()
    if existing is None:  #pragma: no cover - sólo posible ante fallo de BD
        _fail("No fue posible reclamar la clave de idempotencia.")
    if existing.operation != operation:
        _fail("La clave de idempotencia pertenece a otra operación.")
    return existing, False


def complete(db: Session, record: IdempotencyRecord, entity_id: uuid.UUID) -> IdempotencyRecord:
    record.entity_id = entity_id
    record.status = "COMPLETED"
    record.completed_at = datetime.now(timezone.utc)
    db.flush()
    return record


def existing_entity_id(db: Session, key: str, operation: str) -> uuid.UUID:
    """Devuelve la entidad de una operación ya confirmada o falla con 409."""
    record = db.execute(
        select(IdempotencyRecord).where(IdempotencyRecord.idempotency_key == key)
    ).scalar_one_or_none()
    if record is None or record.operation != operation or record.entity_id is None:
        _fail("La operación con esa clave aún no está disponible.")
    return record.entity_id
