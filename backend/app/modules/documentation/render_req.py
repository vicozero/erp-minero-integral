from __future__ import annotations

import io
from dataclasses import dataclass, field

from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Border, Font, Side
from openpyxl.utils import get_column_letter
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from .templates import ASSETS_DIR

PAGE_W, PAGE_H = letter  # 612 x 792

# Registrar Calibri si está disponible (Windows) para mayor fidelidad.
_FONT_REGULAR = "Helvetica"
_FONT_BOLD = "Helvetica-Bold"
try:
    pdfmetrics.registerFont(TTFont("Calibri", r"C:\Windows\Fonts\calibri.ttf"))
    pdfmetrics.registerFont(TTFont("Calibri-Bold", r"C:\Windows\Fonts\calibrib.ttf"))
    _FONT_REGULAR = "Calibri"
    _FONT_BOLD = "Calibri-Bold"
except Exception:
    pass


@dataclass
class REQLine:
    partida: int
    cantidad: str
    unidad: str
    descripcion: str
    consumo_mes: str = ""
    consumo_anio: str = ""
    existencia: str = ""
    codificacion: str = ""


@dataclass
class REQData:
    folio: str
    dia: str
    mes: str
    anio: str
    mina: str
    departamento: str
    uso_inmediato: bool = False
    existencia_almacen: bool = False
    cargo_opex: bool = False
    uso_equipo: str = ""
    proveedor_recomendado: str = ""
    lines: list[REQLine] = field(default_factory=list)
    meses_requeridos: list[str] = field(default_factory=list)  # ENE..DIC marcados
    meses_programados: list[str] = field(default_factory=list)
    approval_text: str | None = None  # texto de aprobación electrónica, si aplica


def _y(y_fitz: float) -> float:
    return PAGE_H - y_fitz


def _chunks(lines: list[REQLine], size: int = 21) -> list[list[REQLine]]:
    if not lines:
        return [[]]
    return [lines[i : i + size] for i in range(0, len(lines), size)]


MONTHS = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"]


def _draw_page(c: canvas.Canvas, data: REQData, page_lines: list[REQLine], page: int, total: int) -> None:
    # Marco general
    c.setLineWidth(0.7)
    c.rect(14.9, _y(698.2), 596.6 - 14.9, 698.2 - 101.2, stroke=1, fill=0)

    # Logo y razón social
    logo = ASSETS_DIR / "logo_req.png"
    if logo.exists():
        c.drawImage(ImageReader(str(logo)), 14.9, _y(89.9), width=69.2, height=31.6, preserveAspectRatio=True, mask="auto")
    c.setFont(_FONT_BOLD, 11)
    c.drawString(215, _y(86), "LA GUITARRA COMPAÑÍA MINERA S.A. DE C.V.")

    # Bloque fecha / mina / folio
    # cajas superiores
    c.rect(14.9, _y(140.5), 93.8, 39.3, stroke=1, fill=0)  # DIA MES AÑO
    c.rect(108.7, _y(140.5), 326.5, 39.3, stroke=1, fill=0)  # MINA / título
    c.rect(435.2, _y(140.5), 161.4, 39.3, stroke=1, fill=0)  # folio
    c.line(14.9, _y(119.3), 108.7, _y(119.3))
    c.line(43.7, _y(101.2), 43.7, _y(140.5))
    c.line(77.0, _y(101.2), 77.0, _y(140.5))
    c.setFont(_FONT_BOLD, 7)
    c.drawCentredString(29.3, _y(113), "DIA")
    c.drawCentredString(60.4, _y(113), "MES")
    c.drawCentredString(92.8, _y(113), "AÑO")
    c.setFont(_FONT_REGULAR, 9)
    c.drawCentredString(29.3, _y(133), data.dia)
    c.drawCentredString(60.4, _y(133), data.mes)
    c.drawCentredString(92.8, _y(133), data.anio)
    c.setFont(_FONT_BOLD, 9)
    c.drawCentredString(272, _y(114), f"MINA  {data.mina}".strip())
    c.setFont(_FONT_BOLD, 11)
    c.drawCentredString(272, _y(133), "REQUISICIÓN DE COMPRA")
    c.setFont(_FONT_BOLD, 9)
    folio_text = data.folio if total == 1 else f"{data.folio} ({page}/{total})"
    c.drawString(440, _y(114), "REQUISICION No.")
    c.setFont(_FONT_REGULAR, 10)
    c.drawString(440, _y(133), folio_text)

    # Bloque depto/uso/cargo
    c.rect(14.9, _y(179.4), 581.7, 38.9, stroke=1, fill=0)
    c.line(14.9, _y(161.6), 596.6, _y(161.6))
    c.line(280, _y(140.5), 280, _y(179.4))
    c.line(450, _y(140.5), 450, _y(179.4))
    c.line(531.4, _y(140.5), 531.4, _y(179.4))
    c.setFont(_FONT_BOLD, 7)
    c.drawString(18, _y(154), "DEPTO. SOLICITANTE:")
    c.drawString(285, _y(154), "USO INMEDIATO")
    c.drawString(455, _y(154), "CARGO")
    c.drawString(535, _y(154), "OPEX")
    c.drawString(285, _y(172), "EXISTENCIA ALMACEN")
    c.setFont(_FONT_REGULAR, 9)
    c.drawString(120, _y(172), (data.departamento or "")[:28])
    if data.uso_inmediato:
        c.drawString(432, _y(154), "X")
    if data.existencia_almacen:
        c.drawString(432, _y(172), "X")
    if data.cargo_opex:
        c.drawString(565, _y(154), "X")

    # Tabla principal encabezado
    main_top = 179.4
    head2 = 200.2
    body_top = 213.2
    row_h = 14.04
    # columnas principales (aprox según grid)
    cols = [14.9, 43.7, 77.0, 108.7, 449.6, 477.1, 504.2, 531.4, 596.6]
    # headers
    c.rect(14.9, _y(508.1), 581.7, 508.1 - 179.4, stroke=1, fill=0)
    c.line(14.9, _y(head2), 596.6, _y(head2))
    c.line(14.9, _y(body_top), 596.6, _y(body_top))
    for x in cols[1:-1]:
        c.line(x, _y(main_top), x, _y(508.1))
    # subcolumnas consumo
    c.line(477.1, _y(head2), 504.2, _y(head2))
    c.setFont(_FONT_BOLD, 6.5)
    c.drawCentredString((14.9 + 43.7) / 2, _y(197), "PARTIDA")
    c.drawCentredString((43.7 + 77.0) / 2, _y(197), "CANTIDAD")
    c.drawCentredString((77.0 + 108.7) / 2, _y(197), "UNIDAD")
    c.drawCentredString((108.7 + 449.6) / 2, _y(197), "DESCRIPCION")
    c.drawCentredString((449.6 + 504.2) / 2, _y(190), "CONSUMO")
    c.drawCentredString((449.6 + 477.1) / 2, _y(208), "MES")
    c.drawCentredString((477.1 + 504.2) / 2, _y(208), "AÑO")
    c.drawCentredString((504.2 + 531.4) / 2, _y(197), "EXIST.")
    c.drawCentredString((531.4 + 596.6) / 2, _y(197), "CODIFICACION")

    c.setFont(_FONT_REGULAR, 7.5)
    for i in range(21):
        y_top = body_top + i * row_h
        y_bot = y_top + row_h
        c.line(14.9, _y(y_bot), 596.6, _y(y_bot))
        cy = _y(y_top + 9.5)
        c.drawCentredString((14.9 + 43.7) / 2, cy, str(i + 1))
        if i < len(page_lines):
            line = page_lines[i]
            c.drawCentredString((43.7 + 77.0) / 2, cy, (line.cantidad or "")[:8])
            c.drawCentredString((77.0 + 108.7) / 2, cy, (line.unidad or "")[:8])
            c.drawString(112, cy, (line.descripcion or "")[:55])
            c.drawCentredString((449.6 + 477.1) / 2, cy, (line.consumo_mes or "")[:6])
            c.drawCentredString((477.1 + 504.2) / 2, cy, (line.consumo_anio or "")[:6])
            c.drawCentredString((504.2 + 531.4) / 2, cy, (line.existencia or "")[:6])
            c.drawString(534, cy, (line.codificacion or "")[:12])

    # Bloques inferiores
    def draw_month_row(y0, y1, label, marked):
        c.rect(14.9, _y(y1), 581.7, y1 - y0, stroke=1, fill=0)
        c.setFont(_FONT_BOLD, 6.5)
        c.drawString(18, _y(y0 + 10), label)
        mx0 = 108.7
        step = (596.6 - mx0) / 12.0
        c.setFont(_FONT_REGULAR, 6)
        for idx, m in enumerate(MONTHS):
            x = mx0 + idx * step
            c.line(x, _y(y0), x, _y(y1))
            c.drawCentredString(x + step / 2, _y(y0 + 10), m)
            if m in marked:
                c.drawCentredString(x + step / 2, _y(y0 + 2), "X")

    draw_month_row(508.1, 527.2, "REQUERIDO PARA:", data.meses_requeridos)
    draw_month_row(527.2, 546.4, "PROGRAMADO (ALMACEN):", data.meses_programados)

    c.rect(14.9, _y(578.9), 581.7, 32.5, stroke=1, fill=0)
    c.rect(14.9, _y(600.5), 581.7, 21.6, stroke=1, fill=0)
    c.setFont(_FONT_BOLD, 7)
    c.drawString(18, _y(560), "USO:")
    c.drawString(18, _y(592), "PROVEEDOR RECOMENDADO:")
    c.setFont(_FONT_REGULAR, 8)
    c.drawString(80, _y(560), (data.uso_equipo or "")[:70])
    c.drawString(150, _y(592), (data.proveedor_recomendado or "")[:60])

    # Firmas
    c.rect(14.9, _y(698.2), 581.7, 97.7, stroke=1, fill=0)
    c.line(211.0, _y(600.5), 211.0, _y(698.2))
    c.line(403.0, _y(600.5), 403.0, _y(698.2))
    c.setFont(_FONT_BOLD, 7)
    c.drawCentredString(113, _y(690), "FIRMA SOLICITANTE")
    c.drawCentredString(307, _y(690), "FIRMA JEFE DE ALMACEN")
    c.drawCentredString(500, _y(690), "AUTORIZACION GERENCIA")
    # Líneas de firma en blanco
    for cx in (113, 307, 500):
        c.line(cx - 70, _y(670), cx + 70, _y(670))
    if data.approval_text:
        c.setFont(_FONT_REGULAR, 6)
        c.drawCentredString(500, _y(655), f"[Aprobación electrónica: {data.approval_text[:60]}]")


def render_req_pdf(data: REQData) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    pages = _chunks(data.lines, 21)
    for idx, page_lines in enumerate(pages, start=1):
        _draw_page(c, data, page_lines, idx, len(pages))
        c.showPage()
    c.save()
    return buf.getvalue()


def render_req_xlsx(data: REQData) -> bytes:
    wb = Workbook()
    wb.remove(wb.active)
    pages = _chunks(data.lines, 21)
    thin = Side(style="thin")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    for idx, page_lines in enumerate(pages, start=1):
        ws = wb.create_sheet(title=f"REQ {idx}")
        ws.page_setup.orientation = ws.ORIENTATION_PORTRAIT
        ws.page_setup.paperSize = ws.PAPERSIZE_LETTER
        ws.page_margins.left = 0.25
        ws.page_margins.right = 0.25
        ws.page_margins.top = 0.4
        ws.page_margins.bottom = 0.4
        ws.print_area = "A1:P38"
        col_widths = [5, 6, 6, 30, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 8]
        for i, w in enumerate(col_widths, start=1):
            ws.column_dimensions[get_column_letter(i)].width = w

        logo = ASSETS_DIR / "logo_req.png"
        if logo.exists():
            img = XLImage(str(logo))
            img.width, img.height = 70, 32
            ws.add_image(img, "A1")

        ws.merge_cells("D1:M1")
        ws["D1"] = "LA GUITARRA COMPAÑÍA MINERA S.A. DE C.V."
        ws["D1"].font = Font(name="Calibri", bold=True, size=11)
        ws.merge_cells("D2:J2")
        ws["D2"] = f"MINA {data.mina}   REQUISICIÓN DE COMPRA"
        ws["D2"].font = Font(name="Calibri", bold=True, size=11)
        ws.merge_cells("K2:P2")
        folio_text = data.folio if len(pages) == 1 else f"{data.folio} ({idx}/{len(pages)})"
        ws["K2"] = f"REQUISICION No. {folio_text}"
        ws["K2"].font = Font(name="Calibri", bold=True, size=10)
        ws["A3"] = "DIA"
        ws["B3"] = "MES"
        ws["C3"] = "AÑO"
        ws["A4"] = data.dia
        ws["B4"] = data.mes
        ws["C4"] = data.anio
        ws.merge_cells("D3:G3")
        ws["D3"] = f"DEPTO. SOLICITANTE: {data.departamento or ''}"
        ws.merge_cells("H3:J3")
        ws["H3"] = f"USO INMEDIATO: {'X' if data.uso_inmediato else ''}"
        ws.merge_cells("K3:N3")
        ws["K3"] = f"EXISTENCIA ALMACEN: {'X' if data.existencia_almacen else ''}"
        ws.merge_cells("O3:P3")
        ws["O3"] = f"CARGO OPEX: {'X' if data.cargo_opex else ''}"

        # Meses en columnas editables para conservar la distribución del original.
        for col, val in enumerate(["PARTIDA","CANT.","UNIDAD","DESCRIPCION","CONS.MES","CONS.AÑO","EXIST.","CODIF.","ENE","FEB","MAR","ABR","MAY","JUN","JUL","AGO"], start=1):
            cell = ws.cell(row=6, column=col, value=val)
            cell.font = Font(name="Calibri", bold=True, size=8)
            cell.alignment = Alignment(horizontal="center", wrap_text=True)
            cell.border = border

        for i in range(21):
            r = 7 + i
            ws.cell(r, 1, i + 1)
            if i < len(page_lines):
                line = page_lines[i]
                ws.cell(r, 2, line.cantidad)
                ws.cell(r, 3, line.unidad)
                ws.cell(r, 4, line.descripcion)
                ws.cell(r, 5, line.consumo_mes)
                ws.cell(r, 6, line.consumo_anio)
                ws.cell(r, 7, line.existencia)
                ws.cell(r, 8, line.codificacion)
            for c in range(1, 17):
                ws.cell(r, c).border = border
                ws.cell(r, c).font = Font(name="Calibri", size=8)

        r0 = 29
        ws.merge_cells(start_row=r0, start_column=1, end_row=r0, end_column=4)
        ws.cell(r0, 1, "REQUERIDO PARA: " + " ".join(m for m in MONTHS if m in data.meses_requeridos)).font = Font(name="Calibri", bold=True, size=8)
        ws.merge_cells(start_row=r0+1, start_column=1, end_row=r0+1, end_column=4)
        ws.cell(r0+1, 1, "PROGRAMADO (ALMACEN): " + " ".join(m for m in MONTHS if m in data.meses_programados)).font = Font(name="Calibri", bold=True, size=8)
        ws.merge_cells(start_row=r0+2, start_column=1, end_row=r0+2, end_column=8)
        ws.cell(r0+2, 1, f"USO: {data.uso_equipo or ''}").font = Font(name="Calibri", size=8)
        ws.merge_cells(start_row=r0+3, start_column=1, end_row=r0+3, end_column=8)
        ws.cell(r0+3, 1, f"PROVEEDOR RECOMENDADO: {data.proveedor_recomendado or ''}").font = Font(name="Calibri", size=8)
        ws.merge_cells(start_row=r0+5, start_column=1, end_row=r0+5, end_column=4)
        ws.merge_cells(start_row=r0+5, start_column=5, end_row=r0+5, end_column=10)
        ws.merge_cells(start_row=r0+5, start_column=11, end_row=r0+5, end_column=16)
        ws.cell(r0+5, 1, "FIRMA SOLICITANTE").alignment = Alignment(horizontal="center")
        ws.cell(r0+5, 5, "FIRMA JEFE DE ALMACEN").alignment = Alignment(horizontal="center")
        ws.cell(r0+5, 11, "AUTORIZACION GERENCIA").alignment = Alignment(horizontal="center")
        for c in (1,5,11):
            ws.cell(r0+5, c).font = Font(name="Calibri", bold=True, size=8)

    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
