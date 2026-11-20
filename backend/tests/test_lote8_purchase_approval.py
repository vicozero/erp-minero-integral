from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import event, text
from sqlalchemy.orm import Session

from tests.conftest import auth_header
from tests.test_inventory import approved_requisition
from tests.test_purchases import create_po


def test_comprador_no_aprueba_su_propia_orden(client: TestClient, db: Session) -> None:
    req, catalog = approved_requisition(client)
    comprador = auth_header(client, "demo.comprador")
    po = create_po(client, comprador, catalog, req["id"])
    assert po.status_code == 201, po.text
    purchase_order_id = po.json()["id"]

    commits: list[int] = []

    def _on_commit(session: Session) -> None:
        commits.append(1)

    event.listen(db, "after_commit", _on_commit)
    try:
        denied = client.post(
            f"/api/v1/purchases/{purchase_order_id}/approve",
            headers=comprador,
        )
    finally:
        event.remove(db, "after_commit", _on_commit)
    assert denied.status_code == 403, denied.text
    assert "comprador" in denied.json()["detail"]
    # La rama de rechazo no retorna: el router debe confirmar explícitamente
    # el evento; comprobar el commit evita que un flush dentro de la prueba
    # enmascare el defecto.
    assert commits, "El evento de rechazo debe quedar confirmado"
    assert client.get(f"/api/v1/purchases/{purchase_order_id}", headers=comprador).json()["status"] == "DRAFT"

    audit = db.execute(
        text(
            """
            SELECT action, detail, entity_id
            FROM aud.audit_log
            WHERE action = 'PURCHASE_ORDER_SELF_APPROVAL_DENIED'
            ORDER BY occurred_at DESC
            LIMIT 1
            """
        )
    ).mappings().first()
    assert audit is not None
    assert audit["detail"] == "El comprador que creó la orden no puede aprobarla."

    approved = client.post(
        f"/api/v1/purchases/{purchase_order_id}/approve",
        headers=auth_header(client),
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "APPROVED"
