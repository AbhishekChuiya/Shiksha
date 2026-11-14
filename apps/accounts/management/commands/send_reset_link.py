"""Test the 'Forgot password' email for one address and say exactly what happens.

    python manage.py send_reset_link someone@vishakha.com
"""
import traceback

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.accounts.forms import AnyPasswordResetForm
from apps.accounts.models import User


class Command(BaseCommand):
    help = "Send a password-reset email to an address and report the result."

    def add_arguments(self, parser):
        parser.add_argument("email")
        parser.add_argument("--domain", default="127.0.0.1:8000", help="host shown in the link")

    def handle(self, email, domain, **opts):
        self.stdout.write(f"Email backend : {settings.EMAIL_BACKEND}")
        if "smtp" in settings.EMAIL_BACKEND:
            self.stdout.write(f"SMTP server   : {settings.EMAIL_HOST}:{settings.EMAIL_PORT}  (login {settings.EMAIL_HOST_USER or 'none'})")
        self.stdout.write(f"From address  : {settings.DEFAULT_FROM_EMAIL}")
        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            self.stdout.write(self.style.ERROR(f"No account exists with the email {email}. The website shows the same 'check your email' page either way, but sends nothing."))
            return
        if not user.is_active:
            self.stdout.write(self.style.ERROR(f"The account {email} exists but is INACTIVE (not verified or deactivated) — no email is sent for inactive accounts."))
            return
        self.stdout.write(f"Account found : {user.get_full_name() or user.email} ({'has a password' if user.has_usable_password() else 'no password yet'})")
        form = AnyPasswordResetForm({"email": email})
        form.is_valid()
        try:
            form.save(domain_override=domain, use_https=False, email_template_name="accounts/emails/password_reset.txt",
                      html_email_template_name="accounts/emails/password_reset.html", subject_template_name="accounts/emails/password_reset_subject.txt")
        except Exception:
            self.stdout.write(self.style.ERROR("SENDING FAILED:"))
            self.stdout.write(traceback.format_exc())
            return
        self.stdout.write(self.style.SUCCESS(f"Sent. Check the inbox (and Spam) of {email}."))
        if "console" in settings.EMAIL_BACKEND:
            self.stdout.write("(Console backend: the email was printed above instead of being sent — set EMAIL_HOST in .env.)")
