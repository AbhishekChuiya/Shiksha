"""Branded HTML + plain-text e-mails (verification, password reset)."""
import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

log = logging.getLogger(__name__)


def send_branded(subject, to, text_template, html_template, context):
    ctx = dict(context, subject=subject, logo_url=getattr(settings, "EMAIL_LOGO_URL", ""))
    msg = EmailMultiAlternatives(subject, render_to_string(text_template, ctx), None, [to])
    msg.attach_alternative(render_to_string(html_template, ctx), "text/html")
    msg.send(fail_silently=False)
