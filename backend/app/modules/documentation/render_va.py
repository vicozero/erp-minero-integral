from __future__ import annotations

import io
from dataclasses import dataclass
from decimal import Decimal

from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Border, Font, Side
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from .templates import ASSETS_DIR

PAGE_W, PAGE_H = landscape(letter)  # 792 x 612


@dataclass
class VALine:
    partida: int
    codigo: str
    cantidad_solicitada: str
    unidad: str
    descripcion: str
    cantidad_despachada: str


@dataclass
class VAData:
    folio: str
    departamento: str
    ceco: str
    area: str
    uso_equipo: str
    fecha_expedicion: str
    lines: list[VALine]


def _fmt_qty(value: Decimal | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    text = format(value.normalize(), "f") if value == value.to_integral() else format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _chunks(lines: list[VALine], size: int = 10) -> list[list[VALine]]:
    if not lines:
        return [[]]
    return [lines[i : i + size] for i in range(0, len(lines), size)]


# --- PDF ---------------------------------------------------------------------

# Fitz (top-left origin) -> ReportLab (bottom-left origin)
def _y(y_fitz: float) -> float:
    return PAGE_H - y_fitz


def _draw_page(c: canvas.Canvas, data: VAData, page_lines: list[VALine], page: int, total: int) -> None:
    c.setLineWidth(0.8)
    # Marco exterior
    c.rect(12, _y(529), 768, 529 - 89.7, stroke=1, fill=0)

    # Logo
    logo = ASSETS_DIR / "logo_va.png"
    if logo.exists():
        c.drawImage(ImageReader(str(logo)), 47.8, _y(163.4), width=148, height=67.3, preserveAspectRatio=True, mask="auto")

    # Encabezado
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(391.5, _y(103), "LA GUITARRA COMPAÑÍA MINERA SA DE CV")
    c.setFont("Helvetica-Bold", 11)
    c.drawString(649, _y(103), "F O L I O")
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(391.5, _y(130), "VALE DE SALIDA")
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(391.5, _y(146), "ALMACÉN")
    c.setFont("Helvetica-Bold", 14)
    folio_text = data.folio if total == 1 else f"{data.folio} ({page}/{total})"
    c.drawString(620, _y(143), folio_text)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(270, _y(159), "DEPARTAMENTO:")
    c.setFont("Helvetica", 11)
    c.drawString(370, _y(159), (data.departamento or "")[:40])

    # Encabezado tabla
    x_edges = [12, 54.5, 122.6, 184.4, 231.7, 702.2, 780]
    header_top = 174.7
    header_bottom = 208.3
    for x in x_edges:
        c.line(x, _y(header_top), x, _y(384.7))
    c.line(12, _y(header_top), 780, _y(header_top))
    c.line(12, _y(header_bottom), 780, _y(header_bottom))

    c.setFont("Helvetica-Bold", 7)
    c.drawCentredString((12 + 54.5) / 2, _y(192), "PARTIDA")
    c.drawCentredString((54.5 + 122.6) / 2, _y(192), "CÓDIGO")
    c.drawCentredString((122.6 + 184.4) / 2, _y(184), "CANT.")
    c.drawCentredString((122.6 + 184.4) / 2, _y(194), "SOLICITADA")
    c.drawCentredString((184.4 + 231.7) / 2, _y(192), "UNIDAD")
    c.setFont("Helvetica-Bold", 7.5)
    c.drawCentredString((231.7 + 702.2) / 2, _y(192), "D E S C R I P C I Ó N   D E   M A T E R I A L")
    c.setFont("Helvetica-Bold", 7)
    c.drawCentredString((702.2 + 780) / 2, _y(184), "CANTIDAD")
    c.drawCentredString((702.2 + 780) / 2, _y(194), "DESPACHADA")

    # Filas (siempre 10)
    row_tops = [208.3 + i * 17.64 for i in range(10)] + [384.7]
    c.setFont("Helvetica", 8.5)
    for i in range(10):
        y_top = row_tops[i]
        y_bot = row_tops[i + 1]
        c.line(12, _y(y_bot), 780, _y(y_bot))
        cy = _y(y_top + 11)
        c.drawCentredString((12 + 54.5) / 2, cy, str(i + 1))
        if i < len(page_lines):
            line = page_lines[i]
            c.drawCentredString((54.5 + 122.6) / 2, cy, (line.codigo or "")[:12])
            c.drawCentredString((122.6 + 184.4) / 2, cy, (line.cantidad_solicitada or "")[:10])
            c.drawCentredString((184.4 + 231.7) / 2, cy, (line.unidad or "")[:8])
            c.drawString(236, cy, (line.descripcion or "")[:72])
            c.drawCentredString((702.2 + 780) / 2, cy, (line.cantidad_despachada or "")[:10])

    # Pie de datos
    c.line(12, _y(402.3), 780, _y(402.3))
    c.line(12, _y(420.8), 780, _y(420.8))
    c.line(12, _y(454.4), 780, _y(454.4))
    c.line(12, _y(505.8), 780, _y(505.8))
    # verticales pie
    for x in [154, 236, 420.9, 571.6]:
        c.line(x, _y(402.3), x, _y(454.4))
    c.setFont("Helvetica-Bold", 7)
    c.drawString(16, _y(414), "CECO:")
    c.drawString(158, _y(414), "ÁREA:")
    c.drawString(240, _y(414), "USO/EQUIPO:")
    c.drawString(575, _y(414), "FECHA DE EXPEDICIÓN:")
    c.setFont("Helvetica", 8)
    c.drawString(16, _y(436), (data.ceco or "")[:22])
    c.drawString(158, _y(436), (data.area or "")[:12])
    c.drawString(240, _y(436), (data.uso_equipo or "")[:52])
    c.drawString(575, _y(436), data.fecha_expedicion or "")

    # Firmas
    c.setFont("Helvetica-Bold", 7.5)
    c.drawCentredString(133, _y(468), "RECIBIDO POR:")
    c.drawCentredString(391.5, _y(468), "AUTORIZADO POR:")
    c.drawCentredString(647, _y(468), "DESPACHADO POR ALMACÉN:")
    c.setFont("Helvetica", 7)
    c.drawCentredString(133, _y(514), "NOMBRE Y FIRMA")
    c.drawCentredString(391.5, _y(514), "NOMBRE Y FIRMA")
    c.drawCentredString(647, _y(514), "NOMBRE Y FIRMA")
    # líneas de firma
    for x0, x1 in [(30, 236), (290, 493), (545, 749)]:
        c.line(x0, _y(505.8), x1, _y(505.8))


def render_va_pdf(data: VAData) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=landscape(letter))
    pages = _chunks(data.lines, 10)
    for idx, page_lines in enumerate(pages, start=1):
        _draw_page(c, data, page_lines, idx, len(pages))
        c.showPage()
    c.save()
    return buf.getvalue()


# --- XLSX --------------------------------------------------------------------

def render_va_xlsx(data: VAData) -> bytes:
    wb = Workbook()
    wb.remove(wb.active)
    pages = _chunks(data.lines, 10)
    thin = Side(style="thin")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    for idx, page_lines in enumerate(pages, start=1):
        ws = wb.create_sheet(title=f"VA {idx}")
        ws.page_setup.orientation = ws.ORIENTATION_LANDSCAPE
        ws.page_setup.paperSize = ws.PAPERSIZE_LETTER
        ws.page_margins.left = 0.2
        ws.page_margins.right = 0.2
        ws.page_margins.top = 0.4
        ws.page_margins.bottom = 0.4
        ws.print_area = "A1:H24"
        # Anchuras aproximadas
        widths = {"A": 6, "B": 10, "C": 12, "D": 8, "E": 46, "F": 10, "G": 10, "H": 12}
        for col, w in widths.items():
            ws.column_dimensions[col].width = w
        for r in range(1, 25):
            ws.row_dimensions[r].height = 18

        # Logo
        logo = ASSETS_DIR / "logo_va.png"
        if logo.exists():
            img = XLImage(str(logo))
            img.width, img.height = 150, 68
            ws.add_image(img, "A1")

        ws.merge_cells("C1:F1")
        ws["C1"] = "LA GUITARRA COMPAÑÍA MINERA SA DE CV"
        ws["C1"].font = Font(bold=True, size=14)
        ws["C1"].alignment = Alignment(horizontal="center")
        ws.merge_cells("G1:H1")
        ws["G1"] = "F O L I O"
        ws["G1"].font = Font(bold=True, size=11)
        ws["G1"].alignment = Alignment(horizontal="center")
        ws.merge_cells("C2:F2")
        ws["C2"] = "VALE DE SALIDA"
        ws["C2"].font = Font(bold=True, size=16)
        ws["C2"].alignment = Alignment(horizontal="center")
        ws.merge_cells("C3:F3")
        ws["C3"] = "ALMACÉN"
        ws["C3"].font = Font(bold=True, size=13)
        ws["C3"].alignment = Alignment(horizontal="center")
        ws.merge_cells("G2:H2")
        ws["G2"] = data.folio if len(pages) == 1 else f"{data.folio} ({idx}/{len(pages)})"
        ws["G2"].font = Font(bold=True, size=13)
        ws["G2"].alignment = Alignment(horizontal="center")
        ws.merge_cells("C4:D4")
        ws["C4"] = "DEPARTAMENTO:"
        ws["C4"].font = Font(bold=True)
        ws.merge_cells("E4:F4")
        ws["E4"] = data.departamento or ""

        headers = {
            1: "PARTIDA",
            2: "CÓDIGO",
            3: "CANT. SOLICITADA",
            4: "UNIDAD",
            5: "DESCRIPCIÓN DE MATERIAL",
            8: "CANTIDAD DESPACHADA",
        }
        ws.merge_cells("E6:G6")
        for col_idx, val in headers.items():
            cell = ws.cell(row=6, column=col_idx, value=val)
            cell.font = Font(bold=True, size=9)
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

        for i in range(10):
            r = 7 + i
            ws.cell(r, 1, i + 1).alignment = Alignment(horizontal="center")
            if i < len(page_lines):
                line = page_lines[i]
                ws.cell(r, 2, line.codigo)
                ws.cell(r, 3, line.cantidad_solicitada)
                ws.cell(r, 4, line.unidad)
                ws.cell(r, 5, line.descripcion)
                ws.cell(r, 8, line.cantidad_despachada)
            ws.merge_cells(start_row=r, start_column=5, end_row=r, end_column=7)
            for c in range(1, 9):
                ws.cell(r, c).border = border
        for c in range(1, 9):
            ws.cell(6, c).border = border

        ws.merge_cells("A18:B18")
        ws["A18"] = "CECO:"
        ws["A18"].font = Font(bold=True, size=9)
        ws.merge_cells("C18:D18")
        ws["C18"] = "ÁREA:"
        ws["C18"].font = Font(bold=True, size=9)
        ws.merge_cells("E18:G18")
        ws["E18"] = "USO/EQUIPO:"
        ws["E18"].font = Font(bold=True, size=9)
        ws["H18"] = "FECHA DE EXPEDICIÓN:"
        ws["H18"].font = Font(bold=True, size=9)
        ws.merge_cells("A19:B19")
        ws["A19"] = data.ceco or ""
        ws.merge_cells("C19:D19")
        ws["C19"] = data.area or ""
        ws.merge_cells("E19:G19")
        ws["E19"] = data.uso_equipo or ""
        ws["H19"] = data.fecha_expedicion or ""
        for r in (18, 19):
            for c in range(1, 9):
                ws.cell(r, c).border = border

        ws.merge_cells("A21:C21")
        ws["A21"] = "RECIBIDO POR:"
        ws["A21"].font = Font(bold=True, size=9)
        ws.merge_cells("D21:F21")
        ws["D21"] = "AUTORIZADO POR:"
        ws["D21"].font = Font(bold=True, size=9)
        ws.merge_cells("G21:H21")
        ws["G21"] = "DESPACHADO POR ALMACÉN:"
        ws["G21"].font = Font(bold=True, size=9)
        ws.row_dimensions[23].height = 28
        ws.merge_cells("A24:C24")
        ws["A24"] = "NOMBRE Y FIRMA"
        ws.merge_cells("D24:F24")
        ws["D24"] = "NOMBRE Y FIRMA"
        ws.merge_cells("G24:H24")
        ws["G24"] = "NOMBRE Y FIRMA"
        for label in ("A21","D21","G21","A24","D24","G24"):
            ws[label].alignment = Alignment(horizontal="center")
            ws[label].font = Font(bold=True, size=9) if "21" in label else Font(size=9)

    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
