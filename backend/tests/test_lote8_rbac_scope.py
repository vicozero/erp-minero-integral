from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.identity.models import AppUser, UserDepartment, UserRole
from app.modules.identity.service import IdentityService
from app.modules.organization.models import MiningUnit, Warehouse
from tests.conftest import auth_header
from tests.test_inventory import approved_requisition
from tests.test_purchases import create_po
from tests.test_requisitions import catalogs, create_requisition


def _warehouse_in_unit(db: Session, unit_code: str, code: str) -> Warehouse:
    unit = db.execute(select(MiningUnit).where(MiningUnit.code == unit_code)).scalar_one()
    warehouse = Warehouse(
        company_id=unit.company_id,
        mining_unit_id=unit.id,
        code=code,
        name="Almacén sintético para prueba de alcance del Lote 8",
        warehouse_type="SURFACE",
        allows_negative=False,
    )
    db.add(warehouse)
    db.flush()
    return warehouse


def _other_unit_warehouse(db: Session) -> Warehouse:
    return _warehouse_in_unit(db, "LAG_OTRA_DEMO", "ALM_FUERA_LOTE8")


def _same_unit_warehouse(db: Session) -> Warehouse:
    return _warehouse_in_unit(db, "LAG_DEMO", "ALM_RESTRINGIDA_LOTE8")


def _restrict_user_to_warehouse(db: Session, username: str, warehouse_id: uuid.UUID) -> None:
    """Deja al usuario sin unidades por departamento y sólo con este almacén."""
    user = db.execute(select(AppUser).where(AppUser.username == username)).scalar_one()
    for assignment in db.execute(
        select(UserDepartment).where(
            UserDepartment.user_id == user.id,
            UserDepartment.revoked_at.is_(None),
        )
    ).scalars():
        assignment.revoked_at = datetime.now(timezone.utc)
    role_id = db.execute(
        select(UserRole.role_id).where(UserRole.user_id == user.id).limit(1)
    ).scalar_one()
    db.add(
        UserRole(
            user_id=user.id,
            role_id=role_id,
            scope_type="WAREHOUSE",
            scope_id=warehouse_id,
        )
    )
    db.flush()


def _restricted_approved_requisition(client: TestClient, warehouse_id: uuid.UUID) -> tuple[dict, dict]:
    admin = auth_header(client)
    catalog = catalogs(client, admin)
    restricted_catalog = {**catalog, "warehouse": str(warehouse_id)}
    created = create_requisition(
        client,
        admin,
        restricted_catalog,
        quantities=(Decimal("2"), Decimal("1")),
    )
    assert created.status_code == 201, created.text
    req_id = created.json()["id"]
    submitted = client.post(f"/api/v1/requisitions/{req_id}/submit", headers=admin)
    assert submitted.status_code == 200, submitted.text

    decision = client.post(
        f"/api/v1/requisitions/{req_id}/decide",
        headers=auth_header(client, "demo.aprobador"),
        json={
            "decisions": [
                {
                    "requisition_line_id": line["id"],
                    "decision": "APPROVE",
                    "approved_qty": line["requested_qty"],
                }
                for line in submitted.json()["lines"]
            ]
        },
    )
    assert decision.status_code == 200, decision.text
    return decision.json(), restricted_catalog


def test_alcance_de_almacen_es_compartido_y_admite_rol_explicito(client: TestClient, db: Session) -> None:
    warehouse = _other_unit_warehouse(db)
    admin_user = db.execute(select(AppUser).where(AppUser.username == "demo.admin")).scalar_one()
    operator = db.execute(select(AppUser).where(AppUser.username == "demo.almacenista")).scalar_one()

    assert IdentityService.allowed_warehouse_ids(db, admin_user.id) is None
    permitted = IdentityService.allowed_warehouse_ids(db, operator.id)
    assert permitted is not None
    assert warehouse.id not in permitted

    _restrict_user_to_warehouse(db, "demo.almacenista", warehouse.id)
    assert warehouse.id in IdentityService.allowed_warehouse_ids(db, operator.id)


def test_inventario_rechaza_almacen_fuera_de_alcance(client: TestClient, db: Session) -> None:
    warehouse = _same_unit_warehouse(db)
    catalog = catalogs(client, auth_header(client, "demo.solicitante"))
    _restrict_user_to_warehouse(db, "demo.almacenista", uuid.UUID(catalog["warehouse"]))
    almacenista = auth_header(client, "demo.almacenista")
    admin = auth_header(client)

    params = {"item_id": catalog["items"][0], "warehouse_id": catalog["warehouse"]}
    assert client.get("/api/v1/inventory/availability", params=params, headers=almacenista).status_code == 200

    foreign_params = {**params, "warehouse_id": str(warehouse.id)}
    denied = client.get("/api/v1/inventory/availability", params=foreign_params, headers=almacenista)
    assert denied.status_code == 403
    assert "almacén" in denied.json()["detail"]
    assert client.get("/api/v1/inventory/availability", params=foreign_params, headers=admin).status_code == 200


def test_reserva_rechaza_partida_de_almacen_ajeno(client: TestClient, db: Session) -> None:
    warehouse = _same_unit_warehouse(db)
    catalog = catalogs(client, auth_header(client, "demo.solicitante"))
    _restrict_user_to_warehouse(db, "demo.almacenista", uuid.UUID(catalog["warehouse"]))
    req, _ = _restricted_approved_requisition(client, warehouse.id)

    denied = client.post(
        "/api/v1/inventory/reservations",
        headers=auth_header(client, "demo.almacenista"),
        json={
            "requisition_line_id": req["lines"][0]["id"],
            "quantity": "1",
            "idempotency_key": "lote8-reserva-fuera-alcance",
        },
    )
    assert denied.status_code == 403
    assert "almacén" in denied.json()["detail"]


def test_compras_oculta_y_rechaza_oc_de_almacen_ajeno(client: TestClient, db: Session) -> None:
    warehouse = _same_unit_warehouse(db)
    catalog = catalogs(client, auth_header(client, "demo.solicitante"))
    _restrict_user_to_warehouse(db, "demo.comprador", uuid.UUID(catalog["warehouse"]))
    comprador = auth_header(client, "demo.comprador")
    admin = auth_header(client)

    req, catalog = approved_requisition(client)
    own = create_po(client, comprador, catalog, req["id"])
    assert own.status_code == 201, own.text

    foreign_req, foreign_catalog = _restricted_approved_requisition(client, warehouse.id)
    foreign = create_po(client, admin, foreign_catalog, foreign_req["id"])
    assert foreign.status_code == 201, foreign.text

    denied = client.get(f"/api/v1/purchases/{foreign.json()['id']}", headers=comprador)
    assert denied.status_code == 403

    ids = {row["id"] for row in client.get("/api/v1/purchases", headers=comprador).json()}
    assert own.json()["id"] in ids
    assert foreign.json()["id"] not in ids

    denied_create = create_po(client, comprador, foreign_catalog, req["id"])
    assert denied_create.status_code == 403


def test_asignacion_de_roles_valida_alcance_por_almacen_y_unidad(client: TestClient, db: Session) -> None:
    admin = auth_header(client)
    user = db.execute(select(AppUser).where(AppUser.username == "demo.solicitante")).scalar_one()
    url = f"/api/v1/admin/users/{user.id}/roles"

    sin_id = client.post(
        url,
        headers=admin,
        json={"role_code": "ALMACENISTA", "scope_type": "WAREHOUSE", "scope_id": None},
    )
    assert sin_id.status_code == 422

    inexistente = client.post(
        url,
        headers=admin,
        json={"role_code": "ALMACENISTA", "scope_type": "WAREHOUSE", "scope_id": str(uuid.uuid4())},
    )
    assert inexistente.status_code == 422

    unidad_inexistente = client.post(
        url,
        headers=admin,
        json={"role_code": "ALMACENISTA", "scope_type": "MINING_UNIT", "scope_id": str(uuid.uuid4())},
    )
    assert unidad_inexistente.status_code == 422

    warehouse = _same_unit_warehouse(db)
    valido = client.post(
        url,
        headers=admin,
        json={"role_code": "ALMACENISTA", "scope_type": "WAREHOUSE", "scope_id": str(warehouse.id)},
    )
    assert valido.status_code == 200, valido.text
    assert warehouse.id in IdentityService.allowed_warehouse_ids(db, user.id)
