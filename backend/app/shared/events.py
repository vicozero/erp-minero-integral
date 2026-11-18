from __future__ import annotations

import json
import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from app.modules.integrations.models import OutboxEvent


def _default(value: object) -> str:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    return str(value)


def emit(
    db: Session,
    aggregate_type: str,
    aggregate_id: uuid.UUID,
    event_type: str,
    payload: dict | None = None,
) -> OutboxEvent:
    safe_payload = json.loads(json.dumps(payload or {}, default=_default))
    event = OutboxEvent(
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        event_type=event_type,
        payload=safe_payload,
    )
    db.add(event)
    return event
