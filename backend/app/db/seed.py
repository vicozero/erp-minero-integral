from __future__ import annotations

import uuid
from datetime import datetime, timezone
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
from app.modules.inventory.models import NULL_UUID, StockBalance, StockMovement
from app.modules.maintenance.models import Equipment
from app.modules.master_data.models import Item, Supplier, Uom
from app.modules.organization.models import Company, Department, MiningUnit, Warehouse
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
