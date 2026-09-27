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
        request = Request(str(url), headers={'User-Agent': 'Biodiversiteit-Verkenner/1.19'})
        with urlopen(request, timeout=12) as response:
            chunks, size = [], 0
            while chunk := response.read(65536):
                size += len(chunk)
                if size > 8 * 1024 * 1024:
                    return None
                chunks.append(chunk)
        with Image.open(BytesIO(b''.join(chunks))) as source:
            picture = ImageOps.exif_transpose(source).convert('RGB')
            picture = ImageOps.fit(picture, (720, 570), method=Image.Resampling.LANCZOS)
            output = BytesIO()
            picture.save(output, format='JPEG', quality=87)
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
                        highlight_unseen=None, photo_loader=None):
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
    margin, gap = 30, 15
    card_width = (page_width - 2 * margin - gap) / 2
    photo_height = card_width * 570 / 720
    body_width = card_width - 22
    name_style = ParagraphStyle('name', fontName='Helvetica-Bold', fontSize=11, leading=13.5)
    scientific_style = ParagraphStyle('scientific', fontName='Helvetica-Oblique', fontSize=9, leading=11)

    def card_height(row):
        name = str(row.get('Engelse naam') or row.get('Wetenschappelijke naam') or 'Unknown species')
        scientific = str(row.get('Wetenschappelijke naam') or '')
        name_h = Paragraph(escape(name), name_style).wrap(body_width, 10000)[1]
        scientific_h = Paragraph(escape(scientific), scientific_style).wrap(body_width, 10000)[1]
        return photo_height + 12 + name_h + 4 + scientific_h + 12 + 20 + (25 if include_personal else 0) + 12

    page_number = 0
    def new_page():
        nonlocal page_number
        if page_number:
            pdf.showPage()
        page_number += 1
        top = page_height - margin
        top -= _paragraph(pdf, 'Biodiversiteit Verkenner', margin, top, page_width - 60,
                          size=17, font='Helvetica-Bold') + 6
        top -= _paragraph(pdf, meta.get('area') or 'Soortenoverzicht', margin, top, page_width - 60,
                          size=11, font='Helvetica-Bold') + 5
        if page_number == 1:
            years = meta.get('years') or ('?', '?')
            month_names = ('januari','februari','maart','april','mei','juni','juli','augustus','september','oktober','november','december')
            months = ', '.join(month_names[int(m)-1] for m in meta.get('months', []) if 1 <= int(m) <= 12)
            group = (meta.get('selected_taxon') or {}).get('label') or meta.get('group_label') or 'Alle soortgroepen'
            details = [f'{years[0]} - {years[1]} | {months or "alle maanden"} | {group}',
                       f'{len(rows)} getoonde soorten | {sort_by} | Minimum: {minimum}']
            if username and include_personal:
                details.append(f'Gebruiker: {username} | Rood: nog nooit gezien | Blauw: alleen hier | Groen: hier en elders')
            if meta.get('truncated'):
                details.append('De veiligheidsgrens is bereikt; zeldzamere soorten kunnen ontbreken.')
            if failed:
                details.append(f'{failed} foto(s) konden niet worden opgehaald.')
            for line in details:
                top -= _paragraph(pdf, line, margin, top, page_width-60, size=8) + 3
        pdf.setFont('Helvetica', 7)
        pdf.setFillColor(HexColor('#52635a'))
        pdf.drawString(margin, 17, f'iNaturalist | {date.today():%d-%m-%Y}')
        pdf.drawRightString(page_width-margin, 17, f'Pagina {page_number}')
        return top - 12

    def pill(text, x, top):
        width = min(body_width, pdf.stringWidth(text, 'Helvetica', 8) + 14)
        pdf.setFillColor(HexColor('#e4f0fa'))
        pdf.roundRect(x, top-19, width, 19, 8, fill=1, stroke=0)
        pdf.setFillColor(HexColor('#25465d'))
        pdf.setFont('Helvetica', 8)
        pdf.drawString(x+7, top-12, text)

    def draw_card(row, x, top, height):
        bottom = top-height
        card_class, border = species_border(row, seen_here, highlight_unseen)
        pdf.setFillColor(HexColor('#f7f9f8'))
        pdf.roundRect(x, bottom, card_width, height, 10, fill=1, stroke=0)
        photo = photos.get(str(row.get('Foto') or ''))
        pdf.saveState()
        path = pdf.beginPath()
        path.roundRect(x, bottom, card_width, height, 10)
        pdf.clipPath(path, stroke=0)
        if photo:
            pdf.drawImage(ImageReader(BytesIO(photo)), x, top-photo_height,
                          width=card_width, height=photo_height)
        else:
            pdf.setFillColor(HexColor('#e4ece5'))
            pdf.rect(x, top-photo_height, card_width, photo_height, fill=1, stroke=0)
            _paragraph(pdf, 'Foto niet beschikbaar', x+12, top-photo_height/2, body_width,
                       size=10, color='#64776b')
        pdf.restoreState()
        cursor = top-photo_height-12
        name = row.get('Engelse naam') or row.get('Wetenschappelijke naam') or 'Unknown species'
        cursor -= _paragraph(pdf, name, x+11, cursor, body_width, size=11, font='Helvetica-Bold') + 4
        cursor -= _paragraph(pdf, row.get('Wetenschappelijke naam') or '', x+11, cursor, body_width,
                             size=9, font='Helvetica-Oblique', color='#657269') + 12
        pill(f"{int(row.get('Waarnemingen in gebied') or 0):,} in gebied", x+11, cursor)
        if include_personal:
            pill(f"Mijn totaal: {int(row.get('Mijn waarnemingen wereldwijd') or 0):,}", x+11, cursor-25)
        pdf.setStrokeColor(HexColor(border))
        pdf.setLineWidth(2.5 if card_class else .7)
        pdf.roundRect(x, bottom, card_width, height, 10, fill=0, stroke=1)
        url = str(row.get('iNaturalist') or '')
        if url.startswith('https://www.inaturalist.org/'):
            pdf.linkURL(url, (x, bottom, x+card_width, top), relative=0, thickness=0)

    top = new_page()
    if not rows:
        _paragraph(pdf, 'Geen soorten voldoen aan de ingestelde filters.', margin, top, page_width-60)
    for offset in range(0, len(rows), 2):
        pair = rows[offset:offset+2]
        height = max(card_height(row) for row in pair)
        if top-height < 35:
            top = new_page()
        for column, row in enumerate(pair):
            draw_card(row, margin+column*(card_width+gap), top, height)
        top -= height+gap
    pdf.save()
    return output.getvalue(), failed
