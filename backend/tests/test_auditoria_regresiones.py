"""Regresiones de la auditoría integral: defensas que deben permanecer.

Las pruebas usan la base sintética ``erp_minero_test`` y las utilidades de
las suites existentes. No modifican la base de desarrollo.
"""

from __future__ import annotations

import importlib.util
import tempfile
import uuid
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.identity.models import AppUser
from app.modules.identity.service import IdentityService
from app.modules.master_data.models import StorageLocation
from app.modules.organization.models import Warehouse
from tests.conftest import auth_header
from tests.test_wms_designer import _draft, _element, _payload, _warehouse_id


def test_downgrade_de_migracion_exige_autorizacion(monkeypatch: pytest.MonkeyPatch) -> None:
    ruta = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "versions"
        / "d147e7ec92fb_tablas_iniciales_por_dominio.py"
    )
    spec = importlib.util.spec_from_file_location("mig_d147_auditoria", ruta)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)

    monkeypatch.delenv("ALLOW_DESTRUCTIVE_DOWNGRADE", raising=False)
    with pytest.raises(RuntimeError, match="Downgrade bloqueado"):
        modulo.downgrade()

    monkeypatch.setenv("ALLOW_DESTRUCTIVE_DOWNGRADE", "1")
    operaciones: list[str] = []
    monkeypatch.setattr(
        modulo.op, "drop_table", lambda *args, **kwargs: operaciones.append("tabla")
    )
    monkeypatch.setattr(
        modulo.op, "drop_index", lambda *args, **kwargs: operaciones.append("indice")
    )
    modulo.downgrade()
    assert len(operaciones) >= 40


def test_admin_comun_no_puede_restablecer_superadministrador(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    superadmin = db.execute(
        select(AppUser).where(AppUser.username == "demo.admin")
    ).scalar_one()
    comun = db.execute(
        select(AppUser).where(AppUser.username == "demo.solicitante")
    ).scalar_one()
    roles_reales = IdentityService.role_codes
    roles_simulados = {
        superadmin.id: ["SUPERADMIN"],
        comun.id: ["ADMIN"],
    }
    monkeypatch.setattr(
        IdentityService,
        "role_codes",
        staticmethod(
            lambda _db, user_id: roles_simulados.get(user_id, roles_reales(_db, user_id))
        ),
    )

    with pytest.raises(HTTPException) as fallo:
        IdentityService.reset_password(db, superadmin.id, comun.id, "Prueba de auditoría")
    assert fallo.value.status_code == 403


def test_plano_rechaza_ubicacion_wms_de_otro_almacen(
    client: TestClient, db: Session
) -> None:
    headers = auth_header(client)
    warehouse_id = _warehouse_id(db)
    draft = _draft(client, headers, warehouse_id)
    original = db.get(Warehouse, warehouse_id)
    assert original is not None

    otro = Warehouse(
        company_id=original.company_id,
        mining_unit_id=original.mining_unit_id,
        code="ALM_AUD_OTRO",
        name="Almacén ajeno de prueba",
        warehouse_type="SURFACE",
        allows_negative=False,
    )
    db.add(otro)
    db.flush()
    ubicacion_ajena = StorageLocation(
        warehouse_id=otro.id,
        code="AUD-LOC-AJENA",
        location_type="STANDARD",
        qr_token=f"auditoria-{uuid.uuid4().hex}",
    )
    db.add(ubicacion_ajena)
    db.flush()

    respuesta = client.put(
        f"/api/v1/wms/plans/{draft['id']}?warehouse_id={warehouse_id}",
        json=_payload(
            draft["revision"],
            [_element("pos-aud", type="POSITION", wms_location_id=str(ubicacion_ajena.id))],
        ),
        headers=headers,
    )
    assert respuesta.status_code == 422, respuesta.text
    assert "no pertenecen" in respuesta.json()["detail"]


def test_asistente_rack_valida_capacidad_y_altura_acumulada(
    client: TestClient, db: Session
) -> None:
    headers = auth_header(client)
    warehouse_id = _warehouse_id(db)
    draft = _draft(client, headers, warehouse_id)
    blueprint = {
        "name": "Rack auditoría",
        "code": "RACK-AUD",
        "zone": "A",
        "aisle": "01",
        "rack": "01",
        "modules": 1,
        "levels": 1,
        "positions_per_level": 1,
        "width": 100,
        "depth": 20,
        "level_height": 10,
        "orientation": 0,
        "capacity_per_position": 10,
        "capacity_validated": True,
        "location_type": "STANDARD",
        "x": 10,
        "y": 10,
        "create_locations": False,
    }

    sin_capacidad = client.post(
        f"/api/v1/wms/plans/{draft['id']}/racks?warehouse_id={warehouse_id}",
        json={**blueprint, "code": "RACK-AUD-CAP", "capacity_per_position": 0},
        headers=headers,
    )
    assert sin_capacidad.status_code == 422, sin_capacidad.text

    altura_excesiva = client.post(
        f"/api/v1/wms/plans/{draft['id']}/racks?warehouse_id={warehouse_id}",
        json={**blueprint, "code": "RACK-AUD-ALT", "levels": 100, "level_height": 10_000},
        headers=headers,
    )
    assert altura_excesiva.status_code == 422, altura_excesiva.text


def test_slugs_que_colisionan_no_duplican_ids_de_escena(
    client: TestClient, db: Session
) -> None:
    headers = auth_header(client)
    warehouse_id = _warehouse_id(db)
    draft = _draft(client, headers, warehouse_id)
    comun = {
        "name": "Rack slug",
        "zone": "A",
        "aisle": "01",
        "rack": "01",
        "modules": 1,
        "levels": 1,
        "positions_per_level": 1,
        "width": 20,
        "depth": 10,
        "level_height": 10,
        "orientation": 0,
        "capacity_per_position": 1,
        "capacity_validated": False,
        "location_type": "STANDARD",
        "x": 10,
        "y": 10,
        "create_locations": False,
    }
    for code in ("RACK-A.01", "RACK-A-01"):
        response = client.post(
            f"/api/v1/wms/plans/{draft['id']}/racks?warehouse_id={warehouse_id}",
            json={**comun, "code": code},
            headers=headers,
        )
        assert response.status_code == 201, response.text

    from tests.test_wms_designer import _workspace

    elementos = _workspace(client, headers, warehouse_id)["draft"]["elements"]
    ids = [item["id"] for item in elementos]
    assert len(ids) == len(set(ids))


def test_publicacion_devuelve_permisos_reales_del_actor(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = auth_header(client)
    warehouse_id = _warehouse_id(db)
    draft = _draft(client, headers, warehouse_id)
    guardado = client.put(
        f"/api/v1/wms/plans/{draft['id']}?warehouse_id={warehouse_id}",
        json=_payload(draft["revision"], [_element("aud-pub-1")]),
        headers=headers,
    )
    assert guardado.status_code == 200, guardado.text
    draft = guardado.json()

    monkeypatch.setattr(
        IdentityService,
        "has_permission",
        staticmethod(
            lambda _db, _user_id, code: code == "warehouse.plan.publish"
        ),
    )
    respuesta = client.post(
        f"/api/v1/wms/plans/{draft['id']}/publish"
        f"?warehouse_id={warehouse_id}&revision={draft['revision']}",
        headers=headers,
    )
    assert respuesta.status_code == 200, respuesta.text
    espacio = respuesta.json()
    borrador = espacio["draft"]
    assert borrador is not None
    assert borrador["can_publish"] is True
    assert borrador["can_edit"] is False


def test_reimpresion_sin_archivo_original_no_regenera_bytes(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.config import settings
    from tests.test_documentation import _draft_payload
    from tests.test_requisitions import catalogs

    almacenista = auth_header(client, "demo.almacenista")
    catalog = catalogs(client, almacenista)
    created = client.post(
        "/api/v1/documents/vouchers",
        headers=almacenista,
        json=_draft_payload(catalog, "aud-reimpresion-original"),
    )
    assert created.status_code == 201, created.text
    voucher_id = created.json()["id"]
    original = client.get(
        f"/api/v1/documents/vouchers/{voucher_id}/pdf", headers=almacenista
    )
    assert original.status_code == 200, original.text

    directorio_auditoria = Path(
        tempfile.mkdtemp(
            prefix="auditoria-reimpresion-",
            dir=r"C:\Users\Dell\AppData\Local\Temp\opencode",
        )
    )
    monkeypatch.setattr(settings, "DOCUMENT_STORAGE_DIR", directorio_auditoria)
    reprint = client.get(
        f"/api/v1/documents/vouchers/{voucher_id}/pdf",
        headers=almacenista,
        params={"reprint": "true"},
    )
    assert reprint.status_code == 409, reprint.text
    renders = client.get(
        f"/api/v1/documents/vouchers/{voucher_id}/renders", headers=almacenista
    ).json()
    assert len(renders) == 1
