"""Create (or reset) test accounts. Safe to run any time; never touches content.

    python manage.py create_test_users

Sign in with the email OR the short name (employee ID), e.g. `test_user`.
Password for all: Test@12345.  Local/testing only — remove these on the live server.
"""
from django.core.management.base import BaseCommand

from apps.accounts.models import ApprovalScope, User
from apps.plants.models import Plant

PASSWORD = "Test@12345"
ACCOUNTS = [
    # short name / employee ID, email, first, last, role, designation
    ("test_user", "test_user@vishakha.com", "Test", "User", User.Role.LEARNER, "Production Operator"),
    ("test_user2", "test_user2@vishakha.com", "Test", "Learner Two", User.Role.LEARNER, "QC Inspector"),
    ("test_manager", "test_manager@vishakha.com", "Test", "Manager", User.Role.LEARNER, "Production HOD"),
    ("test_admin", "test_admin@vishakha.com", "Test", "Admin", User.Role.ADMIN, "Shiksha Administrator"),
]


class Command(BaseCommand):
    help = "Create/reset test_user, test_user2, test_manager and test_admin."

    def handle(self, *args, **opts):
        home = Plant.objects.filter(code="vmpl-p1").first()
        for eid, email, first, last, role, desig in ACCOUNTS:
            user = User.objects.filter(email__iexact=email).first() or User(email=email)
            user.employee_id, user.first_name, user.last_name = eid, first, last
            user.role, user.designation, user.is_active = role, desig, True
            user.is_staff = user.is_superuser = False  # Shiksha admins never get the Django admin
            user.set_password(PASSWORD)
            if home:
                user.default_plant = home
            user.save()
            if eid == "test_manager":  # approval scope for the Phase-3 HOD workflow
                for plant in Plant.objects.all():
                    ApprovalScope.objects.get_or_create(user=user, plant=plant, department=None)
            self.stdout.write(f"  {eid:<13} {email:<28} {role}")
        self.stdout.write(self.style.SUCCESS(f"Done. Password for all: {PASSWORD}"))
