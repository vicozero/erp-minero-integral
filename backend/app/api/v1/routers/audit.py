from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.deps import require_permission
from app.db.session import get_db
from app.modules.audit.models import AuditLog
from app.modules.identity.models import AppUser
from app.modules.identity.schemas import AuditEntryOut
from app.modules.identity.service import IdentityService

router = APIRouter(prefix="/audit", tags=["Bitácora"])

# Solo lectura: no existen endpoints para modificar o borrar auditoría, y la
# base de datos dispone de un trigger que bloquea UPDATE/DELETE.


@router.get("", response_model=list[AuditEntryOut])
def list_audit(
    limit: int = Query(default=100, ge=1, le=500),
    action: str | None = Query(default=None, max_length=80),
    actor: AppUser = Depends(require_permission("auditoria.consultar")),
    db: Session = Depends(get_db),
) -> list[dict]:
    stmt = select(AuditLog).order_by(AuditLog.occurred_at.desc())
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if not IdentityService.has_permission(db, actor.id, "audit.view_all"):
        if not (IdentityService.is_admin(db, actor.id) or IdentityService.has_permission(db, actor.id, "audit.view")):
            stmt = stmt.where(AuditLog.actor_id == actor.id)
    entries = db.execute(stmt.limit(limit)).scalars()
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
