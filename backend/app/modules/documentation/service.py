from __future__ import annotations

import hashlib
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import NoReturn

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.audit.service import AuditService
from app.modules.documentation.models import (
    DocumentRegistry,
    DocumentRender,
    DocumentTemplate,
    WarehouseVoucher,
    WarehouseVoucherLine,
)
from app.modules.documentation.render_req import REQData, REQLine, render_req_pdf, render_req_xlsx
from app.modules.documentation.render_va import VAData, VALine, render_va_pdf, render_va_xlsx
from app.modules.documentation.schemas import VoucherSignatureIn
from app.modules.documentation.templates import REQ_SPEC, VA_SPEC, ensure_template
from app.modules.identity.service import IdentityService
from app.modules.inventory.models import StockMovement
from app.modules.inventory.service import InventoryService
from app.modules.maintenance.models import Equipment
from app.modules.master_data.models import Item, ItemSupplier, Supplier, Uom
from app.modules.organization.models import Department, MiningUnit, Warehouse
from app.modules.requisitions.models import Requisition, RequisitionLine
from app.shared.events import emit
from app.shared.idempotency import acquire, complete
from app.shared.numbering import attach_entity, next_document_number, record_document_event


class DocumentError(HTTPException):
    pass


def _fail(detail: str, code: int = status.HTTP_409_CONFLICT) -> NoReturn:
    raise DocumentError(status_code=code, detail=detail)


def _qty(value: Decimal | None) -> str:
    if value is None:
        return ""
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _date_text(value: date | datetime | None) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        value = value.date()
    return value.strftime("%d/%m/%Y")


class DocumentationService:
    # ------------------------------------------------------------------
    # Vales de salida
    # ------------------------------------------------------------------
    @staticmethod
    def _context(
        db: Session,
        actor_id: uuid.UUID,
        department_id: uuid.UUID,
        warehouse_id: uuid.UUID | None,
    ) -> tuple[uuid.UUID, uuid.UUID, Department]:
        IdentityService.assert_department_access(db, actor_id, department_id)
        department = db.get(Department, department_id)
        if department is None:
            _fail("Departamento inexistente.", status.HTTP_404_NOT_FOUND)
        if department.mining_unit_id is None:
            _fail("El departamento no tiene unidad minera asignada.", status.HTTP_422_UNPROCESSABLE_ENTITY)
        unit = db.get(MiningUnit, department.mining_unit_id)
        if unit is None:
            _fail("Unidad minera inexistente.", status.HTTP_404_NOT_FOUND)
        if warehouse_id is not None:
            warehouse = db.get(Warehouse, warehouse_id)
            if warehouse is None:
                _fail("Almacén inexistente.", status.HTTP_404_NOT_FOUND)
            if warehouse.company_id != department.company_id:
                _fail("El almacén pertenece a otra compañía.", status.HTTP_422_UNPROCESSABLE_ENTITY)
        if warehouse_id is not None:
            IdentityService.assert_warehouse_access(db, actor_id, warehouse_id)
        return department.company_id, unit.id, department

    @staticmethod
    def _assert_voucher_access(db: Session, actor_id: uuid.UUID, voucher: WarehouseVoucher) -> None:
        IdentityService.assert_department_access(db, actor_id, voucher.department_id)
        if voucher.warehouse_id is not None:
            IdentityService.assert_warehouse_access(db, actor_id, voucher.warehouse_id)

    @staticmethod
    def _voucher_lines_from_requisition(
        db: Session, requisition: Requisition, mode: str
    ) -> list[dict]:
        lines = list(
            db.execute(
                select(RequisitionLine)
                .where(RequisitionLine.requisition_id == requisition.id)
                .order_by(RequisitionLine.line_no)
                .with_for_update()
            ).scalars()
        )
        movements = list(
            db.execute(
                select(StockMovement)
                .where(
                    StockMovement.requisition_line_id.in_([line.id for line in lines]),
                    StockMovement.movement_type == "ISSUE",
                    StockMovement.status == "POSTED",
                )
                .order_by(StockMovement.posted_at)
            ).scalars()
        )
        by_line: dict[uuid.UUID, list[StockMovement]] = {}
        for movement in movements:
            if movement.requisition_line_id is None:
                continue
            by_line.setdefault(movement.requisition_line_id, []).append(movement)

        result: list[dict] = []
        for line in lines:
            line_movements = by_line.get(line.id, [])
            dispatched = sum((m.quantity for m in line_movements), Decimal("0"))
            if mode == "DELIVERY" and dispatched <= Decimal("0"):
                continue
            if line.status == "CANCELLED" and dispatched <= Decimal("0"):
                continue
            item = db.get(Item, line.item_id) if line.item_id else None
            uom = db.get(Uom, line.uom_id)
            result.append(
                {
                    "requisition_line_id": line.id,
                    "stock_movement_id": line_movements[0].id if len(line_movements) == 1 else None,
                    "item_id": line.item_id,
                    "item_code": item.code if item else "",
                    "uom_code": uom.code if uom else "",
                    "description": line.description,
                    "requested_qty": line.requested_qty,
                    "dispatched_qty": dispatched if mode == "DELIVERY" else Decimal("0"),
                }
            )
        if mode == "DELIVERY" and not result:
            _fail("No hay entregas confirmadas para generar el vale.")
        if not result:
            _fail("La requisición no tiene partidas vigentes.", status.HTTP_422_UNPROCESSABLE_ENTITY)
        return result

    @staticmethod
    def create_voucher(db: Session, actor_id: uuid.UUID, payload) -> WarehouseVoucher:
        company_id, unit_id, department = DocumentationService._context(
            db, actor_id, payload.department_id, payload.warehouse_id
        )
        requisition: Requisition | None = None
        if payload.requisition_id is not None:
            requisition = db.execute(
                select(Requisition).where(Requisition.id == payload.requisition_id).with_for_update()
            ).scalar_one_or_none()
            if requisition is None:
                _fail("Requisición inexistente.", status.HTTP_404_NOT_FOUND)
            if requisition.company_id != company_id:
                _fail("La requisición pertenece a otra compañía.", status.HTTP_422_UNPROCESSABLE_ENTITY)
            IdentityService.assert_department_access(db, actor_id, requisition.department_id)
            if requisition.status not in ("APPROVED", "PARTIALLY_APPROVED", "IN_PROGRESS", "CLOSED"):
                _fail("La requisición no está autorizada para generar un vale.")
            lines_data = DocumentationService._voucher_lines_from_requisition(db, requisition, payload.mode)
        elif payload.lines:
            lines_data = [
                {
                    "requisition_line_id": line.requisition_line_id,
                    "stock_movement_id": None,
                    "item_id": line.item_id,
                    "item_code": line.item_code,
                    "uom_code": line.uom_code,
                    "description": line.description,
                    "requested_qty": line.requested_qty,
                    "dispatched_qty": line.dispatched_qty if payload.mode == "DELIVERY" else Decimal("0"),
                }
                for line in payload.lines
            ]
        else:
            _fail("El vale requiere una requisición o partidas explícitas.", status.HTTP_422_UNPROCESSABLE_ENTITY)

        if payload.mode == "DELIVERY" and any(line["dispatched_qty"] <= 0 for line in lines_data):
            _fail("Un vale de entrega requiere cantidades despachadas positivas.")

        idem = payload.idempotency_key or (
            f"voucher:{payload.requisition_id}:{payload.mode}:{payload.issue_date or 'hoy'}"
        )
        record, created = acquire(
            db,
            idem,
            operation="documentation.voucher.create",
            entity_type="WarehouseVoucher",
        )
        if not created:
            if record.entity_id is not None:
                existing = db.get(WarehouseVoucher, record.entity_id)
                if existing is not None:
                    return existing
            _fail("La clave de idempotencia ya fue utilizada por otra operación.")

        registry, document_no = next_document_number(
            db,
            "VA",
            company_id,
            series="LAG",
            mining_unit_id=unit_id,
            year=0,
            start_number=166,
            number_format="{code}-{number:06d}",
        )
        spec = VA_SPEC
        template = ensure_template(db, spec)
        voucher = WarehouseVoucher(
            document_no=document_no,
            document_registry_id=registry.id,
            company_id=company_id,
            mining_unit_id=unit_id,
            department_id=payload.department_id,
            warehouse_id=payload.warehouse_id or (requisition.warehouse_id if requisition else None),
            source_requisition_id=requisition.id if requisition else None,
            cost_center_code=payload.cost_center_code,
            area=payload.area or department.name,
            usage_equipment=payload.usage_equipment,
            issue_date=payload.issue_date or date.today(),
            status="ISSUED" if payload.mode == "DELIVERY" else "DRAFT",
            idempotency_key=idem,
            template_code=spec.code,
            template_version=template.template_version,
            issued_at=datetime.now(timezone.utc) if payload.mode == "DELIVERY" else None,
            issued_by=actor_id if payload.mode == "DELIVERY" else None,
            created_by=actor_id,
        )
        db.add(voucher)
        db.flush()
        for index, line_data in enumerate(lines_data, start=1):
            db.add(
                WarehouseVoucherLine(
                    voucher_id=voucher.id,
                    line_no=index,
                    requisition_line_id=line_data["requisition_line_id"],
                    stock_movement_id=line_data["stock_movement_id"],
                    item_id=line_data["item_id"],
                    item_code=line_data["item_code"] or "",
                    uom_code=line_data["uom_code"] or "",
                    description=line_data["description"],
                    requested_qty=line_data["requested_qty"],
                    dispatched_qty=line_data["dispatched_qty"],
                    created_by=actor_id,
                )
            )
        db.flush()
        attach_entity(db, registry, "WarehouseVoucher", voucher.id)
        record_document_event(
            db, registry, "VOUCHER_CREATED", None, voucher.status, actor_id, {"mode": payload.mode}
        )
        AuditService.record(
            db,
            action="VOUCHER_CREATE",
            entity_type="WarehouseVoucher",
            entity_id=voucher.id,
            actor_id=actor_id,
            after={
                "document_no": document_no,
                "mode": payload.mode,
                "requisition_id": str(requisition.id) if requisition else None,
                "lines": len(lines_data),
            },
        )
        emit(db, "WarehouseVoucher", voucher.id, "VOUCHER_CREATED", {"document_no": document_no})
        complete(db, record, voucher.id)
        return voucher

    @staticmethod
    def issue_voucher(db: Session, actor_id: uuid.UUID, voucher_id: uuid.UUID) -> WarehouseVoucher:
        voucher = db.execute(
            select(WarehouseVoucher).where(WarehouseVoucher.id == voucher_id).with_for_update()
        ).scalar_one_or_none()
        if voucher is None:
            _fail("Vale inexistente.", status.HTTP_404_NOT_FOUND)
        DocumentationService._assert_voucher_access(db, actor_id, voucher)
        if voucher.status == "ISSUED":
            return voucher
        if voucher.source_requisition_id is None:
            _fail("El vale no está vinculado a una requisición con entregas confirmadas.")
        requisition = db.get(Requisition, voucher.source_requisition_id)
        if requisition is None:
            _fail("La requisición de origen no existe.")
        lines = DocumentationService._voucher_lines_from_requisition(db, requisition, "DELIVERY")
        if not lines:
            _fail("No hay entregas confirmadas para emitir el vale.")
        existing = {line.requisition_line_id: line for line in voucher.lines}
        for data in lines:
            line = existing.get(data["requisition_line_id"])
            if line is None:
                continue
            line.dispatched_qty = data["dispatched_qty"]
            line.stock_movement_id = data["stock_movement_id"]
            line.updated_by = actor_id
        voucher.status = "ISSUED"
        voucher.issued_at = datetime.now(timezone.utc)
        voucher.issued_by = actor_id
        voucher.updated_by = actor_id
        registry = db.get(DocumentRegistry, voucher.document_registry_id)
        if registry is not None:
            record_document_event(db, registry, "VOUCHER_ISSUED", "DRAFT", "ISSUED", actor_id)
        AuditService.record(
            db,
            action="VOUCHER_ISSUE",
            entity_type="WarehouseVoucher",
            entity_id=voucher.id,
            actor_id=actor_id,
            before={"status": "DRAFT"},
            after={"status": "ISSUED", "document_no": voucher.document_no},
        )
        emit(db, "WarehouseVoucher", voucher.id, "VOUCHER_ISSUED", {"document_no": voucher.document_no})
        return voucher

    @staticmethod
    def record_signatures(
        db: Session,
        actor_id: uuid.UUID,
        voucher_id: uuid.UUID,
        payload: VoucherSignatureIn,
    ) -> WarehouseVoucher:
        """Registra nombres declarados; no captura ni simula firmas gráficas."""
        voucher = db.execute(
            select(WarehouseVoucher).where(WarehouseVoucher.id == voucher_id).with_for_update()
        ).scalar_one_or_none()
        if voucher is None:
            _fail("Vale inexistente.", status.HTTP_404_NOT_FOUND)
        DocumentationService._assert_voucher_access(db, actor_id, voucher)
        fields = ("received_by_name", "authorized_by_name", "dispatched_by_name")
        changed: dict[str, str] = {}
        for field in fields:
            value = getattr(payload, field)
            if value is not None and value.strip():
                changed[field] = value.strip()
        if not changed:
            _fail("Capture al menos un nombre de recepción, autorización o despacho.",
                  status.HTTP_422_UNPROCESSABLE_ENTITY)
        before = {field: getattr(voucher, field) for field in changed}
        for field, value in changed.items():
            setattr(voucher, field, value)
        voucher.signatures_recorded_at = datetime.now(timezone.utc)
        voucher.signatures_recorded_by = actor_id
        voucher.updated_by = actor_id
        voucher.version += 1
        registry = db.get(DocumentRegistry, voucher.document_registry_id)
        if registry is not None:
            record_document_event(
                db,
                registry,
                "VOUCHER_SIGNATURES_RECORDED",
                voucher.status,
                voucher.status,
                actor_id,
                {"fields": sorted(changed), "graphic_signature": False},
            )
        AuditService.record(
            db,
            action="VOUCHER_SIGNATURES_RECORDED",
            entity_type="WarehouseVoucher",
            entity_id=voucher.id,
            actor_id=actor_id,
            before=before,
            after={"fields": sorted(changed), "graphic_signature": False},
            detail="Constancia nominal; no se generó ninguna firma gráfica.",
        )
        emit(
            db,
            "WarehouseVoucher",
            voucher.id,
            "VOUCHER_SIGNATURES_RECORDED",
            {"document_no": voucher.document_no, "fields": sorted(changed)},
        )
        return voucher

    @staticmethod
    def to_out(voucher: WarehouseVoucher) -> dict:
        return {
            "id": voucher.id,
            "document_no": voucher.document_no,
            "department_id": voucher.department_id,
            "warehouse_id": voucher.warehouse_id,
            "source_requisition_id": voucher.source_requisition_id,
            "cost_center_code": voucher.cost_center_code,
            "area": voucher.area,
            "usage_equipment": voucher.usage_equipment,
            "issue_date": voucher.issue_date,
            "status": voucher.status,
            "template_code": voucher.template_code,
            "template_version": voucher.template_version,
            "issued_at": voucher.issued_at,
            "created_at": voucher.created_at,
            "received_by_name": voucher.received_by_name,
            "authorized_by_name": voucher.authorized_by_name,
            "dispatched_by_name": voucher.dispatched_by_name,
            "signatures_recorded_at": voucher.signatures_recorded_at,
            "lines": [
                {
                    "id": line.id,
                    "line_no": line.line_no,
                    "requisition_line_id": line.requisition_line_id,
                    "stock_movement_id": line.stock_movement_id,
                    "item_id": line.item_id,
                    "item_code": line.item_code,
                    "uom_code": line.uom_code,
                    "description": line.description,
                    "requested_qty": line.requested_qty,
                    "dispatched_qty": line.dispatched_qty,
                }
                for line in sorted(voucher.lines, key=lambda item: item.line_no)
            ],
        }

    # ------------------------------------------------------------------
    # Render PDF/XLSX
    # ------------------------------------------------------------------
    @staticmethod
    def _voucher_data(db: Session, voucher: WarehouseVoucher) -> VAData:
        department = db.get(Department, voucher.department_id)
        return VAData(
            folio=voucher.document_no,
            departamento=department.name if department else "",
            ceco=voucher.cost_center_code or "",
            area=voucher.area or "",
            uso_equipo=voucher.usage_equipment or "",
            fecha_expedicion=_date_text(voucher.issue_date),
            recibido_por=voucher.received_by_name or "",
            autorizado_por=voucher.authorized_by_name or "",
            despachado_por=voucher.dispatched_by_name or "",
            lines=[
                VALine(
                    partida=line.line_no,
                    codigo=line.item_code,
                    cantidad_solicitada=_qty(line.requested_qty),
                    unidad=line.uom_code,
                    descripcion=line.description,
                    cantidad_despachada=_qty(line.dispatched_qty),
                )
                for line in sorted(voucher.lines, key=lambda item: item.line_no)
            ],
        )

    @staticmethod
    def _recommended_supplier(db: Session, requisition: Requisition) -> str:
        """Proveedor preferido del catálogo; nunca se inventa si no hay fuente."""
        for line in sorted(requisition.lines, key=lambda item: item.line_no):
            if line.item_id is None:
                continue
            rows = db.execute(
                select(Supplier.name)
                .join(ItemSupplier, ItemSupplier.supplier_id == Supplier.id)
                .where(ItemSupplier.item_id == line.item_id)
                .order_by(ItemSupplier.preferred.desc(), Supplier.name)
            ).scalars()
            name = rows.first()
            if name:
                return name
        return ""

    @staticmethod
    def _requisition_data(db: Session, requisition: Requisition) -> REQData:
        department = db.get(Department, requisition.department_id)
        unit = db.get(MiningUnit, requisition.mining_unit_id)
        equipment = db.get(Equipment, requisition.equipment_id) if requisition.equipment_id else None
        needed = requisition.needed_at
        meses = []
        if needed is not None:
            meses = [["ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"][needed.month - 1]]
        lines: list[REQLine] = []
        for line in sorted(requisition.lines, key=lambda item: item.line_no):
            item = db.get(Item, line.item_id) if line.item_id else None
            uom = db.get(Uom, line.uom_id)
            existencia = ""
            if item is not None and requisition.warehouse_id is not None:
                try:
                    existencia = _qty(InventoryService.availability(db, item.id, requisition.warehouse_id)["on_hand_qty"])
                except HTTPException:
                    existencia = ""
            lines.append(
                REQLine(
                    partida=line.line_no,
                    cantidad=_qty(line.requested_qty),
                    unidad=uom.code if uom else "",
                    descripcion=line.description,
                    consumo_mes=str(needed.month) if needed else "",
                    consumo_anio=str(needed.year) if needed else "",
                    existencia=existencia,
                    codificacion=item.code if item else "",
                )
            )
        approval_text = None
        if requisition.approved_at is not None:
            approval_text = f"{requisition.status} {requisition.approved_at:%Y-%m-%d %H:%M}"
        return REQData(
            folio=requisition.document_no,
            dia=f"{requisition.created_at.day:02d}",
            mes=f"{requisition.created_at.month:02d}",
            anio=str(requisition.created_at.year),
            mina=unit.name if unit else "",
            departamento=department.name if department else "",
            uso_inmediato=requisition.priority in ("HIGH", "URGENT"),
            existencia_almacen=requisition.requisition_type == "STOCK",
            cargo_opex=requisition.cost_center_id is not None,
            uso_equipo=(
                f"{equipment.asset_tag} {equipment.description}"
                if equipment is not None
                else (requisition.work_order_no or "")
            ),
            proveedor_recomendado=DocumentationService._recommended_supplier(db, requisition),
            lines=lines,
            meses_requeridos=meses,
            meses_programados=[],
            approval_text=approval_text,
        )

    @staticmethod
    def _store_and_record(
        db: Session,
        *,
        actor_id: uuid.UUID,
        template: DocumentTemplate,
        entity_type: str,
        entity_id: uuid.UUID,
        document_no: str,
        document_format: str,
        content: bytes,
        is_reprint: bool,
        source_render_id: uuid.UUID | None,
        metadata: dict | None = None,
    ) -> DocumentRender:
        digest = hashlib.sha256(content).hexdigest()
        extension = "pdf" if document_format == "PDF" else "xlsx"
        relative = f"{entity_type.lower()}/{entity_id}/{uuid.uuid4()}.{extension}"
        path = settings.DOCUMENT_STORAGE_DIR / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        render = DocumentRender(
            document_template_id=template.id,
            entity_type=entity_type,
            entity_id=entity_id,
            document_no=document_no,
            document_format=document_format,
            sha256=digest,
            size_bytes=len(content),
            storage_name=relative,
            is_reprint=is_reprint,
            source_render_id=source_render_id,
            rendered_by=actor_id,
            metadata_json=metadata or {},
        )
        db.add(render)
        db.flush()
        AuditService.record(
            db,
            action="DOCUMENT_REPRINT" if is_reprint else "DOCUMENT_RENDER",
            entity_type=entity_type,
            entity_id=entity_id,
            actor_id=actor_id,
            after={
                "document_no": document_no,
                "format": document_format,
                "sha256": digest,
                "template": template.code,
                "template_version": template.template_version,
                "reprint": is_reprint,
            },
        )
        return render

    @staticmethod
    def _latest_render(
        db: Session, entity_type: str, entity_id: uuid.UUID, document_format: str
    ) -> DocumentRender | None:
        return db.execute(
            select(DocumentRender)
            .where(
                DocumentRender.entity_type == entity_type,
                DocumentRender.entity_id == entity_id,
                DocumentRender.document_format == document_format,
                DocumentRender.is_reprint.is_(False),
            )
            .order_by(DocumentRender.rendered_at.desc())
        ).scalars().first()

    @staticmethod
    def render_voucher(
        db: Session,
        actor_id: uuid.UUID,
        voucher_id: uuid.UUID,
        document_format: str,
        *,
        reprint: bool = False,
    ) -> tuple[DocumentRender, bytes]:
        voucher = db.get(WarehouseVoucher, voucher_id)
        if voucher is None:
            _fail("Vale inexistente.", status.HTTP_404_NOT_FOUND)
        DocumentationService._assert_voucher_access(db, actor_id, voucher)
        document_format = document_format.upper()
        if document_format not in ("PDF", "XLSX"):
            _fail("Formato no soportado.", status.HTTP_422_UNPROCESSABLE_ENTITY)
        template = ensure_template(db, VA_SPEC)
        source = DocumentationService._latest_render(db, "WarehouseVoucher", voucher.id, document_format)
        if reprint and source is not None:
            path = settings.DOCUMENT_STORAGE_DIR / source.storage_name
            if not path.is_file():
                _fail(
                    "El render original no está disponible; no se puede reimprimir.",
                    status.HTTP_409_CONFLICT,
                )
            content = path.read_bytes()
            render = DocumentationService._store_and_record(
                db,
                actor_id=actor_id,
                template=template,
                entity_type="WarehouseVoucher",
                entity_id=voucher.id,
                document_no=voucher.document_no,
                document_format=document_format,
                content=content,
                is_reprint=True,
                source_render_id=source.id,
                metadata={"reprint_of": str(source.id)},
            )
            registry = db.get(DocumentRegistry, voucher.document_registry_id)
            if registry is not None:
                record_document_event(
                    db, registry, "VOUCHER_REPRINTED", voucher.status, voucher.status, actor_id,
                    {"format": document_format, "source_render_id": str(source.id)},
                )
            return render, content
        data = DocumentationService._voucher_data(db, voucher)
        content = render_va_pdf(data) if document_format == "PDF" else render_va_xlsx(data)
        render = DocumentationService._store_and_record(
            db,
            actor_id=actor_id,
            template=template,
            entity_type="WarehouseVoucher",
            entity_id=voucher.id,
            document_no=voucher.document_no,
            document_format=document_format,
            content=content,
            is_reprint=False,
            source_render_id=None,
        )
        registry = db.get(DocumentRegistry, voucher.document_registry_id)
        if registry is not None:
            record_document_event(
                db, registry, "VOUCHER_RENDERED", voucher.status, voucher.status, actor_id,
                {"format": document_format, "sha256": render.sha256},
            )
        return render, content

    @staticmethod
    def render_requisition(
        db: Session,
        actor_id: uuid.UUID,
        requisition_id: uuid.UUID,
        document_format: str,
        *,
        reprint: bool = False,
    ) -> tuple[DocumentRender, bytes]:
        requisition = db.get(Requisition, requisition_id)
        if requisition is None:
            _fail("Requisición inexistente.", status.HTTP_404_NOT_FOUND)
        IdentityService.assert_department_access(db, actor_id, requisition.department_id)
        document_format = document_format.upper()
        if document_format not in ("PDF", "XLSX"):
            _fail("Formato no soportado.", status.HTTP_422_UNPROCESSABLE_ENTITY)
        template = ensure_template(db, REQ_SPEC)
        source = DocumentationService._latest_render(db, "Requisition", requisition.id, document_format)
        if reprint and source is not None:
            path = settings.DOCUMENT_STORAGE_DIR / source.storage_name
            if path.is_file():
                content = path.read_bytes()
                render = DocumentationService._store_and_record(
                    db,
                    actor_id=actor_id,
                    template=template,
                    entity_type="Requisition",
                    entity_id=requisition.id,
                    document_no=requisition.document_no,
                    document_format=document_format,
                    content=content,
                    is_reprint=True,
                    source_render_id=source.id,
                    metadata={"reprint_of": str(source.id)},
                )
                registry = db.get(DocumentRegistry, requisition.document_registry_id)
                if registry is not None:
                    record_document_event(
                        db, registry, "REQUISITION_REPRINTED", requisition.status, requisition.status, actor_id,
                        {"format": document_format, "source_render_id": str(source.id)},
                    )
                return render, content
        data = DocumentationService._requisition_data(db, requisition)
        content = render_req_pdf(data) if document_format == "PDF" else render_req_xlsx(data)
        render = DocumentationService._store_and_record(
            db,
            actor_id=actor_id,
            template=template,
            entity_type="Requisition",
            entity_id=requisition.id,
            document_no=requisition.document_no,
            document_format=document_format,
            content=content,
            is_reprint=False,
            source_render_id=None,
        )
        registry = db.get(DocumentRegistry, requisition.document_registry_id)
        if registry is not None:
            record_document_event(
                db, registry, "REQUISITION_RENDERED", requisition.status, requisition.status, actor_id,
                {"format": document_format, "sha256": render.sha256},
            )
        return render, content

    @staticmethod
    def list_renders(db: Session, entity_type: str, entity_id: uuid.UUID) -> list[DocumentRender]:
        return list(
            db.execute(
                select(DocumentRender)
                .where(DocumentRender.entity_type == entity_type, DocumentRender.entity_id == entity_id)
                .order_by(DocumentRender.rendered_at.desc())
            ).scalars()
        )
