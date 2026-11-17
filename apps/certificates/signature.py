"""Signatories and handwritten-style signatures for certificates (HTML and PDF share one generator)."""
import hashlib
import random

from django.conf import settings


def signers(cert):
    """The two people who 'sign' every certificate: head of HR and the head of the module's department."""
    dept = cert.module.department.name if cert.module.department_id else ""
    return [
        {"title": getattr(settings, "CERT_HR_HEAD_TITLE", "Head – Human Resources"), "name": getattr(settings, "CERT_HR_HEAD_NAME", "")},
        {"title": f"Head of Department – {dept}" if dept else "Head of Department", "name": getattr(settings, "CERT_HOD_NAME", "")},
    ]


def _curves(seed, width, height):
    """A repeatable pen-stroke for `seed`: (start, [cubic segments]) in a width x height box, y pointing down."""
    rnd = random.Random(int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12], 16))
    n = rnd.randint(7, 10)
    step = width * 0.8 / n
    x, y = 6.0, height * 0.62
    start, curves = (x, y), []
    for i in range(n):
        amp = height * rnd.uniform(0.28, 0.5) * (1.25 if i == 0 else 1)
        nx, ny = x + step, height * rnd.uniform(0.42, 0.7)
        curves.append((x + step * 0.15, y - amp * rnd.uniform(0.7, 1.3), x + step * 0.6, y + amp * rnd.uniform(-0.3, 0.9), nx, ny))
        x, y = nx, ny
    curves.append((x + 10, y + height * 0.2, width * 0.5, height * 0.92, width * 0.12, height * 0.86))     # underline sweep back to the left
    return start, curves


def svg_path(seed, width=190, height=56):
    (x, y), curves = _curves(seed, width, height)
    return f"M{x:.1f} {y:.1f} " + " ".join("C" + " ".join(f"{v:.1f}" for v in c) for c in curves)


def draw_pdf(c, seed, left, bottom, width=150, height=44):
    """Draw the same stroke on a reportlab canvas; (left, bottom) is the box's lower-left corner."""
    (x, y), curves = _curves(seed, width, height)
    p = c.beginPath()
    p.moveTo(left + x, bottom + height - y)
    for a, b, cc, d, e, f in curves:
        p.curveTo(left + a, bottom + height - b, left + cc, bottom + height - d, left + e, bottom + height - f)
    c.setLineCap(1)
    c.drawPath(p, stroke=1, fill=0)


def qr_svg(url, size=92):
    """An inline SVG QR code for the verification link."""
    from reportlab.graphics import renderSVG
    from reportlab.graphics.barcode import qr
    from reportlab.graphics.shapes import Drawing
    widget = qr.QrCodeWidget(url)
    x0, y0, x1, y1 = widget.getBounds()
    d = Drawing(size, size, transform=[size / (x1 - x0), 0, 0, size / (y1 - y0), 0, 0])
    d.add(widget)
    svg = renderSVG.drawToString(d)
    return svg[svg.index("<svg"):]
