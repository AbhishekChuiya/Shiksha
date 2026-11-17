"""Server-side PDF certificate (A4 landscape) — a real downloadable file, not a browser print."""
from io import BytesIO

from django.conf import settings
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from .signature import draw_pdf, signers

GOLD = HexColor("#B8963E")
WINE = HexColor("#8A0C22")
INK = HexColor("#2A1A1A")
SOFT = HexColor("#6B5A50")
PAPER = HexColor("#FFFDF8")


def _fit(text, font, size, max_width, min_size=16):
    while size > min_size and stringWidth(text, font, size) > max_width:
        size -= 1
    return size


def _latin(text):
    """Built-in PDF fonts only cover Latin; replace anything else so no empty boxes appear."""
    text = text.replace("–", "-").replace("—", "-").replace("’", "'").replace("“", '"').replace("”", '"')
    return text.encode("latin-1", "replace").decode("latin-1")


def build_certificate_pdf(cert, verify_url):
    W, H = landscape(A4)
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(W, H))
    c.setTitle(f"Certificate — {cert.module.title}")
    c.setAuthor("Vishakha Group · Project Shiksha")

    c.setFillColor(PAPER)
    c.rect(0, 0, W, H, stroke=0, fill=1)
    c.setStrokeColor(GOLD)
    c.setLineWidth(3.5)
    c.rect(22, 22, W - 44, H - 44, stroke=1, fill=0)
    c.setLineWidth(0.8)
    c.rect(31, 31, W - 62, H - 62, stroke=1, fill=0)

    # watermark mark
    mark = settings.BASE_DIR / "static" / "img" / "brand" / "logo-mark.png"
    logo = settings.BASE_DIR / "static" / "img" / "brand" / "logo.png"
    try:
        c.saveState()
        c.setFillAlpha(0.05)
        c.drawImage(ImageReader(str(mark)), W / 2 - 150, H / 2 - 155, 300, 305, mask="auto")
        c.restoreState()
        c.drawImage(ImageReader(str(logo)), W / 2 - 100, H - 98, 200, 43, mask="auto")
    except Exception:  # a missing logo must never block a certificate
        pass

    c.setFillColor(GOLD)
    c.setFont("Helvetica", 9.5)
    c.drawCentredString(W / 2, H - 118, "P R O J E C T   S H I K S H A   ·   L E A R N I N G   P L A T F O R M")

    c.setFillColor(WINE)
    c.setFont("Times-Bold", 40)
    c.drawCentredString(W / 2, H - 172, "Certificate of Completion")

    c.setFillColor(SOFT)
    c.setFont("Times-Roman", 15)
    c.drawCentredString(W / 2, H - 210, "This is to certify that")

    name = _latin(cert.holder_name)
    size = _fit(name, "Times-BoldItalic", 40, W - 220)
    c.setFillColor(INK)
    c.setFont("Times-BoldItalic", size)
    c.drawCentredString(W / 2, H - 262, name)
    half = min(stringWidth(name, "Times-BoldItalic", size) / 2 + 30, (W - 160) / 2)
    c.setStrokeColor(GOLD)
    c.setLineWidth(1)
    c.line(W / 2 - half, H - 272, W / 2 + half, H - 272)

    c.setFillColor(SOFT)
    c.setFont("Times-Roman", 15)
    c.drawCentredString(W / 2, H - 306, "has successfully completed the learning module")

    title = _latin(cert.module.title)
    tsize = _fit(title, "Helvetica-Bold", 26, W - 200, min_size=14)
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", tsize)
    c.drawCentredString(W / 2, H - 346, title)

    plant = cert.module.plant
    where = f"at {plant.company} ({plant.name})" if plant.company else f"at {plant.name}"
    if cert.score_percent is not None:
        where += f"  ·  assessment score {cert.score_percent}%"
    c.setFillColor(SOFT)
    c.setFont("Times-Roman", 14)
    c.drawCentredString(W / 2, H - 374, _latin(where))

    # footer: date | HR signature | seal | HoD signature | QR
    y = 92
    c.setStrokeColor(GOLD)
    c.setLineWidth(0.8)
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 10.5)
    c.drawString(74, y + 18, cert.issued_at.strftime("%d %B %Y"))
    c.setFillColor(SOFT)
    c.setFont("Helvetica", 8.5)
    c.drawString(74, y + 5, "Date of issue")
    c.setFont("Helvetica", 8)
    c.drawString(74, y - 8, f"Certificate ID: {cert.short_code}")

    ink = HexColor("#1D2A5B")
    centres = (292, 552)
    for cx, sg in zip(centres, signers(cert)):
        c.setStrokeColor(ink)
        c.setLineWidth(1.3)
        draw_pdf(c, sg["name"] or sg["title"], cx - 75, y + 14)
        c.setStrokeColor(GOLD)
        c.setLineWidth(0.8)
        c.line(cx - 90, y + 12, cx + 90, y + 12)
        yy = y - 1
        if sg["name"]:
            c.setFillColor(INK)
            c.setFont("Helvetica-Bold", 10)
            c.drawCentredString(cx, yy, _latin(sg["name"]))
            yy -= 12
        c.setFillColor(SOFT)
        c.setFont("Helvetica", 8.5)
        c.drawCentredString(cx, yy, _latin(sg["title"]))

    # gold seal between the two signatures
    sx, sy = (centres[0] + centres[1]) / 2, y + 22
    c.setFillColor(HexColor("#D9B44F"))
    c.circle(sx, sy, 30, stroke=0, fill=1)
    c.setStrokeColor(HexColor("#FFF3C4"))
    c.setLineWidth(2)
    c.circle(sx, sy, 26, stroke=1, fill=0)
    c.setStrokeColor(WINE)
    c.setLineWidth(0.8)
    c.circle(sx, sy, 23, stroke=1, fill=0)
    c.setStrokeColor(WINE)
    c.setLineWidth(3)
    c.setLineCap(1)
    c.line(sx - 10, sy + 3, sx - 3, sy - 4)
    c.line(sx - 3, sy - 4, sx + 11, sy + 11)
    c.setFillColor(WINE)
    c.setFont("Helvetica-Bold", 4.6)
    c.drawCentredString(sx, sy - 17, "VERIFIED LEARNER")

    widget = qr.QrCodeWidget(verify_url)
    x0, y0, x1, y1 = widget.getBounds()
    box = 62
    d = Drawing(box, box, transform=[box / (x1 - x0), 0, 0, box / (y1 - y0), 0, 0])
    d.add(widget)
    renderPDF.draw(d, c, W - 74 - box, y - 6)
    c.setFillColor(SOFT)
    c.setFont("Helvetica", 7.5)
    c.drawCentredString(W - 74 - box / 2, y - 16, "Scan to verify")

    c.showPage()
    c.save()
    return buf.getvalue()
