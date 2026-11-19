"""Genera evidencias estructurales de los formatos VA y REQ.

Uso (desde ``backend``)::

    python scripts/generar_evidencia_formatos.py

Solo usa datos sintéticos. No compara imágenes píxel a píxel: produce un
reporte con geometría, fuentes, imágenes incrustadas, paginación y hashes
para revisión humana.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

import fitz
from openpyxl import load_workbook

from app.modules.documentation.render_req import REQData, REQLine, render_req_pdf, render_req_xlsx
from app.modules.documentation.render_va import VAData, VALine, render_va_pdf, render_va_xlsx

BACKEND_DIR = Path(__file__).resolve().parents[1]
REFERENCE_DIR = BACKEND_DIR.parent / "docs" / "plantillas_referencia"
EVIDENCE_DIR = BACKEND_DIR.parent / "docs" / "EVIDENCIA_FORMATOS"

VA_REFERENCE = REFERENCE_DIR / "VA-000162.pdf"
REQ_REFERENCE = REFERENCE_DIR / "Requisicion_REQ-0006_JL-03_2026-11-13.pdf"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _pdf_facts(path: Path | None = None, *, content: bytes | None = None) -> dict:
    doc = fitz.open(path) if path is not None else fitz.open(stream=content, filetype="pdf")
    try:
        fonts: Counter[str] = Counter()
        for page in doc:
            for block in page.get_text("dict")["blocks"]:
                if block.get("type") != 0:
                    continue
                for line in block["lines"]:
                    for span in line["spans"]:
                        fonts[span["font"]] += 1
        return {
            "paginas": doc.page_count,
            "tamano_pagina_1_pt": [round(doc[0].rect.width, 1), round(doc[0].rect.height, 1)],
            "imagenes_pagina_1": len(doc[0].get_images(full=True)),
            "trazos_pagina_1": len(doc[0].get_drawings()),
            "fuentes": dict(fonts),
        }
    finally:
        doc.close()


def _xlsx_facts(content: bytes) -> dict:
    wb = load_workbook(__import__("io").BytesIO(content))
    try:
        ws = wb[wb.sheetnames[0]]
        return {
            "hojas": wb.sheetnames,
            "area_impresion": str(ws.print_area),
            "orientacion": ws.page_setup.orientation,
            "papel": ws.page_setup.paperSize,
            "combinaciones": sorted(str(rng) for rng in ws.merged_cells.ranges)[:12],
            "encabezado_tabla": ws["E6"].value if ws.title.startswith("VA") else ws["D6"].value,
        }
    finally:
        wb.close()


def _save_png(pdf_content: bytes, page_index: int, target: Path) -> None:
    doc = fitz.open(stream=pdf_content, filetype="pdf")
    try:
        pix = doc[page_index].get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
        pix.save(target)
    finally:
        doc.close()


def _va_data() -> VAData:
    return VAData(
        folio="VA-000166",
        departamento="MANTENIMIENTO (DATO SINTETICO)",
        ceco="CC-SINT-01",
        area="MECANICA",
        uso_equipo="EQUIPO SINTETICO 07",
        fecha_expedicion="19/11/2026",
        lines=[
            VALine(i, f"SINT-{i:05d}", str(i % 4 + 1), "PZA", f"ARTICULO SINTETICO {i}", str(i % 2 + 1))
            for i in range(1, 26)
        ],
    )


def _req_data() -> REQData:
    return REQData(
        folio="REQ-SINT-2026-000001",
        dia="19",
        mes="11",
        anio="2026",
        mina="MINA SINTETICA",
        departamento="MANTENIMIENTO (DATO SINTETICO)",
        uso_inmediato=True,
        existencia_almacen=True,
        cargo_opex=True,
        uso_equipo="EQUIPO SINTETICO 07",
        proveedor_recomendado="PROVEEDOR SINTETICO",
        lines=[
            REQLine(i, str(i % 4 + 1), "PZA", f"MATERIAL SINTETICO {i}", "1", "1", "5", f"SINT{i:05d}")
            for i in range(1, 26)
        ],
        meses_requeridos=["NOV"],
        meses_programados=["DIC"],
        approval_text="APROBADO ELECTRONICAMENTE 2026-11-19",
    )


def main() -> None:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    report: dict = {"advertencia": "Comparación estructural; no sustituye revisión visual humana."}

    va_pdf = render_va_pdf(_va_data())
    va_xlsx = render_va_xlsx(_va_data())
    (EVIDENCE_DIR / "VA_sintetico.pdf").write_bytes(va_pdf)
    (EVIDENCE_DIR / "VA_sintetico.xlsx").write_bytes(va_xlsx)
    _save_png(va_pdf, 0, EVIDENCE_DIR / "VA_sintetico_pagina1.png")
    _save_png(va_pdf, 1, EVIDENCE_DIR / "VA_sintetico_pagina2.png")
    report["VA"] = {
        "plantilla_referencia": {
            "archivo": VA_REFERENCE.name,
            "sha256": _sha(VA_REFERENCE.read_bytes()),
            **_pdf_facts(path=VA_REFERENCE),
        },
        "generado": {
            "pdf": {"sha256": _sha(va_pdf), **_pdf_facts(content=va_pdf)},
            "xlsx": {"sha256": _sha(va_xlsx), **_xlsx_facts(va_xlsx)},
            "partidas_por_hoja": 10,
            "partidas_totales": 25,
        },
    }

    req_pdf = render_req_pdf(_req_data())
    req_xlsx = render_req_xlsx(_req_data())
    (EVIDENCE_DIR / "REQ_sintetico.pdf").write_bytes(req_pdf)
    (EVIDENCE_DIR / "REQ_sintetico.xlsx").write_bytes(req_xlsx)
    _save_png(req_pdf, 0, EVIDENCE_DIR / "REQ_sintetico_pagina1.png")
    report["REQ"] = {
        "plantilla_referencia": {
            "archivo": REQ_REFERENCE.name,
            "sha256": _sha(REQ_REFERENCE.read_bytes()),
            **_pdf_facts(path=REQ_REFERENCE),
        },
        "generado": {
            "pdf": {"sha256": _sha(req_pdf), **_pdf_facts(content=req_pdf)},
            "xlsx": {"sha256": _sha(req_xlsx), **_xlsx_facts(req_xlsx)},
            "partidas_por_hoja": 21,
            "partidas_totales": 25,
        },
    }

    (EVIDENCE_DIR / "reporte_estructural.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# Reporte estructural de formatos",
        "",
        "> Comparación estructural con las plantillas autorizadas. No es una comparación",
        "> píxel a píxel ni sustituye la revisión visual humana.",
        "",
    ]
    for key, title in (("VA", "Vale de salida"), ("REQ", "Requisición de compra")):
        block = report[key]
        ref = block["plantilla_referencia"]
        gen = block["generado"]
        lines += [
            f"## {title}",
            "",
            f"- Referencia: `{ref['archivo']}` SHA-256 `{ref['sha256']}`.",
            f"- Referencia: {ref['paginas']} página, {ref['tamano_pagina_1_pt']} pt, "
            f"{ref['imagenes_pagina_1']} imagen(es), {ref['trazos_pagina_1']} trazos.",
            f"- Generado PDF: {gen['pdf']['paginas']} páginas, {gen['pdf']['tamano_pagina_1_pt']} pt, "
            f"{gen['pdf']['imagenes_pagina_1']} imagen(es) en la primera página.",
            f"- Generado PDF SHA-256: `{gen['pdf']['sha256']}`.",
            f"- Generado XLSX: hojas `{', '.join(gen['xlsx']['hojas'])}`, "
            f"área `{gen['xlsx']['area_impresion']}`, orientación `{gen['xlsx']['orientacion']}`.",
            f"- Generado XLSX SHA-256: `{gen['xlsx']['sha256']}`.",
            f"- Paginación: {gen['partidas_por_hoja']} partidas por hoja, "
            f"{gen['partidas_totales']} partidas sintéticas.",
            f"- Fuentes referencia: `{ref['fuentes']}`.",
            f"- Fuentes generado: `{gen['pdf']['fuentes']}`.",
            "",
        ]
    lines += [
        "## Evidencias visuales",
        "",
        "- `VA_sintetico_pagina1.png`, `VA_sintetico_pagina2.png`",
        "- `REQ_sintetico_pagina1.png`",
        "",
        "Los archivos PDF/XLSX deben abrirse y revisarse con la plantilla autorizada.",
        "",
    ]
    (EVIDENCE_DIR / "reporte_estructural.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Evidencias generadas en {EVIDENCE_DIR}")


if __name__ == "__main__":
    main()
