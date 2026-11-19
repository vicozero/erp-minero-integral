from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.modules.audit.service import AuditService
from app.modules.costing.models import CostCenter
from app.modules.documentation.models import DocumentNumbering, DocumentType
from app.modules.identity.models import AppUser, Permission, Role, RolePermission, UserDepartment, UserRole
from app.modules.inventory.models import NULL_UUID, LocationMap, StockBalance, StockMovement
from app.modules.maintenance.models import Equipment
from app.modules.master_data.models import (
    Item,
    ItemCrossReference,
    ItemFamily,
    ItemSupplier,
    LocationRestriction,
    Lot,
    Serial,
    StorageLocation,
    Supplier,
    Uom,
)
from app.modules.organization.models import Company, Department, MiningUnit, Warehouse
from app.modules.sla.models import SlaPolicy
from app.shared.constants import DOCUMENT_TYPES, ROLE_LABELS, ROLE_PERMISSIONS
from app.shared.events import emit
from app.shared.numbering import next_document_number

DEMO_COMPANY = "EMP_DEMO"
DEMO_UNIT = "LAG_DEMO"
DEMO_WAREHOUSE = "ALM_PRINCIPAL_DEMO"
DEMO_SERIES = "LAG"
DEMO_ITEMS = (
    ("DEMO-TORNILLO", "Tornillo M8 x 30 (demo)", "UND", Decimal("120.000000"), Decimal("2.5000")),
    ("DEMO-ACEITE", "Aceite hidráulico demo", "LT", Decimal("80.000000"), Decimal("45.0000")),
    ("DEMO-FILTRO", "Filtro de aire demo", "UND", Decimal("40.000000"), Decimal("120.0000")),
)


def _assign_department(db: Session, user_id: uuid.UUID, department_id: uuid.UUID) -> None:
    existing = db.execute(
        select(UserDepartment).where(
            UserDepartment.user_id == user_id,
            UserDepartment.department_id == department_id,
        )
    ).scalar_one_or_none()
    if existing is None:
        db.add(UserDepartment(user_id=user_id, department_id=department_id))
        db.flush()
    elif existing.revoked_at is not None:
        existing.revoked_at = None
        existing.revoked_by = None
        db.flush()


def _get_or_create_role(db: Session, code: str, name: str) -> Role:
    role = db.execute(select(Role).where(Role.code == code)).scalar_one_or_none()
    if role is None:
        role = Role(code=code, name=name)
        db.add(role)
        db.flush()
    return role


def _get_or_create_user(
    db: Session,
    username: str,
    email: str,
    full_name: str,
    password_hash: str,
) -> AppUser:
    user = db.execute(select(AppUser).where(AppUser.username == username)).scalar_one_or_none()
    if user is None:
        user = AppUser(
            username=username,
            email=email,
            full_name=full_name,
            password_hash=password_hash,
            status="ACTIVE",
        )
        db.add(user)
        db.flush()
    return user


def _ensure_user_role(db: Session, user_id: uuid.UUID, role_id: uuid.UUID) -> None:
    existing = db.execute(
        select(UserRole).where(UserRole.user_id == user_id, UserRole.role_id == role_id)
    ).scalar_one_or_none()
    if existing is None:
        db.add(UserRole(user_id=user_id, role_id=role_id, scope_type="GLOBAL"))
        db.flush()


def _seed_wms_demo(
    db: Session,
    *,
    company,
    warehouse,
    items: dict[str, Item],
    supplier: Supplier,
    admin: AppUser,
) -> None:
    """Catálogo WMS sintético. Nunca modifica cantidades de los saldos."""
    now = datetime.now(timezone.utc)

    families: dict[str, ItemFamily] = {}
    for code, name in (
        ("CONSUMIBLES", "Consumibles y ferretería"),
        ("LUBRICANTES", "Lubricantes y fluidos"),
        ("REPUESTOS", "Repuestos y filtros"),
    ):
        family = db.execute(
            select(ItemFamily).where(ItemFamily.company_id == company.id, ItemFamily.code == code)
        ).scalar_one_or_none()
        if family is None:
            family = ItemFamily(company_id=company.id, code=code, name=name, created_by=admin.id)
            db.add(family)
            db.flush()
        families[code] = family

    locations: dict[str, StorageLocation] = {}
    # Coordenadas sintéticas dentro del plano 1000 × 600; son una proyección
    # referencial, nunca un plano exacto ni una fuente de existencias.
    for code, zone, aisle, rack, level, position, location_type, coord_x, coord_y in (
        ("REC-A-01", "A", "01", None, None, None, "RECEIPT", "80", "300"),
        ("A-01-R1-1-01", "A", "01", "R1", "1", "01", "STANDARD", "260", "180"),
        ("A-01-R1-2-01", "A", "01", "R1", "2", "01", "STANDARD", "260", "260"),
        ("A-02-R1-1-01", "A", "02", "R1", "1", "01", "STANDARD", "460", "180"),
        ("CUAR-B-01", "B", "01", None, None, None, "QUARANTINE", "700", "300"),
        ("DESP-C-01", "C", "01", None, None, None, "DISPATCH", "880", "300"),
    ):
        location = db.execute(
            select(StorageLocation).where(
                StorageLocation.warehouse_id == warehouse.id, StorageLocation.code == code
            )
        ).scalar_one_or_none()
        if location is None:
            location = StorageLocation(
                warehouse_id=warehouse.id,
                code=code,
                zone=zone,
                aisle=aisle,
                rack=rack,
                level=level,
                position=position,
                location_type=location_type,
                qr_token=f"WMS:{warehouse.code}:{code}",
                capacity_qty=Decimal("1000"),
                status="ACTIVE",
                coord_x=Decimal(coord_x),
                coord_y=Decimal(coord_y),
                created_by=admin.id,
            )
            db.add(location)
            db.flush()
        elif location.coord_x is None:
            location.coord_x = Decimal(coord_x)
            location.coord_y = Decimal(coord_y)
        locations[code] = location

    map_row = db.execute(
        select(LocationMap).where(
            LocationMap.warehouse_id == warehouse.id, LocationMap.is_active.is_(True)
        )
    ).scalar_one_or_none()
    if map_row is None:
        db.add(
            LocationMap(
                warehouse_id=warehouse.id,
                map_version=1,
                label="Referencial · no es plano exacto",
                width=Decimal("1000"),
                height=Decimal("600"),
                is_active=True,
                created_by=admin.id,
            )
        )
        db.flush()

    item_meta: dict[str, dict[str, object]] = {
        "DEMO-TORNILLO": {
            "family": "CONSUMIBLES",
            "manufacturer": "Fabricante Ficticio S.A.",
            "part": "FF-M8-30",
            "barcode": "7500000000017",
            "consumable": True,
        },
        "DEMO-ACEITE": {
            "family": "LUBRICANTES",
            "manufacturer": "Lubricantes Demo",
            "part": "LD-HID-46",
            "barcode": "7500000000024",
            "consumable": True,
        },
        "DEMO-FILTRO": {
            "family": "REPUESTOS",
            "manufacturer": "Filtros Demo",
            "part": "FD-AIR-200",
            "barcode": "7500000000031",
            "consumable": False,
        },
    }
    for code, meta in item_meta.items():
        item = items[code]
        if item.family_id is None:
            item.family_id = families[str(meta["family"])].id
        if item.manufacturer is None:
            item.manufacturer = str(meta["manufacturer"])
            item.manufacturer_part_no = str(meta["part"])
            item.barcode = str(meta["barcode"])
        item.is_consumable = bool(meta["consumable"])
        item.is_returnable = code == "DEMO-FILTRO"
        item.is_tool = False
        item.reorder_point = Decimal("20")
        item.safety_stock = Decimal("10")
        item.max_stock = Decimal("500")
        item.default_supplier_id = supplier.id
        db.flush()

        relation = db.execute(
            select(ItemSupplier).where(ItemSupplier.item_id == item.id, ItemSupplier.supplier_id == supplier.id)
        ).scalar_one_or_none()
        if relation is None:
            db.add(
                ItemSupplier(
                    item_id=item.id,
                    supplier_id=supplier.id,
                    supplier_part_number=str(meta["part"]),
                    lead_time_days=5,
                    min_order_qty=Decimal("1"),
                    preferred=True,
                    last_unit_cost=item.standard_cost,
                    created_by=admin.id,
                )
            )

    tornillo = items["DEMO-TORNILLO"]
    xref = db.execute(
        select(ItemCrossReference).where(
            ItemCrossReference.item_id == tornillo.id,
            ItemCrossReference.reference_type == "MANUFACTURER",
            ItemCrossReference.reference_code == "FF-M8-30",
        )
    ).scalar_one_or_none()
    if xref is None:
        db.add(
            ItemCrossReference(
                item_id=tornillo.id,
                reference_type="MANUFACTURER",
                reference_code="FF-M8-30",
                authorised=True,
                approved_by=admin.id,
                valid_from=now,
                notes="Equivalencia sintética autorizada para demostración.",
                created_by=admin.id,
            )
        )

    lots: dict[str, Lot] = {}
    for item_code, lot_number in (("DEMO-TORNILLO", "LOT-DEMO-001"), ("DEMO-ACEITE", "LOT-DEMO-002")):
        lot = db.execute(
            select(Lot).where(Lot.item_id == items[item_code].id, Lot.lot_number == lot_number)
        ).scalar_one_or_none()
        if lot is None:
            lot = Lot(
                item_id=items[item_code].id,
                lot_number=lot_number,
                manufactured_at=now - timedelta(days=15),
                expiry_date=date.today() + timedelta(days=365),
                status="ACTIVE",
                created_by=admin.id,
            )
            db.add(lot)
            db.flush()
        lots[item_code] = lot
        items[item_code].lot_tracked = True

    filtro = items["DEMO-FILTRO"]
    filtro.serial_tracked = True
    for index in range(1, 4):
        serial_number = f"SER-DEMO-{index:03d}"
        serial = db.execute(
            select(Serial).where(Serial.item_id == filtro.id, Serial.serial_number == serial_number)
        ).scalar_one_or_none()
        if serial is None:
            db.add(
                Serial(
                    item_id=filtro.id,
                    serial_number=serial_number,
                    status="ACTIVE",
                    current_location_id=locations["A-01-R1-2-01"].id,
                    created_by=admin.id,
                )
            )

    restriction = db.execute(
        select(LocationRestriction).where(
            LocationRestriction.location_id == locations["A-02-R1-1-01"].id,
            LocationRestriction.item_family_id == families["CONSUMIBLES"].id,
        )
    ).scalar_one_or_none()
    if restriction is None:
        db.add(
            LocationRestriction(
                location_id=locations["A-02-R1-1-01"].id,
                item_family_id=families["CONSUMIBLES"].id,
                max_qty=Decimal("250"),
                created_by=admin.id,
            )
        )

    for item_code, location_code in (
        ("DEMO-TORNILLO", "A-01-R1-1-01"),
        ("DEMO-ACEITE", "A-02-R1-1-01"),
        ("DEMO-FILTRO", "A-01-R1-2-01"),
    ):
        balance = db.execute(
            select(StockBalance).where(
                StockBalance.warehouse_id == warehouse.id,
                StockBalance.item_id == items[item_code].id,
                StockBalance.lot_id == NULL_UUID,
                StockBalance.location_id == NULL_UUID,
            )
        ).scalar_one_or_none()
        if balance is not None and balance.location_ref_id is None:
            balance.location_ref_id = locations[location_code].id
            lot = lots.get(item_code)
            if lot is not None:
                balance.lot_ref_id = lot.id
    db.flush()


def _seed_sla_policies(db: Session) -> None:
    """Siembra de forma idempotente la política SLA aprobada para la demo.

    El modo emergencia permanece desactivado: solo puede activarlo un actor
    con ``sla.policy.approve`` mediante el servicio auditado.
    """
    policies = (
        ("11111111-1111-4111-8111-000000000001", "LOW", 72, 96),
        ("11111111-1111-4111-8111-000000000002", "NORMAL", 48, 72),
        ("11111111-1111-4111-8111-000000000003", "HIGH", 24, 48),
        ("11111111-1111-4111-8111-000000000004", "URGENT", 8, 16),
    )
    for policy_id, priority, green_hours, yellow_hours in policies:
        exists = db.execute(
            select(SlaPolicy.id).where(
                SlaPolicy.priority == priority,
                SlaPolicy.department_key == "ALL",
                SlaPolicy.requisition_type == "ALL",
            )
        ).first()
        if exists is not None:
            continue
        db.add(
            SlaPolicy(
                id=uuid.UUID(policy_id),
                priority=priority,
                department_key="ALL",
                department_id=None,
                requisition_type="ALL",
                green_hours=green_hours,
                yellow_hours=yellow_hours,
                is_active=True,
                emergency_enabled=False,
                emergency_green_hours=4,
                emergency_yellow_hours=8,
                scope="GLOBAL",
                evidence="Propuesta aprobada por el usuario el 19/11/2026.",
                notes="La emergencia requiere aprobación explícita y permiso sla.policy.approve.",
            )
        )
        db.flush()


def seed_demo_data(db: Session) -> None:
    if not settings.DEMO_PASSWORD:
        raise RuntimeError(
            "DEMO_PASSWORD no está configurado. Defina una contraseña ficticia en .env antes de sembrar."
        )

    password_hash = hash_password(settings.DEMO_PASSWORD)
    now = datetime.now(timezone.utc)

    roles = {
        code: _get_or_create_role(db, code, ROLE_LABELS.get(code, code.title()))
        for code in ROLE_PERMISSIONS
    }
    permission_codes: set[str] = set()
    for codes in ROLE_PERMISSIONS.values():
        permission_codes.update(codes)
    permissions: dict[str, Permission] = {}
    for code in sorted(permission_codes):
        perm = db.execute(select(Permission).where(Permission.code == code)).scalar_one_or_none()
        if perm is None:
            perm = Permission(code=code, description=code)
            db.add(perm)
            db.flush()
        permissions[code] = perm

    for role_code, codes in ROLE_PERMISSIONS.items():
        role = roles[role_code]
        for code in dict.fromkeys(codes):
            exists = db.execute(
                select(RolePermission).where(
                    RolePermission.role_id == role.id,
                    RolePermission.permission_id == permissions[code].id,
                )
            ).scalar_one_or_none()
            if exists is None:
                db.add(RolePermission(role_id=role.id, permission_id=permissions[code].id))
    db.flush()

    users = {
        "demo.admin": _get_or_create_user(db, "demo.admin", "admin.demo@example.invalid", "Administrador Demo", password_hash),
        "demo.solicitante": _get_or_create_user(
            db, "demo.solicitante", "solicitante.demo@example.invalid", "Solicitante Demo", password_hash
        ),
        "demo.aprobador": _get_or_create_user(
            db, "demo.aprobador", "aprobador.demo@example.invalid", "Aprobador Demo", password_hash
        ),
        "demo.almacenista": _get_or_create_user(
            db, "demo.almacenista", "almacen.demo@example.invalid", "Almacenista Demo", password_hash
        ),
        "demo.comprador": _get_or_create_user(
            db, "demo.comprador", "compras.demo@example.invalid", "Comprador Demo", password_hash
        ),
        "demo.jefe": _get_or_create_user(
            db, "demo.jefe", "jefe.demo@example.invalid", "Jefe de departamento Demo", password_hash
        ),
        "demo.gerencia": _get_or_create_user(
            db, "demo.gerencia", "gerencia.demo@example.invalid", "Gerencia Demo", password_hash
        ),
        "demo.auditor": _get_or_create_user(
            db, "demo.auditor", "auditor.demo@example.invalid", "Auditor Demo", password_hash
        ),
        "demo.temporal": _get_or_create_user(
            db, "demo.temporal", "temporal.demo@example.invalid", "Usuario con contraseña temporal", password_hash
        ),
    }
    role_by_user = {
        "demo.admin": "ADMIN",
        "demo.solicitante": "SOLICITANTE",
        "demo.aprobador": "APROBADOR",
        "demo.almacenista": "ALMACENISTA",
        "demo.comprador": "COMPRADOR",
        "demo.jefe": "JEFE_DEPARTAMENTO",
        "demo.gerencia": "GERENCIA",
        "demo.auditor": "AUDITOR",
        "demo.temporal": "SOLICITANTE",
    }
    for username, role_code in role_by_user.items():
        _ensure_user_role(db, users[username].id, roles[role_code].id)

    temporal = users["demo.temporal"]
    if not temporal.must_change_password:
        temporal.must_change_password = True
        db.flush()

    company = db.execute(select(Company).where(Company.code == DEMO_COMPANY)).scalar_one_or_none()
    if company is None:
        company = Company(code=DEMO_COMPANY, name="Empresa Demostrativa (ficticia)", is_active=True)
        db.add(company)
        db.flush()

    unit = db.execute(
        select(MiningUnit).where(MiningUnit.company_id == company.id, MiningUnit.code == DEMO_UNIT)
    ).scalar_one_or_none()
    if unit is None:
        unit = MiningUnit(company_id=company.id, code=DEMO_UNIT, name="Unidad Minera Demo La Guitarra")
        db.add(unit)
        db.flush()

    other_unit = db.execute(
        select(MiningUnit).where(MiningUnit.company_id == company.id, MiningUnit.code == "LAG_OTRA_DEMO")
    ).scalar_one_or_none()
    if other_unit is None:
        other_unit = MiningUnit(
            company_id=company.id,
            code="LAG_OTRA_DEMO",
            name="Unidad minera ficticia adicional (pruebas de alcance)",
        )
        db.add(other_unit)
        db.flush()

    departments: dict[str, Department] = {}
    for code, name, owner in (
        ("DEMO-MINA", "Mina Demo", unit),
        ("DEMO-MANT", "Mantenimiento Demo", unit),
        ("DEMO-OTRA", "Departamento ajeno Demo", other_unit),
    ):
        dept = db.execute(
            select(Department).where(Department.company_id == company.id, Department.code == code)
        ).scalar_one_or_none()
        if dept is None:
            dept = Department(
                company_id=company.id,
                mining_unit_id=owner.id,
                code=code,
                name=name,
            )
            db.add(dept)
            db.flush()
        departments[code] = dept

    # Alcance por departamento de las cuentas demo. ADMIN no requiere filas:
    # su alcance es global por rol. DEMO-OTRA queda fuera del alcance de las
    # cuentas operativas para poder probar denegación entre departamentos.
    for username in (
        "demo.solicitante",
        "demo.aprobador",
        "demo.almacenista",
        "demo.comprador",
        "demo.jefe",
        "demo.temporal",
    ):
        for code in ("DEMO-MINA", "DEMO-MANT"):
            _assign_department(db, users[username].id, departments[code].id)
    for username in ("demo.gerencia", "demo.auditor"):
        for code in ("DEMO-MINA", "DEMO-MANT", "DEMO-OTRA"):
            _assign_department(db, users[username].id, departments[code].id)

    warehouse = db.execute(
        select(Warehouse).where(Warehouse.company_id == company.id, Warehouse.code == DEMO_WAREHOUSE)
    ).scalar_one_or_none()
    if warehouse is None:
        warehouse = Warehouse(
            company_id=company.id,
            mining_unit_id=unit.id,
            code=DEMO_WAREHOUSE,
            name="Almacén principal demo",
            warehouse_type="MAIN",
            allows_negative=False,
        )
        db.add(warehouse)
        db.flush()

    cost_center = db.execute(
        select(CostCenter).where(CostCenter.company_id == company.id, CostCenter.code == "CC-DEMO-MINA")
    ).scalar_one_or_none()
    if cost_center is None:
        cost_center = CostCenter(
            company_id=company.id,
            mining_unit_id=unit.id,
            code="CC-DEMO-MINA",
            name="Centro de costo mina demo",
        )
        db.add(cost_center)
        db.flush()

    equipment = db.execute(
        select(Equipment).where(Equipment.company_id == company.id, Equipment.asset_tag == "EQ-DEMO-001")
    ).scalar_one_or_none()
    if equipment is None:
        equipment = Equipment(
            company_id=company.id,
            mining_unit_id=unit.id,
            cost_center_id=cost_center.id,
            asset_tag="EQ-DEMO-001",
            description="Equipo de perforación demo",
            equipment_type="PERFORADORA",
            status="ACTIVE",
        )
        db.add(equipment)
        db.flush()

    uoms: dict[str, Uom] = {}
    for code, name in (("UND", "Unidad"), ("LT", "Litro"), ("KG", "Kilogramo"), ("M", "Metro")):
        uom = db.execute(select(Uom).where(Uom.code == code)).scalar_one_or_none()
        if uom is None:
            uom = Uom(code=code, name=name, precision=2)
            db.add(uom)
            db.flush()
        uoms[code] = uom

    items: dict[str, Item] = {}
    for code, description, uom_code, qty, cost in DEMO_ITEMS:
        item = db.execute(
            select(Item).where(Item.company_id == company.id, Item.code == code)
        ).scalar_one_or_none()
        if item is None:
            item = Item(
                company_id=company.id,
                code=code,
                description=description,
                item_type="STOCK",
                uom_id=uoms[uom_code].id,
                standard_cost=cost,
            )
            db.add(item)
            db.flush()
        items[code] = item

    supplier = db.execute(
        select(Supplier).where(Supplier.company_id == company.id, Supplier.code == "PROV-DEMO-01")
    ).scalar_one_or_none()
    if supplier is None:
        supplier = Supplier(
            company_id=company.id,
            code="PROV-DEMO-01",
            name="Proveedor ficticio demo",
            status="ACTIVE",
        )
        db.add(supplier)
        db.flush()

    for code in DOCUMENT_TYPES:
        doc_type = db.execute(select(DocumentType).where(DocumentType.code == code)).scalar_one_or_none()
        if doc_type is None:
            doc_type = DocumentType(code=code, name=code)
            db.add(doc_type)
            db.flush()
        numbering = db.execute(
            select(DocumentNumbering).where(
                DocumentNumbering.document_type_id == doc_type.id,
                DocumentNumbering.company_id == company.id,
                DocumentNumbering.mining_unit_id == unit.id,
                DocumentNumbering.series == DEMO_SERIES,
                DocumentNumbering.year == now.year,
            )
        ).scalar_one_or_none()
        if numbering is None:
            db.add(
                DocumentNumbering(
                    document_type_id=doc_type.id,
                    company_id=company.id,
                    mining_unit_id=unit.id,
                    series=DEMO_SERIES,
                    year=now.year,
                    next_number=1,
                )
            )

    admin = users["demo.admin"]
    for code, _description, uom_code, qty, _cost in DEMO_ITEMS:
        item = items[code]
        balance = db.execute(
            select(StockBalance).where(
                StockBalance.warehouse_id == warehouse.id,
                StockBalance.item_id == item.id,
                StockBalance.lot_id == NULL_UUID,
                StockBalance.location_id == NULL_UUID,
            )
        ).scalar_one_or_none()
        if balance is not None:
            continue
        balance = StockBalance(
            warehouse_id=warehouse.id,
            item_id=item.id,
            lot_id=NULL_UUID,
            location_id=NULL_UUID,
            on_hand_qty=qty,
            reserved_qty=Decimal("0"),
        )
        db.add(balance)
        db.flush()
        registry, movement_no = next_document_number(
            db,
            "INV_MOV",
            company.id,
            series=DEMO_SERIES,
            mining_unit_id=unit.id,
        )
        movement = StockMovement(
            movement_no=movement_no,
            document_registry_id=registry.id,
            movement_type="INITIAL",
            direction="IN",
            quantity=qty,
            item_id=item.id,
            warehouse_id=warehouse.id,
            lot_id=NULL_UUID,
            location_id=NULL_UUID,
            balance_after_qty=qty,
            source_document_type="SEED",
            source_document_id=None,
            idempotency_key=f"seed:initial:{code}",
            created_by=admin.id,
        )
        db.add(movement)
        db.flush()
        registry.entity_type = "StockMovement"
        registry.entity_id = movement.id
        AuditService.record(
            db,
            action="INVENTARIO_INICIAL_DEMO",
            entity_type="StockBalance",
            entity_id=balance.id,
            actor_id=admin.id,
            actor_username=admin.username,
            after={"item": code, "warehouse": DEMO_WAREHOUSE, "quantity": str(qty)},
        )
        emit(
            db,
            aggregate_type="StockMovement",
            aggregate_id=movement.id,
            event_type="INITIAL_STOCK_SEEDED",
            payload={"item": code, "quantity": str(qty)},
        )

    _seed_wms_demo(
        db,
        company=company,
        warehouse=warehouse,
        items=items,
        supplier=supplier,
        admin=admin,
    )
    _seed_sla_policies(db)

    db.commit()


def main() -> None:
    db = SessionLocal()
    try:
        seed_demo_data(db)
        print("Semilla demo aplicada correctamente.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
