import re

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from .models import Certificate
from .pdf import build_certificate_pdf


def _own_or_admin(request, code):
    qs = Certificate.objects.select_related("user", "module__plant")
    if not request.user.is_shiksha_admin:
        qs = qs.filter(user=request.user)
    return get_object_or_404(qs, code=code)


@login_required
def certificate_list(request):
    certs = request.user.certificates.select_related("module__plant")
    return render(request, "certificates/list.html", {"certificates": certs})


@login_required
def certificate_detail(request, code):
    cert = _own_or_admin(request, code)
    verify_url = request.build_absolute_uri(reverse("certificates:verify", args=[cert.code]))
    return render(request, "certificates/detail.html", {"cert": cert, "verify_url": verify_url})


@login_required
def certificate_download(request, code):
    cert = _own_or_admin(request, code)
    verify_url = request.build_absolute_uri(reverse("certificates:verify", args=[cert.code]))
    pdf = build_certificate_pdf(cert, verify_url)
    slug = re.sub(r"[^A-Za-z0-9]+", "_", f"{cert.holder_name}_{cert.module.title}").strip("_")
    resp = HttpResponse(pdf, content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="Shiksha_Certificate_{slug}.pdf"'
    return resp


def certificate_verify(request, code):
    """Public page (no login) — what the QR code on the PDF opens."""
    cert = Certificate.objects.select_related("user", "module__plant").filter(code=code).first()
    return render(request, "certificates/verify.html", {"cert": cert}, status=200 if cert else 404)
