from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.deps import require_permission
from app.db.session import get_db
from app.modules.costing.models import CostCenter
from app.modules.identity.models import AppUser
from app.modules.maintenance.models import Equipment
from app.modules.master_data.models import Item, Supplier, Uom
from app.modules.organization.models import Department, MiningUnit, Warehouse

router = APIRouter(prefix="/catalogs", tags=["Catálogos"])


@router.get("")
def catalogs(
    db: Session = Depends(get_db),
    _actor: AppUser = Depends(require_permission("requisition.view")),
) -> dict:
    def rows(model, active_only: bool = False):
        stmt = db.query(model)
        if active_only and hasattr(model, "is_active"):
            stmt = stmt.filter(model.is_active.is_(True))
        return [
            {
                "id": str(obj.id),
                "code": getattr(obj, "code", None),
                "name": getattr(obj, "name", None)
                or getattr(obj, "description", None)
                or getattr(obj, "full_name", None)
                or getattr(obj, "asset_tag", None),
            }
            for obj in stmt.order_by(model.created_at).all()
        ]

    return {
        "mining_units": rows(MiningUnit),
        "departments": rows(Department),
        "warehouses": rows(Warehouse),
        "items": rows(Item, active_only=True),
        "uoms": rows(Uom),
        "suppliers": rows(Supplier),
        "cost_centers": rows(CostCenter, active_only=True),
        "equipment": rows(Equipment),
    }
