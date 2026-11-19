from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.seed import seed_demo_data
from app.modules.costing.models import CostCenter
from app.modules.identity.models import AppUser
from app.modules.inventory.models import NULL_UUID, StockBalance, StockReservation
from app.modules.inventory.service import InventoryService
from app.modules.master_data.models import Item, Uom
from app.modules.organization.models import Department, Warehouse
from app.modules.purchasing.models import PurchaseOrder
from app.modules.purchasing.service import PurchasingService
from app.modules.requisitions.service import RequisitionService
from app.modules.workflow.models import ApprovalRequest, ApprovalStep
from tests.conftest import auth_header
from tests.test_inventory import approved_requisition
from tests.test_requisitions import catalogs, create_requisition


def _committed_requisition(
    engine,
    quantities=(Decimal("10"), Decimal("3")),
    *,
    approve: bool = True,
) -> tuple[uuid.UUID, list[uuid.UUID], uuid.UUID, uuid.UUID, uuid.UUID]:
    """Crea datos sintéticos confirmados para pruebas con conexiones independientes."""
    session = Session(engine, expire_on_commit=False)
    try:
        seed_demo_data(session)
        requester = session.execute(
            select(AppUser).where(AppUser.username == "demo.solicitante")
        ).scalar_one()
        approver = session.execute(
            select(AppUser).where(AppUser.username == "demo.aprobador")
        ).scalar_one()
        department = session.execute(
            select(Department).where(Department.code == "DEMO-MINA")
        ).scalar_one()
        warehouse = session.execute(
            select(Warehouse).where(Warehouse.code == "ALM_PRINCIPAL_DEMO")
        ).scalar_one()
        cost_center = session.execute(
            select(CostCenter).where(CostCenter.code == "CC-DEMO-MINA")
        ).scalar_one()
        items = list(
            session.execute(
                select(Item).where(Item.code.in_(["DEMO-TORNILLO", "DEMO-ACEITE"]))
            ).scalars()
        )
        uoms = {row.code: row for row in session.execute(select(Uom)).scalars()}
        from app.modules.master_data.models import Supplier

        supplier = session.execute(select(Supplier).where(Supplier.code == "PROV-DEMO-01")).scalar_one()

        payload = SimpleNamespace(
            department_id=department.id,
            warehouse_id=warehouse.id,
            equipment_id=None,
            cost_center_id=cost_center.id,
            requisition_type="STOCK",
            priority="HIGH",
            justification="Concurrencia sintética Fase 4",
            observations=None,
            needed_at=None,
            work_order_no="OT-CC-001",
            lines=[
                SimpleNamespace(
                    id=None,
                    item_id=items[index].id,
                    description=items[index].description,
                    uom_id=uoms["UND" if index == 0 else "LT"].id,
                    requested_qty=quantity,
                    notes=None,
                )
                for index, quantity in enumerate(quantities)
            ],
        )
        req = RequisitionService.create(session, requester.id, payload)
        session.flush()
        RequisitionService.submit(session, requester.id, req.id)
        if approve:
            decision = SimpleNamespace(
                decisions=[
                    SimpleNamespace(
                        requisition_line_id=line.id,
                        decision="APPROVE",
                        approved_qty=line.requested_qty,
                        reason=None,
                    )
                    for line in req.lines
                ],
                reason=None,
            )
            RequisitionService.decide(session, approver.id, req.id, decision)
        session.commit()
        return req.id, [line.id for line in req.lines], warehouse.id, supplier.id, requester.id
    finally:
        session.close()


@pytest.fixture(autouse=True)
def _clean_test_db(engine):
    """Aísla cada prueba restaurando la base sintética de pruebas.

    Las pruebas de concurrencia confirman transacciones reales en conexiones
    independientes; sin este reinicio, sus registros confirmados colisionarían
    con las pruebas que usan transacciones revertidas. Solo actúa sobre la base
    de pruebas (`erp_minero_test`), nunca sobre datos reales.
    """
    _reset_test_db(engine)
    yield
    _reset_test_db(engine)


def _reserve_committed(engine, line_id: uuid.UUID, quantity: Decimal, key: str, actor_id: uuid.UUID):
    session = Session(engine, expire_on_commit=False)
    try:
        payload = SimpleNamespace(
            requisition_line_id=line_id, quantity=quantity, idempotency_key=key
        )
        result = InventoryService.reserve(session, actor_id, payload)
        session.commit()
        return result
    finally:
        session.close()


def _reset_test_db(engine) -> None:
    """Limpia y vuelve a sembrar únicamente la base sintética de pruebas."""
    from sqlalchemy import text

    schemas = ("seg", "org", "mdm", "doc", "req", "wfl", "inv", "pur", "mnt", "cost", "intg", "aud")
    session = Session(engine, expire_on_commit=False)
    try:
        schema_list = ", ".join(f"'{schema}'" for schema in schemas)
        tables = [
            row[0]
            for row in session.execute(
                text(
                    "SELECT schemaname || '.' || tablename FROM pg_tables "
                    f"WHERE schemaname IN ({schema_list})"
                )
            )
        ]
        if tables:
            session.execute(text(f"TRUNCATE TABLE {', '.join(tables)} RESTART IDENTITY CASCADE"))
        seed_demo_data(session)
        session.commit()
    finally:
        session.close()


# 1 ---------------------------------------------------------------------
def test_folio_unico_y_partidas_consecutivas(client):
    solicitante = auth_header(client, "demo.solicitante")
    catalog = catalogs(client, solicitante)
    created = create_requisition(client, solicitante, catalog)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["document_no"].startswith("REQ-LAG-")
    assert [line["line_no"] for line in body["lines"]] == [1, 2]
    assert all(line["status"] == "OPEN" for line in body["lines"])


# 2 ---------------------------------------------------------------------
def test_captura_rechaza_partidas_vacias_y_cantidades_no_positivas(client):
    solicitante = auth_header(client, "demo.solicitante")
    catalog = catalogs(client, solicitante)
    base = create_requisition(client, solicitante, catalog).json()

    invalid_description = dict(base)
    invalid_description["lines"] = [{**base["lines"][0], "description": "  "}]
    response = client.post("/api/v1/requisitions", headers=solicitante, json=invalid_description)
    assert response.status_code == 422

    invalid_qty = dict(base)
    invalid_qty["lines"] = [{**base["lines"][0], "requested_qty": "0"}]
    response = client.post("/api/v1/requisitions", headers=solicitante, json=invalid_qty)
    assert response.status_code == 422

    empty = dict(base)
    empty["lines"] = []
    response = client.post("/api/v1/requisitions", headers=solicitante, json=empty)
    assert response.status_code == 422


# 3 ---------------------------------------------------------------------
def test_borrador_editable_incluye_partidas_y_orden_de_trabajo(client):
    solicitante = auth_header(client, "demo.solicitante")
    catalog = catalogs(client, solicitante)
    created = create_requisition(client, solicitante, catalog)
    req_id = created.json()["id"]
    line_id = created.json()["lines"][0]["id"]

    response = client.patch(
        f"/api/v1/requisitions/{req_id}/draft",
        headers=solicitante,
        json={
            "priority": "URGENT",
            "justification": "Justificación revisada en borrador",
            "work_order_no": "OT-GMAO-4471",
            "lines": [
                {
                    "id": line_id,
                    "item_id": created.json()["lines"][0]["item_id"],
                    "description": "Tornillo revisado",
                    "uom_id": created.json()["lines"][0]["uom_id"],
                    "requested_qty": "7",
                }
            ],
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["work_order_no"] == "OT-GMAO-4471"
    assert body["priority"] == "URGENT"
    assert len(body["lines"]) == 2  # la partida omitida queda cancelada
    assert Decimal(body["lines"][0]["requested_qty"]) == Decimal("7")


# 4 ---------------------------------------------------------------------
def test_envio_crea_solicitud_y_paso_de_aprobacion(client, db: Session):
    solicitante = auth_header(client, "demo.solicitante")
    catalog = catalogs(client, solicitante)
    created = create_requisition(client, solicitante, catalog)
    req_id = created.json()["id"]
    sent = client.post(f"/api/v1/requisitions/{req_id}/submit", headers=solicitante)
    assert sent.status_code == 200, sent.text

    approval = db.execute(
        select(ApprovalRequest).where(ApprovalRequest.requisition_id == uuid.UUID(req_id))
    ).scalar_one()
    assert approval.status == "PENDING"
    steps = db.execute(
        select(ApprovalStep).where(ApprovalStep.approval_request_id == approval.id)
    ).scalars()
    assert len(list(steps)) == 1


# 5 ---------------------------------------------------------------------
def test_reglas_de_segregacion_autoautorizacion_y_decision_duplicada(client, db: Session):
    solicitante = auth_header(client, "demo.solicitante")
    catalog = catalogs(client, solicitante)
    created = create_requisition(client, solicitante, catalog)
    req_id = created.json()["id"]
    client.post(f"/api/v1/requisitions/{req_id}/submit", headers=solicitante)
    decisions = [
        {
            "requisition_line_id": line["id"],
            "decision": "APPROVE",
            "approved_qty": line["requested_qty"],
        }
        for line in created.json()["lines"]
    ]

    self_approval = client.post(
        f"/api/v1/requisitions/{req_id}/decide", headers=solicitante, json={"decisions": decisions}
    )
    assert self_approval.status_code == 403

    aprobador = auth_header(client, "demo.aprobador")
    first = client.post(
        f"/api/v1/requisitions/{req_id}/decide", headers=aprobador, json={"decisions": decisions}
    )
    assert first.status_code == 200, first.text
    duplicate = client.post(
        f"/api/v1/requisitions/{req_id}/decide", headers=aprobador, json={"decisions": decisions}
    )
    assert duplicate.status_code == 409


# 6 ---------------------------------------------------------------------
def test_rechazo_con_motivo_y_historial(client):
    solicitante = auth_header(client, "demo.solicitante")
    catalog = catalogs(client, solicitante)
    created = create_requisition(client, solicitante, catalog)
    req_id = created.json()["id"]
    client.post(f"/api/v1/requisitions/{req_id}/submit", headers=solicitante)

    aprobador = auth_header(client, "demo.aprobador")
    rejected = client.post(
        f"/api/v1/requisitions/{req_id}/decide",
        headers=aprobador,
        json={
            "decisions": [
                {
                    "requisition_line_id": created.json()["lines"][0]["id"],
                    "decision": "REJECT",
                    "reason": "Presupuesto insuficiente",
                }
            ],
            "reason": "Presupuesto insuficiente",
        },
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "REJECTED"
    history = client.get(f"/api/v1/requisitions/{req_id}/history", headers=solicitante)
    assert history.status_code == 200
    events = [event["event_type"] for event in history.json()]
    assert "REQUISITION_SUBMITTED" in events
    assert "REQUISITION_DECIDED" in events


# 7 ---------------------------------------------------------------------
def test_pending_qty_usa_autorizado_no_solicitado(client):
    req, catalog = approved_requisition(client, quantities=(Decimal("10"), Decimal("3")))
    aprobador = auth_header(client, "demo.aprobador")
    parcial = client.post(
        f"/api/v1/requisitions/{revert_pending_id(req)}/decide",
        headers=aprobador,
        json={"decisions": []},
    )
    assert parcial.status_code == 409  # ya decidida: no se puede volver a autorizar
    detail = client.get(f"/api/v1/requisitions/{req['id']}", headers=aprobador).json()
    assert Decimal(detail["lines"][0]["pending_qty"]) == Decimal("10")


def revert_pending_id(req: dict) -> str:
    return req["id"]


# 8 ---------------------------------------------------------------------
def test_reserva_parcial_y_anti_sobrereserva(client):
    req, catalog = approved_requisition(client, quantities=(Decimal("10"), Decimal("3")))
    almacenista = auth_header(client, "demo.almacenista")
    line_id = req["lines"][0]["id"]

    first = client.post(
        "/api/v1/inventory/reservations",
        headers=almacenista,
        json={"requisition_line_id": line_id, "quantity": "6", "idempotency_key": "f4-res-6"},
    )
    assert first.status_code == 201, first.text
    over = client.post(
        "/api/v1/inventory/reservations",
        headers=almacenista,
        json={"requisition_line_id": line_id, "quantity": "5", "idempotency_key": "f4-res-5"},
    )
    assert over.status_code == 409
    rest = client.post(
        "/api/v1/inventory/reservations",
        headers=almacenista,
        json={"requisition_line_id": line_id, "quantity": "4", "idempotency_key": "f4-res-4"},
    )
    assert rest.status_code == 201, rest.text


# 9 ---------------------------------------------------------------------
def test_idempotencia_concurrente_reserva(engine):
    req_id, line_ids, _warehouse_id, _supplier_id, actor_id = _committed_requisition(
        engine, (Decimal("10"),)
    )
    key = f"cc-reserva-idempotente-{uuid.uuid4()}"
    payload = SimpleNamespace(
        requisition_line_id=line_ids[0], quantity=Decimal("4"), idempotency_key=key
    )

    def run():
        session = Session(engine, expire_on_commit=False)
        try:
            reservation = InventoryService.reserve(session, actor_id, payload)
            session.commit()
            return reservation.id
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: run(), range(2)))
    assert results[0] == results[1]
    check = Session(engine)
    try:
        count = check.execute(
            select(__import__("sqlalchemy").func.count())
            .select_from(StockReservation)
            .where(StockReservation.idempotency_key == key)
        ).scalar_one()
    finally:
        check.close()
    assert count == 1


# 10 ---------------------------------------------------------------------
def test_concurrencia_claves_distintas_no_sobrereserva(engine):
    _req_id, line_ids, _warehouse_id, _supplier_id, actor_id = _committed_requisition(
        engine, (Decimal("10"),)
    )

    run_id = uuid.uuid4()

    def run(index: int):
        session = Session(engine, expire_on_commit=False)
        try:
            payload = SimpleNamespace(
                requisition_line_id=line_ids[0],
                quantity=Decimal("8"),
                idempotency_key=f"cc-race-{run_id}-{index}",
            )
            InventoryService.reserve(session, actor_id, payload)
            session.commit()
            return True
        except Exception:
            session.rollback()
            return False
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(run, range(2)))
    assert sorted(outcomes) == [False, True]


# 11 ---------------------------------------------------------------------
def test_cancelacion_libera_reservas_y_registra_auditoria(client, db: Session):
    req, catalog = approved_requisition(client, quantities=(Decimal("10"), Decimal("3")))
    almacenista = auth_header(client, "demo.almacenista")
    line_id = req["lines"][0]["id"]
    reserve = client.post(
        "/api/v1/inventory/reservations",
        headers=almacenista,
        json={"requisition_line_id": line_id, "quantity": "4", "idempotency_key": "f4-cancel-res"},
    )
    assert reserve.status_code == 201, reserve.text

    admin = auth_header(client, "demo.admin")
    cancelled = client.post(
        f"/api/v1/requisitions/{req['id']}/cancel",
        headers=admin,
        json={"reason": "Cancelación autorizada por administrador"},
    )
    assert cancelled.status_code == 200, cancelled.text
    reservations = db.execute(
        select(StockReservation).where(StockReservation.requisition_line_id == uuid.UUID(line_id))
    ).scalars()
    assert all(reservation.status == "RELEASED" for reservation in reservations)


# 12 ---------------------------------------------------------------------
def test_linea_rechazada_queda_cancelada_y_no_se_puede_reservar(client):
    solicitante = auth_header(client, "demo.solicitante")
    catalog = catalogs(client, solicitante)
    created = create_requisition(client, solicitante, catalog)
    req_id = created.json()["id"]
    submitted = client.post(f"/api/v1/requisitions/{req_id}/submit", headers=solicitante)
    assert submitted.status_code == 200, submitted.text
    first_line = submitted.json()["lines"][0]
    second_line = submitted.json()["lines"][1]

    aprobador = auth_header(client, "demo.aprobador")
    decided = client.post(
        f"/api/v1/requisitions/{req_id}/decide",
        headers=aprobador,
        json={
            "decisions": [
                {
                    "requisition_line_id": first_line["id"],
                    "decision": "APPROVE",
                    "approved_qty": first_line["requested_qty"],
                },
                {
                    "requisition_line_id": second_line["id"],
                    "decision": "REJECT",
                    "reason": "Artículo no disponible",
                },
            ],
            "reason": "Rechazo parcial por disponibilidad",
        },
    )
    assert decided.status_code == 200, decided.text
    body = decided.json()
    assert body["status"] in ("PARTIALLY_APPROVED", "APPROVED")
    rejected_line = next(line for line in body["lines"] if line["id"] == second_line["id"])
    assert rejected_line["status"] == "CANCELLED"
    assert Decimal(rejected_line["authorised_qty"]) == Decimal("0")

    almacenista = auth_header(client, "demo.almacenista")
    illegal_reserve = client.post(
        "/api/v1/inventory/reservations",
        headers=almacenista,
        json={
            "requisition_line_id": second_line["id"],
            "quantity": "1",
            "idempotency_key": "f4-rejected-line-res",
        },
    )
    assert illegal_reserve.status_code == 409


# 13 ---------------------------------------------------------------------
def test_expiracion_de_reserva_devuelve_saldo(client, db: Session):
    req, catalog = approved_requisition(client, quantities=(Decimal("10"), Decimal("3")))
    almacenista = auth_header(client, "demo.almacenista")
    line_id = req["lines"][0]["id"]
    balance_stmt = select(StockBalance).where(
        StockBalance.warehouse_id == uuid.UUID(catalog["warehouse"]),
        StockBalance.item_id == uuid.UUID(catalog["items"][0]),
        StockBalance.lot_id == NULL_UUID,
        StockBalance.location_id == NULL_UUID,
    )
    reserved_before = db.execute(balance_stmt).scalar_one().reserved_qty

    reserve = client.post(
        "/api/v1/inventory/reservations",
        headers=almacenista,
        json={"requisition_line_id": line_id, "quantity": "5", "idempotency_key": "f4-expire-res"},
    )
    assert reserve.status_code == 201, reserve.text
    reservation = db.get(StockReservation, uuid.UUID(reserve.json()["id"]))
    from datetime import datetime, timedelta, timezone

    reservation.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.flush()

    released = client.post("/api/v1/inventory/reservations/expire", headers=almacenista)
    assert released.status_code == 200, released.text
    assert released.json()["released"] >= 1
    db.refresh(reservation)
    assert reservation.status == "EXPIRED"
    # La liberación devuelve exactamente la cantidad reservada; el saldo previo
    # puede incluir datos confirmados por las pruebas de concurrencia.
    assert db.execute(balance_stmt).scalar_one().reserved_qty == reserved_before


# 14 ---------------------------------------------------------------------
def test_entrega_parcial_y_cierre_automatico(client):
    req, catalog = approved_requisition(client, quantities=(Decimal("6"), Decimal("3")))
    almacenista = auth_header(client, "demo.almacenista")
    for index, line in enumerate(req["lines"]):
        quantity = line["authorised_qty"]
        reserve = client.post(
            "/api/v1/inventory/reservations",
            headers=almacenista,
            json={
                "requisition_line_id": line["id"],
                "quantity": quantity,
                "idempotency_key": f"f4-close-res-{index}",
            },
        )
        assert reserve.status_code == 201, reserve.text
        issued = client.post(
            "/api/v1/inventory/issues",
            headers=almacenista,
            json={
                "requisition_line_id": line["id"],
                "quantity": quantity,
                "reservation_id": reserve.json()["id"],
                "idempotency_key": f"f4-close-issue-{index}",
            },
        )
        assert issued.status_code == 201, issued.text

    detail = client.get(f"/api/v1/requisitions/{req['id']}", headers=almacenista).json()
    assert detail["status"] == "CLOSED"
    assert Decimal(detail["lines"][0]["delivered_qty"]) == Decimal("6")


# 15 ---------------------------------------------------------------------
def test_idempotencia_concurrente_entrega(engine):
    req_id, line_ids, warehouse_id, _supplier_id, actor_id = _committed_requisition(
        engine, (Decimal("10"),)
    )
    reservation = _reserve_committed(engine, line_ids[0], Decimal("10"), f"cc-issue-res-{uuid.uuid4()}", actor_id)

    key = f"cc-entrega-idempotente-{uuid.uuid4()}"
    payload = SimpleNamespace(
        requisition_line_id=line_ids[0],
        quantity=Decimal("10"),
        reservation_id=reservation.id,
        idempotency_key=key,
    )

    def run():
        session = Session(engine, expire_on_commit=False)
        try:
            movement = InventoryService.issue(session, actor_id, payload)
            session.commit()
            return movement.id
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: run(), range(2)))
    assert results[0] == results[1]


# 16 ---------------------------------------------------------------------
def test_oc_cancelada_vuelve_a_contar_como_faltante(client):
    req, catalog = approved_requisition(client, quantities=(Decimal("10"), Decimal("3")))
    comprador = auth_header(client, "demo.comprador")
    first = client.post(
        "/api/v1/purchases/from-shortages",
        headers=comprador,
        json={
            "requisition_id": req["id"],
            "supplier_id": catalog["supplier"],
            "warehouse_id": catalog["warehouse"],
            "idempotency_key": "f4-po-primera",
        },
    )
    assert first.status_code == 201, first.text
    cancelled = client.post(
        f"/api/v1/purchases/{first.json()['id']}/cancel",
        headers=comprador,
        json={"reason": "Proveedor sin disponibilidad"},
    )
    assert cancelled.status_code == 200, cancelled.text
    second = client.post(
        "/api/v1/purchases/from-shortages",
        headers=comprador,
        json={
            "requisition_id": req["id"],
            "supplier_id": catalog["supplier"],
            "warehouse_id": catalog["warehouse"],
            "idempotency_key": "f4-po-segunda",
        },
    )
    assert second.status_code == 201, second.text
    assert Decimal(second.json()["lines"][0]["ordered_qty"]) == Decimal("10")


# 17 ---------------------------------------------------------------------
def test_adjuntos_controlados_registran_sha256_y_rechazan_tipo(client):
    solicitante = auth_header(client, "demo.solicitante")
    catalog = catalogs(client, solicitante)
    created = create_requisition(client, solicitante, catalog)
    req_id = created.json()["id"]
    content = b"%PDF-1.4 contenido sintetico de prueba"

    uploaded = client.post(
        f"/api/v1/requisitions/{req_id}/attachments",
        headers=solicitante,
        files={"file": ("cotizacion.pdf", content, "application/pdf")},
    )
    assert uploaded.status_code == 201, uploaded.text
    import hashlib

    assert uploaded.json()["sha256"] == hashlib.sha256(content).hexdigest()
    invalid = client.post(
        f"/api/v1/requisitions/{req_id}/attachments",
        headers=solicitante,
        files={"file": ("ejecutable.exe", b"MZ", "application/octet-stream")},
    )
    assert invalid.status_code == 422
    listed = client.get(f"/api/v1/requisitions/{req_id}/attachments", headers=solicitante)
    assert len(listed.json()) == 1


# 18 ---------------------------------------------------------------------
def test_idempotencia_concurrente_creacion_oc(engine):
    req_id, line_ids, warehouse_id, supplier_id, actor_id = _committed_requisition(engine)

    payload = SimpleNamespace(
        requisition_id=req_id,
        supplier_id=supplier_id,
        warehouse_id=warehouse_id,
        notes="Concurrencia OC",
        idempotency_key=f"cc-po-idempotente-{uuid.uuid4()}",
    )

    def run():
        session = Session(engine, expire_on_commit=False)
        try:
            po = PurchasingService.create_from_shortages(session, actor_id, payload)
            session.commit()
            return po.id
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: run(), range(2)))
    assert results[0] == results[1]
    check = Session(engine)
    try:
        count = check.execute(
            select(__import__("sqlalchemy").func.count())
            .select_from(PurchaseOrder)
            .where(PurchaseOrder.requisition_id == req_id)
        ).scalar_one()
    finally:
        check.close()
    assert count == 1
