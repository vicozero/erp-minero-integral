from __future__ import annotations

import hashlib
import json
import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.context import current_request_id
from app.modules.audit.models import AuditLog


def _json_safe(value: object | None) -> dict | None:
    if value is None:
        return None
    return json.loads(json.dumps(value, default=_default))


def _default(value: object) -> str:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    return str(value)


def hash_ip(ip: str | None) -> str | None:
    if not ip:
        return None
    return hashlib.sha256(ip.encode("utf-8")).hexdigest()[:64]


class AuditService:
    @staticmethod
    def record(
        db: Session,
        action: str,
        entity_type: str,
        entity_id: uuid.UUID | None = None,
        *,
        actor_id: uuid.UUID | None = None,
        actor_username: str | None = None,
        before: object | None = None,
        after: object | None = None,
        detail: str | None = None,
        ip_hash: str | None = None,
        request_id: str | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_id=actor_id,
            actor_username=actor_username,
            before_json=_json_safe(before),
            after_json=_json_safe(after),
            detail=detail,
            ip_hash=ip_hash,
            request_id=request_id or current_request_id(),
        )
        db.add(entry)
        return entry
