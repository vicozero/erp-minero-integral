from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.v1.deps import require_permission
from app.db.session import get_db
from app.modules.documentation.models import DocumentRender, WarehouseVoucher
from app.modules.documentation.schemas import (
    RenderOut,
    VoucherCreate,
    VoucherOut,
    VoucherSignatureIn,
)
from app.modules.documentation.service import DocumentationService as Service
from app.modules.identity.models import AppUser
from app.modules.identity.service import IdentityService
from app.modules.requisitions.models import Requisition

router = APIRouter(prefix="/documents", tags=["Documentos"])

_MEDIA_TYPES = {
    "PDF": "application/pdf",
    "XLSX": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def _attachment_headers(document_no: str, document_format: str, *, reprint: bool) -> dict[str, str]:
    extension = "pdf" if document_format == "PDF" else "xlsx"
    suffix = "_reimpresion" if reprint else ""
    filename = f"{document_no}{suffix}.{extension}"
    disposition = "inline" if document_format == "PDF" else "attachment"
    return {
        "Content-Disposition": f'{disposition}; filename="{filename}"',
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
    }


@router.post("/vouchers", response_model=VoucherOut, status_code=status.HTTP_201_CREATED)
def create_voucher(
    payload: VoucherCreate,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("warehouse.voucher.create")),
) -> dict:
    voucher = Service.create_voucher(db, actor.id, payload)
    db.commit()
    db.refresh(voucher)
    return Service.to_out(voucher)


@router.get("/vouchers", response_model=list[VoucherOut])
def list_vouchers(
    status_filter: str | None = Query(default=None, alias="status"),
    department_id: uuid.UUID | None = None,
    requisition_id: uuid.UUID | None = None,
    document_no: str | None = None,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("document.render")),
) -> list[dict]:
    stmt = select(WarehouseVoucher)
    if not IdentityService.is_admin(db, actor.id):
        allowed = IdentityService.department_ids(db, actor.id)
        allowed_warehouses = IdentityService.allowed_warehouse_ids(db, actor.id)
        stmt = stmt.where(WarehouseVoucher.department_id.in_(allowed))
        stmt = stmt.where(
            or_(
                WarehouseVoucher.warehouse_id.is_(None),
                WarehouseVoucher.warehouse_id.in_(allowed_warehouses or []),
            )
        )
    if status_filter:
        stmt = stmt.where(WarehouseVoucher.status == status_filter)
    if department_id is not None:
        stmt = stmt.where(WarehouseVoucher.department_id == department_id)
    if requisition_id is not None:
        stmt = stmt.where(WarehouseVoucher.source_requisition_id == requisition_id)
    if document_no:
        stmt = stmt.where(WarehouseVoucher.document_no.ilike(f"%{document_no}%"))
    vouchers = db.execute(stmt.order_by(WarehouseVoucher.created_at.desc())).scalars()
    return [Service.to_out(voucher) for voucher in vouchers]


@router.get("/vouchers/{voucher_id}", response_model=VoucherOut)
def get_voucher(
    voucher_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("document.render")),
) -> dict:
    voucher = db.get(WarehouseVoucher, voucher_id)
    if voucher is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vale inexistente.")
    IdentityService.assert_department_access(db, actor.id, voucher.department_id)
    if voucher.warehouse_id is not None:
        IdentityService.assert_warehouse_access(db, actor.id, voucher.warehouse_id)
    return Service.to_out(voucher)


@router.post("/vouchers/{voucher_id}/issue", response_model=VoucherOut)
def issue_voucher(
    voucher_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("warehouse.voucher.issue")),
) -> dict:
    voucher = Service.issue_voucher(db, actor.id, voucher_id)
    db.commit()
    db.refresh(voucher)
    return Service.to_out(voucher)


@router.post("/vouchers/{voucher_id}/signatures", response_model=VoucherOut)
def record_voucher_signatures(
    voucher_id: uuid.UUID,
    payload: VoucherSignatureIn,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("warehouse.voucher.issue")),
) -> dict:
    voucher = Service.record_signatures(db, actor.id, voucher_id, payload)
    db.commit()
    db.refresh(voucher)
    return Service.to_out(voucher)


@router.get("/vouchers/{voucher_id}/renders", response_model=list[RenderOut])
def list_voucher_renders(
    voucher_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("document.render")),
) -> list[DocumentRender]:
    voucher = db.get(WarehouseVoucher, voucher_id)
    if voucher is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vale inexistente.")
    IdentityService.assert_department_access(db, actor.id, voucher.department_id)
    if voucher.warehouse_id is not None:
        IdentityService.assert_warehouse_access(db, actor.id, voucher.warehouse_id)
    return Service.list_renders(db, "WarehouseVoucher", voucher.id)


@router.get("/vouchers/{voucher_id}/pdf")
def voucher_pdf(
    voucher_id: uuid.UUID,
    reprint: bool = Query(default=False),
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("document.render")),
) -> Response:
    render, content = Service.render_voucher(db, actor.id, voucher_id, "PDF", reprint=reprint)
    db.commit()
    return Response(
        content=content,
        media_type=_MEDIA_TYPES["PDF"],
        headers=_attachment_headers(render.document_no, "PDF", reprint=render.is_reprint),
    )


@router.get("/vouchers/{voucher_id}/xlsx")
def voucher_xlsx(
    voucher_id: uuid.UUID,
    reprint: bool = Query(default=False),
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("document.render")),
) -> Response:
    render, content = Service.render_voucher(db, actor.id, voucher_id, "XLSX", reprint=reprint)
    db.commit()
    return Response(
        content=content,
        media_type=_MEDIA_TYPES["XLSX"],
        headers=_attachment_headers(render.document_no, "XLSX", reprint=render.is_reprint),
    )


@router.get("/requisitions/{requisition_id}/renders", response_model=list[RenderOut])
def list_requisition_renders(
    requisition_id: uuid.UUID,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("document.render")),
) -> list[DocumentRender]:
    requisition = db.get(Requisition, requisition_id)
    if requisition is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requisición inexistente.")
    IdentityService.assert_department_access(db, actor.id, requisition.department_id)
    return Service.list_renders(db, "Requisition", requisition.id)


@router.get("/requisitions/{requisition_id}/pdf")
def requisition_pdf(
    requisition_id: uuid.UUID,
    reprint: bool = Query(default=False),
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("document.render")),
) -> Response:
    render, content = Service.render_requisition(db, actor.id, requisition_id, "PDF", reprint=reprint)
    db.commit()
    return Response(
        content=content,
        media_type=_MEDIA_TYPES["PDF"],
        headers=_attachment_headers(render.document_no, "PDF", reprint=render.is_reprint),
    )


@router.get("/requisitions/{requisition_id}/xlsx")
def requisition_xlsx(
    requisition_id: uuid.UUID,
    reprint: bool = Query(default=False),
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_permission("document.render")),
) -> Response:
    render, content = Service.render_requisition(db, actor.id, requisition_id, "XLSX", reprint=reprint)
    db.commit()
    return Response(
        content=content,
        media_type=_MEDIA_TYPES["XLSX"],
        headers=_attachment_headers(render.document_no, "XLSX", reprint=render.is_reprint),
    )
