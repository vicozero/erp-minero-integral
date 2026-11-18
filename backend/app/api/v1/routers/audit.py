from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.deps import require_permission
from app.db.session import get_db
from app.modules.audit.models import AuditLog
from app.modules.identity.models import AppUser

router = APIRouter(prefix="/audit", tags=["Bitácora"])


@router.get("")
def list_audit(
    limit: int = 100,
    db: Session = Depends(get_db),
    _actor: AppUser = Depends(require_permission("audit.view")),
) -> list[dict]:
    entries = db.query(AuditLog).order_by(AuditLog.occurred_at.desc()).limit(limit).all()
    return [
        {
            "id": str(entry.id),
            "occurred_at": entry.occurred_at,
            "actor_username": entry.actor_username,
            "action": entry.action,
            "entity_type": entry.entity_type,
            "entity_id": str(entry.entity_id) if entry.entity_id else None,
            "detail": entry.detail,
            "request_id": entry.request_id,
        }
        for entry in entries
    ]
