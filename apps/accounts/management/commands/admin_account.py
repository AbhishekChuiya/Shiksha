"""See, create or repair a superuser (the account that may open the Django admin at /admin/).

    python manage.py admin_account                                   # list superusers and how to sign in
    python manage.py admin_account --email me@vishakha.com --password "Strong#Pass1" [--employee-id abhi]
"""
from django.core.management.base import BaseCommand

from apps.accounts.models import User


class Command(BaseCommand):
    help = "List superusers, or create / repair one."

    def add_arguments(self, parser):
        parser.add_argument("--email")
        parser.add_argument("--password")
        parser.add_argument("--employee-id", dest="employee_id")

    def handle(self, *args, **o):
        if o["email"]:
            if not o["password"]:
                self.stderr.write("Give --password too."); return
            user = User.objects.filter(email__iexact=o["email"]).first() or User(email=o["email"].lower())
            user.is_superuser = user.is_staff = user.is_active = True
            user.role = User.Role.ADMIN
            if o["employee_id"]:
                user.employee_id = o["employee_id"]
            user.set_password(o["password"])
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Superuser ready: sign in with email {user.email}" + (f" or Employee ID {user.employee_id}" if user.employee_id else "") + "."))
            return
        rows = User.objects.filter(is_superuser=True)
        if not rows:
            self.stdout.write("No superuser yet. Create one with:  python manage.py admin_account --email you@vishakha.com --password ...")
        for u in rows:
            self.stdout.write(f"  email: {u.email:<36} employee ID: {u.employee_id or '-':<12} active: {u.is_active}  staff: {u.is_staff}")
        self.stdout.write("Sign in at /admin/ with the EMAIL (or Employee ID) shown above plus your password.")
