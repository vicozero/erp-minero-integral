"""Contratos del Lote B.0: permisos, aliases, feature flag y esquemas.

No registra endpoints ni toca tablas. Comprueba que el inventario heredado
conserva su comportamiento y que la bandera nueva nace desactivada.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.core.config import settings
from app.main import app
from app.modules.inventory.wms_movement_schemas import (
    IssueInWms,
    KardexEntryOut,
    MovementOrderOut,
    ReceiptIn,
    ReversalIn,
    ReturnIn,
    StockState,
)
from app.shared.constants import (
    PERMISSIONS,
    PERMISSIONS_WMS_LOTE_B,
    PERMISSIONS_WMS_LOTE_B_ALIASES,
    ROLE_PERMISSIONS,
    canonical_permission,
)

_NOW = datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc)


def _payload() -> dict[str, object]:
    return {
        "warehouse_id": uuid.uuid4(),
        "item_id": uuid.uuid4(),
        "quantity": Decimal("12.500000"),
        "lot_ref_id": uuid.uuid4(),
        "location_ref_id": uuid.uuid4(),
        "occurred_at": _NOW,
        "idempotency_key": "b0-receipt-0001",
    }


def test_permisos_canonicos_y_aliases_registrados() -> None:
    for code in PERMISSIONS_WMS_LOTE_B + PERMISSIONS_WMS_LOTE_B_ALIASES:
        assert code in PERMISSIONS


def test_aliases_resuelven_sin_modificar_el_kardex_heredado() -> None:
    esperados = {
        "almacenes.entradas": "wms.receipt.create",
        "almacenes.salidas": "wms.issue.create",
        "almacenes.devoluciones": "wms.return.create",
        "almacenes.reversos": "wms.reversal.create",
        "entradas.crear": "wms.receipt.create",
        "salidas.crear": "wms.issue.create",
        "devoluciones.crear": "wms.return.create",
        "reversos.crear": "wms.reversal.create",
    }
    for alias, canonico in esperados.items():
        assert canonical_permission(alias) == canonico
    assert canonical_permission("almacenes.kardex") == "inventory.kardex.view"


def test_asignacion_de_roles_es_aditiva() -> None:
    almacen = ROLE_PERMISSIONS["ALMACENISTA"]
    assert set(PERMISSIONS_WMS_LOTE_B[:4]).issubset(almacen)  # creación
    assert set(PERMISSIONS_WMS_LOTE_B[8:]).issubset(almacen)  # consulta
    assert not set(PERMISSIONS_WMS_LOTE_B[4:8]).issubset(almacen)  # aprobación

    aprobador = ROLE_PERMISSIONS["APROBADOR"]
    assert set(PERMISSIONS_WMS_LOTE_B[4:8]).issubset(aprobador)

    for rol in ("GERENCIA", "AUDITOR"):
        assert set(PERMISSIONS_WMS_LOTE_B[8:]).issubset(ROLE_PERMISSIONS[rol])
        assert not set(PERMISSIONS_WMS_LOTE_B[:8]).issubset(ROLE_PERMISSIONS[rol])

    assert set(PERMISSIONS).issubset(set(ROLE_PERMISSIONS["ADMIN"]))


def test_feature_flag_nace_desactivado() -> None:
    assert settings.WMS_LOTE_B_ENABLED is False


def test_esquemas_usan_decimal_y_no_float() -> None:
    assert ReceiptIn.model_fields["quantity"].annotation is Decimal
    assert IssueInWms.model_fields["quantity"].annotation is Decimal
    assert ReturnIn.model_fields["quantity"].annotation is Decimal
    assert ReceiptIn.model_fields["unit_cost"].annotation == Decimal | None

    receipt = ReceiptIn.model_validate(_payload())
    assert isinstance(receipt.quantity, Decimal)
    assert receipt.stock_state is StockState.AVAILABLE
    assert receipt.source_document_type.value == "GOODS_RECEIPT"


def test_esquemas_rechazan_cantidades_invalidas_y_claves_cortas() -> None:
    payload = _payload()
    payload["quantity"] = Decimal("0")
    with pytest.raises(ValidationError):
        ReceiptIn.model_validate(payload)

    payload = _payload()
    payload["idempotency_key"] = "ab"
    with pytest.raises(ValidationError):
        ReceiptIn.model_validate(payload)

    with pytest.raises(ValidationError):
        ReversalIn.model_validate(
            {
                "movement_id": uuid.uuid4(),
                "reason": "x",
                "idempotency_key": "b0-reversal-0001",
            }
        )


def test_devolucion_y_reverso_tienen_referencia_origen() -> None:
    payload = _payload()
    payload["return_of_movement_id"] = uuid.uuid4()
    retorno = ReturnIn.model_validate(payload)
    assert retorno.stock_state is StockState.INSPECTION

    reverso = ReversalIn.model_validate(
        {
            "movement_id": uuid.uuid4(),
            "reason": "Correccion autorizada de prueba",
            "idempotency_key": "b0-reversal-0002",
        }
    )
    assert reverso.approved_by is None


def test_app_no_registra_rutas_nuevas_de_movimientos() -> None:
    rutas = {ruta.path for ruta in app.routes}
    assert not any("/wms/movements" in ruta for ruta in rutas)
    assert app.openapi()["info"]["title"]


def test_salidas_y_orden_wms_tienen_contrato() -> None:
    payload = _payload()
    payload["requisition_line_id"] = uuid.uuid4()
    payload["delivery_seq"] = 1
    salida = IssueInWms.model_validate(payload)
    assert salida.stock_state is StockState.AVAILABLE

    assert "document_no" in MovementOrderOut.model_fields
    assert "signed_running_qty" in KardexEntryOut.model_fields
