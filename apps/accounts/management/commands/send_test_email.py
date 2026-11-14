"""Check your email settings:  python manage.py send_test_email you@vishakha.com"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.emailing import send_branded


class Command(BaseCommand):
    help = "Send a test e-mail using the configured EMAIL_* settings."

    def add_arguments(self, parser):
        parser.add_argument("to")

    def handle(self, to, **opts):
        self.stdout.write(f"Backend : {settings.EMAIL_BACKEND}")
        if "smtp" in settings.EMAIL_BACKEND:
            self.stdout.write(f"Server  : {settings.EMAIL_HOST}:{settings.EMAIL_PORT}  TLS={settings.EMAIL_USE_TLS}")
            self.stdout.write(f"Login   : {settings.EMAIL_HOST_USER}")
        else:
            self.stdout.write("(No EMAIL_HOST set — the email will be printed below instead of sent.)")
        try:
            send_branded("Project Shiksha — test email", to, "accounts/emails/verify.txt",
                         "accounts/emails/verify.html",
                         {"user": type("U", (), {"first_name": "there", "email": to})(),
                          "link": "https://example.com/this-is-a-test"})
        except Exception as exc:
            raise CommandError(f"Sending failed: {exc}")
        self.stdout.write(self.style.SUCCESS(f"Done. Check the inbox of {to}."))
