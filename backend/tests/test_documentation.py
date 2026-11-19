from __future__ import annotations

import hashlib
import io
import re
from decimal import Decimal

import fitz
from openpyxl import load_workbook

from app.modules.documentation.render_req import REQData, REQLine, render_req_pdf, render_req_xlsx
from app.modules.documentation.render_va import VAData, VALine, render_va_pdf, render_va_xlsx
from tests.conftest import auth_header
from tests.test_inventory import approved_requisition
from tests.test_requisitions import catalogs

FOLIO_VA = re.compile(r"^VA-\d{6}$")


# ---------------------------------------------------------------------------
# Renderizadores (sin base de datos)
# ---------------------------------------------------------------------------
def _va_data(lines: int = 25) -> VAData:
    return VAData(
        folio="VA-000166",
        departamento="MANTENIMIENTO",
        ceco="CC-DEMO-MINA",
        area="MECANICA",
        uso_equipo="CAMION 07",
        fecha_expedicion="19/11/2026",
        lines=[
            VALine(i, f"2097{i:02d}", "1", "PZA", f"REFACCION SINTETICA {i}", "1")
            for i in range(1, lines + 1)
        ],
    )


def _req_data(lines: int = 25) -> REQData:
    return REQData(
        folio="REQ-LAG-2026-000123",
        dia="19",
        mes="11",
        anio="2026",
        mina="LA GUITARRA",
        departamento="MANTENIMIENTO",
        uso_inmediato=True,
        existencia_almacen=True,
        cargo_opex=True,
        uso_equipo="CAMION 07",
        proveedor_recomendado="PROVEEDOR SINTETICO",
        lines=[
            REQLine(i, "2", "PZA", f"MATERIAL SINTETICO {i}", "1", "1", "5", f"86{i:06d}")
            for i in range(1, lines + 1)
        ],
        meses_requeridos=["NOV"],
        meses_programados=["DIC"],
        approval_text="APPROVED 2026-11-19",
    )


def test_va_pdf_pagina_carta_apaisada_y_diez_partidas_por_hoja() -> None:
    content = render_va_pdf(_va_data(25))
    doc = fitz.open(stream=content, filetype="pdf")
    try:
        assert doc.page_count == 3
        for page in doc:
            assert (round(page.rect.width), round(page.rect.height)) == (792, 612)
        text = doc[0].get_text()
        assert "VALE DE SALIDA" in text
        assert "VA-000166 (1/3)" in text
        # El encabezado de la tabla aparece y las partidas 11..25 viven en hojas 2 y 3.
        assert "D E S C R I P C I Ó N   D E   M A T E R I A L" in text
        assert "REFACCION SINTETICA 10" in text
        assert "REFACCION SINTETICA 11" not in text
        assert "REFACCION SINTETICA 25" in doc[2].get_text()
    finally:
        doc.close()


def test_va_xlsx_conserva_hojas_area_de_impresion_y_combinaciones() -> None:
    content = render_va_xlsx(_va_data(25))
    wb = load_workbook(io.BytesIO(content))
    try:
        assert wb.sheetnames == ["VA 1", "VA 2", "VA 3"]
        ws = wb["VA 1"]
        assert ws.print_area == "'VA 1'!$A$1:$H$24"
        assert ws.page_setup.orientation == ws.ORIENTATION_LANDSCAPE
        assert "E6:G6" in {str(rng) for rng in ws.merged_cells.ranges}
        assert ws["E6"].value == "DESCRIPCIÓN DE MATERIAL"
        assert ws["B7"].value == "209701"
        assert ws["E7"].value == "REFACCION SINTETICA 1"
        assert ws["A18"].value == "CECO:"
        assert ws["A21"].value == "RECIBIDO POR:"
    finally:
        wb.close()


def test_req_pdf_pagina_carta_vertical_y_21_partidas_por_hoja() -> None:
    content = render_req_pdf(_req_data(25))
    doc = fitz.open(stream=content, filetype="pdf")
    try:
        assert doc.page_count == 2
        for page in doc:
            assert (round(page.rect.width), round(page.rect.height)) == (612, 792)
        text = doc[0].get_text()
        assert "REQUISICIÓN DE COMPRA" in text
        assert "REQ-LAG-2026-000123 (1/2)" in text
        assert "MATERIAL SINTETICO 21" in text
        assert "MATERIAL SINTETICO 22" not in text
        assert "MATERIAL SINTETICO 25" in doc[1].get_text()
        # Las firmas se imprimen en blanco cuando no hay firma capturada.
        assert "FIRMA SOLICITANTE" in text
        assert "Aprobación electrónica" in text
    finally:
        doc.close()


def test_req_xlsx_conserva_hojas_y_area_de_impresion() -> None:
    content = render_req_xlsx(_req_data(25))
    wb = load_workbook(io.BytesIO(content))
    try:
        assert wb.sheetnames == ["REQ 1", "REQ 2"]
        ws = wb["REQ 1"]
        assert ws.print_area == "'REQ 1'!$A$1:$P$38"
        assert ws.page_setup.orientation == ws.ORIENTATION_PORTRAIT
        assert ws["A3"].value == "DIA"
        assert ws["A4"].value == "19"
        assert ws["B7"].value == "2"
        assert ws["D7"].value == "MATERIAL SINTETICO 1"
        assert "REQUISICION No. REQ-LAG-2026-000123 (1/2)" in str(ws["K2"].value)
    finally:
        wb.close()


# ---------------------------------------------------------------------------
# API documental
# ---------------------------------------------------------------------------
def _draft_payload(catalog: dict, idempotency_key: str) -> dict:
    return {
        "department_id": catalog["department"],
        "warehouse_id": catalog["warehouse"],
        "mode": "DRAFT",
        "cost_center_code": "CC-DEMO-MINA",
        "area": "MANTENIMIENTO",
        "usage_equipment": "CAMION 07",
        "issue_date": "2026-11-19",
        "lines": [
            {
                "item_id": catalog["items"][0],
                "item_code": "209765",
                "uom_code": "PZA",
                "description": "Refacción sintética de prueba",
                "requested_qty": "2",
                "dispatched_qty": "0",
            }
        ],
        "idempotency_key": idempotency_key,
    }


def _kardex_count(client, headers, item_id: str) -> int:
    response = client.get("/api/v1/inventory/kardex", headers=headers, params={"item_id": item_id})
    assert response.status_code == 200, response.text
    return len(response.json())


def test_crear_vale_borrador_emite_folio_unico_sin_mover_stock(client) -> None:
    almacenista = auth_header(client, "demo.almacenista")
    catalog = catalogs(client, almacenista)
    before = _kardex_count(client, almacenista, catalog["items"][0])

    first = client.post(
        "/api/v1/documents/vouchers",
        headers=almacenista,
        json=_draft_payload(catalog, "doc-vale-borrador-001"),
    )
    assert first.status_code == 201, first.text
    second = client.post(
        "/api/v1/documents/vouchers",
        headers=almacenista,
        json=_draft_payload(catalog, "doc-vale-borrador-002"),
    )
    assert second.status_code == 201, second.text

    body = first.json()
    assert FOLIO_VA.match(body["document_no"])
    assert body["status"] == "DRAFT"
    assert body["issued_at"] is None
    assert body["template_code"] == "VA_SALIDA_ALMACEN"
    assert body["lines"][0]["requested_qty"] == "2.000000"
    assert FOLIO_VA.match(second.json()["document_no"])
    assert int(second.json()["document_no"][3:]) == int(body["document_no"][3:]) + 1

    # Descargar/crear el vale no altera existencias ni genera movimientos.
    assert _kardex_count(client, almacenista, catalog["items"][0]) == before


def test_idempotencia_devuelve_el_mismo_vale(client) -> None:
    almacenista = auth_header(client, "demo.almacenista")
    catalog = catalogs(client, almacenista)
    payload = _draft_payload(catalog, "doc-vale-idem-001")

    first = client.post("/api/v1/documents/vouchers", headers=almacenista, json=payload)
    second = client.post("/api/v1/documents/vouchers", headers=almacenista, json=payload)
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["id"] == second.json()["id"]

    listed = client.get(
        "/api/v1/documents/vouchers",
        headers=almacenista,
        params={"document_no": first.json()["document_no"]},
    )
    assert listed.status_code == 200, listed.text
    assert len(listed.json()) == 1


def test_vale_desde_requisicion_entregada_refleja_cantidad_despachada(client) -> None:
    req, catalog = approved_requisition(client)
    almacenista = auth_header(client, "demo.almacenista")
    line_id = req["lines"][0]["id"]

    reserve = client.post(
        "/api/v1/inventory/reservations",
        headers=almacenista,
        json={
            "requisition_line_id": line_id,
            "quantity": "4",
            "idempotency_key": "doc-vale-reserva-001",
        },
    )
    assert reserve.status_code == 201, reserve.text
    issue = client.post(
        "/api/v1/inventory/issues",
        headers=almacenista,
        json={
            "requisition_line_id": line_id,
            "quantity": "4",
            "reservation_id": reserve.json()["id"],
            "idempotency_key": "doc-vale-entrega-001",
        },
    )
    assert issue.status_code == 201, issue.text
    before = _kardex_count(client, almacenista, catalog["items"][0])

    response = client.post(
        "/api/v1/documents/vouchers",
        headers=almacenista,
        json={
            "department_id": catalog["department"],
            "warehouse_id": catalog["warehouse"],
            "requisition_id": req["id"],
            "mode": "DELIVERY",
            "issue_date": "2026-11-19",
            "idempotency_key": "doc-vale-entrega-001-vale",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "ISSUED"
    assert body["issued_at"] is not None
    assert body["source_requisition_id"] == req["id"]
    assert FOLIO_VA.match(body["document_no"])
    dispatched = {line["requisition_line_id"]: line for line in body["lines"]}
    assert Decimal(dispatched[line_id]["dispatched_qty"]) == Decimal("4")
    assert dispatched[line_id]["stock_movement_id"] == issue.json()["id"]

    # Crear el vale no duplica la salida de inventario.
    assert _kardex_count(client, almacenista, catalog["items"][0]) == before


def test_descarga_pdf_no_genera_movimientos_y_reimpresion_conserva_bytes(client) -> None:
    almacenista = auth_header(client, "demo.almacenista")
    catalog = catalogs(client, almacenista)
    created = client.post(
        "/api/v1/documents/vouchers",
        headers=almacenista,
        json=_draft_payload(catalog, "doc-vale-render-001"),
    )
    assert created.status_code == 201, created.text
    voucher_id = created.json()["id"]
    before = _kardex_count(client, almacenista, catalog["items"][0])

    first = client.get(f"/api/v1/documents/vouchers/{voucher_id}/pdf", headers=almacenista)
    assert first.status_code == 200, first.text
    assert first.headers["content-type"] == "application/pdf"
    assert "VA-" in first.headers["content-disposition"]
    assert first.content.startswith(b"%PDF")
    assert _kardex_count(client, almacenista, catalog["items"][0]) == before

    renders = client.get(
        f"/api/v1/documents/vouchers/{voucher_id}/renders", headers=almacenista
    )
    assert renders.status_code == 200, renders.text
    assert len(renders.json()) == 1
    assert renders.json()[0]["is_reprint"] is False
    original_sha = renders.json()[0]["sha256"]
    assert original_sha == hashlib.sha256(first.content).hexdigest()

    reprint = client.get(
        f"/api/v1/documents/vouchers/{voucher_id}/pdf",
        headers=almacenista,
        params={"reprint": "true"},
    )
    assert reprint.status_code == 200, reprint.text
    assert reprint.content == first.content
    assert _kardex_count(client, almacenista, catalog["items"][0]) == before

    renders = client.get(
        f"/api/v1/documents/vouchers/{voucher_id}/renders", headers=almacenista
    ).json()
    assert len(renders) == 2
    reprints = [item for item in renders if item["is_reprint"]]
    assert len(reprints) == 1
    assert reprints[0]["sha256"] == original_sha
    assert reprints[0]["source_render_id"] == renders[0]["id"] or reprints[0]["source_render_id"] is not None


def test_xlsx_editable_descargable_sin_efectos_de_stock(client) -> None:
    almacenista = auth_header(client, "demo.almacenista")
    catalog = catalogs(client, almacenista)
    created = client.post(
        "/api/v1/documents/vouchers",
        headers=almacenista,
        json=_draft_payload(catalog, "doc-vale-xlsx-001"),
    )
    assert created.status_code == 201, created.text
    before = _kardex_count(client, almacenista, catalog["items"][0])

    response = client.get(
        f"/api/v1/documents/vouchers/{created.json()['id']}/xlsx", headers=almacenista
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    wb = load_workbook(io.BytesIO(response.content))
    try:
        assert wb.sheetnames == ["VA 1"]
        assert wb["VA 1"]["E6"].value == "DESCRIPCIÓN DE MATERIAL"
    finally:
        wb.close()
    assert _kardex_count(client, almacenista, catalog["items"][0]) == before


def test_render_requisicion_pdf_y_xlsx(client) -> None:
    req, _catalog = approved_requisition(client)
    almacenista = auth_header(client, "demo.almacenista")

    pdf = client.get(f"/api/v1/documents/requisitions/{req['id']}/pdf", headers=almacenista)
    assert pdf.status_code == 200, pdf.text
    assert pdf.content.startswith(b"%PDF")
    doc = fitz.open(stream=pdf.content, filetype="pdf")
    try:
        assert (round(doc[0].rect.width), round(doc[0].rect.height)) == (612, 792)
        assert req["document_no"] in doc[0].get_text()
    finally:
        doc.close()

    xlsx = client.get(f"/api/v1/documents/requisitions/{req['id']}/xlsx", headers=almacenista)
    assert xlsx.status_code == 200, xlsx.text
    wb = load_workbook(io.BytesIO(xlsx.content))
    try:
        assert wb.sheetnames == ["REQ 1"]
        assert req["document_no"] in str(wb["REQ 1"]["K2"].value)
    finally:
        wb.close()

    renders = client.get(
        f"/api/v1/documents/requisitions/{req['id']}/renders", headers=almacenista
    )
    assert renders.status_code == 200, renders.text
    assert {item["document_format"] for item in renders.json()} == {"PDF", "XLSX"}


def test_alcance_por_departamento_bloquea_vale_ajeno(client) -> None:
    admin = auth_header(client, "demo.admin")
    raw_catalog = client.get("/api/v1/catalogs", headers=admin)
    assert raw_catalog.status_code == 200, raw_catalog.text
    other_department = next(
        dept["id"]
        for dept in raw_catalog.json()["departments"]
        if dept["code"] == "DEMO-OTRA"
    )
    created = client.post(
        "/api/v1/documents/vouchers",
        headers=admin,
        json={
            "department_id": other_department,
            "mode": "DRAFT",
            "issue_date": "2026-11-19",
            "lines": [
                {
                    "item_code": "SINT-001",
                    "uom_code": "PZA",
                    "description": "Partida de otro departamento",
                    "requested_qty": "1",
                    "dispatched_qty": "0",
                }
            ],
            "idempotency_key": "doc-vale-ajeno-001",
        },
    )
    assert created.status_code == 201, created.text
    voucher_id = created.json()["id"]

    almacenista = auth_header(client, "demo.almacenista")
    denied = client.get(f"/api/v1/documents/vouchers/{voucher_id}", headers=almacenista)
    assert denied.status_code == 403
    denied_pdf = client.get(f"/api/v1/documents/vouchers/{voucher_id}/pdf", headers=almacenista)
    assert denied_pdf.status_code == 403


def test_permiso_documental_requerido(client) -> None:
    # demo.solicitante puede consultar/exportar, pero no emitir vales de almacén.
    solicitante = auth_header(client, "demo.solicitante")
    catalog = catalogs(client, solicitante)
    response = client.post(
        "/api/v1/documents/vouchers",
        headers=solicitante,
        json=_draft_payload(catalog, "doc-vale-sin-permiso-001"),
    )
    assert response.status_code == 403
