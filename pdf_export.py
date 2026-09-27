"""Printable, complete species overview for the active exploration."""

from datetime import date
from html import escape
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


FONT_DIR = Path(__file__).resolve().parent / "fonts"


def _fonts():
    if "Explorer" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("Explorer", str(FONT_DIR / "DejaVuSans.ttf")))
        pdfmetrics.registerFont(TTFont("Explorer-Bold", str(FONT_DIR / "DejaVuSans-Bold.ttf")))


def _value(value):
    """Make API-sourced labels safe for ReportLab's paragraph markup."""
    if value is None:
        return "—"
    try:
        if value != value:  # pandas NaN
            return "—"
    except (TypeError, ValueError):
        pass
    return escape(str(value)) or "—"


def create_overview_pdf(frame, meta, *, sort_by, minimum, username="", personal_ready=False):
    """Return PDF bytes with every filtered species, in the supplied order."""
    _fonts()
    output = BytesIO()
    document = SimpleDocTemplate(
        output, pagesize=landscape(A4), leftMargin=36, rightMargin=36,
        topMargin=37, bottomMargin=43,
        title=f"Biodiversiteit Verkenner - {meta.get('area', 'Gebied')}",
        author="Biodiversiteit Verkenner",
    )
    normal = ParagraphStyle("normal", fontName="Explorer", fontSize=8, leading=12)
    heading = ParagraphStyle("heading", parent=normal, fontName="Explorer-Bold", fontSize=16, leading=21)
    subheading = ParagraphStyle("subheading", parent=normal, fontName="Explorer-Bold", fontSize=10, leading=14)
    small = ParagraphStyle("small", parent=normal, fontSize=7, leading=10)
    table_text = ParagraphStyle("table", parent=normal, fontSize=7, leading=10)
    table_right = ParagraphStyle("table-right", parent=table_text, alignment=TA_RIGHT)
    p = lambda value, style=normal: Paragraph(_value(value), style)

    years = meta.get("years") or ("?", "?")
    months = meta.get("months") or []
    month_names = [
        "januari", "februari", "maart", "april", "mei", "juni",
        "juli", "augustus", "september", "oktober", "november", "december",
    ]
    month_label = ", ".join(month_names[int(m) - 1] for m in months if 1 <= int(m) <= 12) or "alle maanden"
    taxon = meta.get("selected_taxon")
    group = taxon.get("label") if taxon else meta.get("group_label") or "Alle soortgroepen"
    count = int(frame["Waarnemingen in gebied"].sum())
    personal = bool(username and personal_ready)
    details = [
        f"Gebied: {meta.get('area') or '—'}  |  Soortgroep: {group}",
        f"Periode: {years[0]}–{years[1]}  |  Maanden: {month_label}",
        f"Kwaliteit: {meta.get('quality_label') or '—'}  |  Minimum per soort: {minimum}",
        f"Sortering: {sort_by}  |  Soorten: {len(frame):,}  |  Waarnemingen: {count:,}",
    ]
    if personal:
        unseen = int((frame["Mijn waarnemingen wereldwijd"] == 0).sum())
        details.append(f"iNaturalist-gebruiker: {username}  |  Nog nooit gezien: {unseen:,}")
    story = [p("Biodiversiteit Verkenner", heading), Spacer(1, 4),
             p("Soortenoverzicht", subheading), Spacer(1, 8)]
    story.extend([p(line) for line in details])
    story += [Spacer(1, 8)]
    if meta.get("truncated"):
        story += [p("Let op: de veiligheidsgrens voor een zeer soortenrijk gebied is bereikt; zeldzamere soorten kunnen ontbreken.", small), Spacer(1, 5)]
    story += [p("Aantallen zijn gebaseerd op historische waarnemingen binnen de kleinste rechthoek om het gekozen gebied. Ze garanderen niet dat een soort er nu aanwezig is.", small), Spacer(1, 12)]

    headers = ["Engelse naam", "Wetenschappelijke naam", "Waarnemingen in gebied"]
    widths = [173, 173, 115]
    if personal:
        headers.append("Mijn waarnemingen wereldwijd")
        widths.append(120)
    headers += ["Familie", "Orde"]
    available = landscape(A4)[0] - document.leftMargin - document.rightMargin
    remaining = available - sum(widths)
    widths += [remaining * .52, remaining * .48]
    data = [[p(label, table_text) for label in headers]]
    for _, row in frame.iterrows():
        cells = [p(row.get("Engelse naam"), table_text),
                 p(row.get("Wetenschappelijke naam"), table_text),
                 p(f"{int(row['Waarnemingen in gebied']):,}", table_right)]
        if personal:
            cells.append(p(f"{int(row['Mijn waarnemingen wereldwijd']):,}", table_right))
        cells += [p(row.get("Familie"), table_text), p(row.get("Orde"), table_text)]
        data.append(cells)
    if len(data) == 1:
        story.append(p("Geen soorten voldoen aan de ingestelde filters."))
    else:
        table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e7f2eb")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f6f8f7")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LINEBELOW", (0, 0), (-1, 0), .6, colors.HexColor("#59876a")),
        ]))
        story.append(table)

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Explorer", 7)
        canvas.setFillColor(colors.HexColor("#52635a"))
        canvas.drawString(36, 23, f"Biodiversiteit Verkenner  |  {date.today():%d-%m-%Y}")
        canvas.drawRightString(landscape(A4)[0] - 36, 23, f"Pagina {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
