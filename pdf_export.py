"""Photo-card PDF using the displayed species order and border rules."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from html import escape
from io import BytesIO

from urllib.request import Request, urlopen
from urllib.error import URLError
from PIL import Image, ImageOps
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph


def species_border(row, seen_here=None, highlight_unseen=False):
    """Shared by the screen cards and PDF so their colours cannot diverge."""
    personal = int(row.get('Mijn waarnemingen wereldwijd') or 0)
    area_count = (seen_here or {}).get(int(row['species_id']), 0)
    if area_count and area_count == personal:
        return 'only-here', '#1976d2'
    if area_count:
        return 'seen-here', '#228b45'
    if highlight_unseen and personal == 0:
        return 'unseen', '#e53935'
    return '', '#bfc8cd'


def _photo(url):
    if not url or not str(url).startswith(('https://', 'http://')):
        return None
    try:
        request = Request(str(url), headers={'User-Agent': 'Biodiversiteit-Verkenner/1.20'})
        with urlopen(request, timeout=12) as response:
            chunks, size = [], 0
            while chunk := response.read(65536):
                size += len(chunk)
                if size > 8 * 1024 * 1024:
                    return None
                chunks.append(chunk)
        with Image.open(BytesIO(b''.join(chunks))) as source:
            picture = ImageOps.exif_transpose(source).convert('RGB')
            # A card is only about 130 pt wide. Keep enough pixels for print,
            # but avoid embedding full-size images in a many-page PDF.
            picture = ImageOps.fit(picture, (300, 300), method=Image.Resampling.LANCZOS)
            output = BytesIO()
            picture.save(output, format='JPEG', quality=60, optimize=True)
            return output.getvalue()
    except (URLError, OSError, ValueError, Image.DecompressionBombError):
        return None


def _paragraph(pdf, text, x, top, width, *, size=9, font='Helvetica', color='#26372d'):
    style = ParagraphStyle('text', fontName=font, fontSize=size,
                           leading=size * 1.22, textColor=HexColor(color))
    paragraph = Paragraph(escape(str(text)), style)
    _, height = paragraph.wrap(width, 10000)
    paragraph.drawOn(pdf, x, top - height)
    return height


def create_overview_pdf(frame, meta, *, sort_by, minimum, username='',
                        personal_ready=False, seen_here=None, include_personal=None,
                        highlight_unseen=None, photo_loader=None, summary=None):
    """Return (PDF bytes, failed-photo count) for exactly the supplied cards."""
    include_personal = personal_ready if include_personal is None else include_personal
    highlight_unseen = personal_ready if highlight_unseen is None else highlight_unseen
    rows = frame.to_dict('records')
    urls = list(dict.fromkeys(str(row.get('Foto') or '') for row in rows))
    loader = photo_loader or _photo
    with ThreadPoolExecutor(max_workers=6) as pool:
        photos = dict(zip(urls, pool.map(loader, urls)))
    failed = sum(bool(row.get('Foto')) and photos.get(str(row['Foto'])) is None for row in rows)
    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=A4)
    pdf.setTitle(f"Biodiversiteit Verkenner - {meta.get('area', 'Gebied')}")
    pdf.setAuthor('Biodiversiteit Verkenner')
    page_width, page_height = A4
    margin, gap = 24, 8
    card_width = (page_width - 2 * margin - 3 * gap) / 4
    body_width = card_width - 12
    summary = summary or {
        'species': len(rows),
        'observations': sum(int(row.get('Waarnemingen in gebied') or 0) for row in rows),
        'unseen': sum(int(row.get('Mijn waarnemingen wereldwijd') or 0) == 0 for row in rows),
    }

    page_number = 0
    def new_page():
        nonlocal page_number
        if page_number:
            pdf.showPage()
        page_number += 1
        top = page_height - margin
        top -= _paragraph(pdf, 'Biodiversiteit Verkenner', margin, top, page_width - 60,
                          size=15, font='Helvetica-Bold') + 4
        top -= _paragraph(pdf, meta.get('area') or 'Soortenoverzicht', margin, top, page_width - 60,
                          size=10, font='Helvetica-Bold') + 5
        if page_number == 1:
            years = meta.get('years') or ('?', '?')
            month_names = ('januari','februari','maart','april','mei','juni','juli','augustus','september','oktober','november','december')
            months = ', '.join(month_names[int(m)-1] for m in meta.get('months', []) if 1 <= int(m) <= 12)
            group = (meta.get('selected_taxon') or {}).get('label') or meta.get('group_label') or 'Alle soortgroepen'
            top -= _paragraph(pdf, 'Samenvatting', margin, top, page_width-48,
                              size=9, font='Helvetica-Bold') + 3
            metrics = f"Soorten in gebied: {summary['species']:,} | Waarnemingen: {summary['observations']:,}"
            if include_personal:
                metrics += f" | Nog nooit gezien: {summary['unseen']:,}"
            details = [metrics,
                       f"Periode: {years[0]} - {years[1]} | Maanden: {months or 'alle maanden'}",
                       f"Soortgroep: {group} | Kwaliteit: {meta.get('quality_label') or '-'}",
                       f"Sortering: {sort_by} | Minimum: {minimum} | Fotokaarten in deze PDF: {len(rows)}"]
            if username and include_personal:
                details.append(f'Gebruiker: {username} | Rood: nog nooit gezien | Blauw: alleen hier | Groen: hier en elders')
            if meta.get('truncated'):
                details.append('De veiligheidsgrens is bereikt; zeldzamere soorten kunnen ontbreken.')
            if failed:
                details.append(f'{failed} foto(s) konden niet worden opgehaald.')
            for line in details:
                top -= _paragraph(pdf, line, margin, top, page_width-48, size=7) + 2
        pdf.setFont('Helvetica', 7)
        pdf.setFillColor(HexColor('#52635a'))
        pdf.drawString(margin, 17, f'iNaturalist | {date.today():%d-%m-%Y}')
        pdf.drawRightString(page_width-margin, 17, f'Pagina {page_number}')
        return top - 12

    def fitted_text(text, x, top, max_height, *, size=8, font='Helvetica', color='#26372d'):
        # Keep long names inside their reserved space, without truncation.
        style = ParagraphStyle('card', fontName=font, fontSize=size, leading=size*1.15,
                               textColor=HexColor(color))
        paragraph = Paragraph(escape(str(text)), style)
        _, height = paragraph.wrap(body_width, 10000)
        while height > max_height and size > 4:
            size -= .25
            style.fontSize = size
            style.leading = size*1.15
            paragraph = Paragraph(escape(str(text)), style)
            _, height = paragraph.wrap(body_width, 10000)
        paragraph.drawOn(pdf, x, top-height)

    def draw_card(row, x, top, height):
        bottom = top-height
        photo_height = height - 67
        card_class, border = species_border(row, seen_here, highlight_unseen)
        pdf.setFillColor(HexColor('#f7f9f8'))
        pdf.roundRect(x, bottom, card_width, height, 6, fill=1, stroke=0)
        photo = photos.get(str(row.get('Foto') or ''))
        pdf.saveState()
        path = pdf.beginPath()
        path.roundRect(x, bottom, card_width, height, 6)
        pdf.clipPath(path, stroke=0)
        if photo:
            # Pass the JPEG bytes directly: ReportLab embeds the compressed
            # stream instead of inflating a Pillow bitmap into the PDF.
            photo_clip = pdf.beginPath()
            photo_clip.rect(x, top-photo_height, card_width, photo_height)
            pdf.clipPath(photo_clip, stroke=0)
            pdf.drawImage(ImageReader(BytesIO(photo)), x,
                          top-photo_height-(card_width-photo_height)/2,
                          width=card_width, height=card_width)
        else:
            pdf.setFillColor(HexColor('#e4ece5'))
            pdf.rect(x, top-photo_height, card_width, photo_height, fill=1, stroke=0)
            _paragraph(pdf, 'Foto niet beschikbaar', x+6, top-photo_height/2, body_width,
                       size=7, color='#64776b')
        pdf.restoreState()
        cursor = top-photo_height-5
        name = row.get('Engelse naam') or row.get('Wetenschappelijke naam') or 'Unknown species'
        fitted_text(name, x+6, cursor, 19, size=8, font='Helvetica-Bold')
        fitted_text(row.get('Wetenschappelijke naam') or '', x+6, cursor-21, 16,
                     size=7, font='Helvetica-Oblique', color='#657269')
        pdf.setFillColor(HexColor('#e4f0fa'))
        pdf.roundRect(x+5, bottom+5, card_width-10, 20, 4, fill=1, stroke=0)
        fitted_text(f"{int(row.get('Waarnemingen in gebied') or 0):,} in gebied",
                     x+7, bottom+23, 8, size=6.5, color='#25465d')
        if include_personal:
            fitted_text(f"Mijn totaal: {int(row.get('Mijn waarnemingen wereldwijd') or 0):,}",
                         x+7, bottom+14, 8, size=6.5, color='#25465d')
        pdf.setStrokeColor(HexColor(border))
        pdf.setLineWidth(1.7 if card_class else .5)
        pdf.roundRect(x, bottom, card_width, height, 6, fill=0, stroke=1)
        url = str(row.get('iNaturalist') or '')
        if url.startswith('https://www.inaturalist.org/'):
            pdf.linkURL(url, (x, bottom, x+card_width, top), relative=0, thickness=0)

    for offset in range(0, max(1, len(rows)), 16):
        top = new_page()
        height = (top - 34 - 3*gap) / 4
        if not rows:
            _paragraph(pdf, 'Geen soorten voldoen aan de ingestelde filters.', margin, top, page_width-48)
        for index, row in enumerate(rows[offset:offset+16]):
            grid_row, column = divmod(index, 4)
            draw_card(row, margin+column*(card_width+gap), top-grid_row*(height+gap), height)
    pdf.save()
    return output.getvalue(), failed
