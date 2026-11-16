from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q


class EmailOrEmployeeIdBackend(ModelBackend):
    """Authenticate with company email or employee ID."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        username = username or kwargs.get("email")
        if not username or not password:
            return None
        User = get_user_model()
        user = User.objects.filter(
            Q(email__iexact=username.strip()) | Q(employee_id__iexact=username.strip())
        ).first()
        if user is None:
            User().set_password(password)  # equalise timing
            return None
        if not user.is_superuser and not self._domain_ok(user.email):   # superusers are made on the server with createsuperuser
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

    @staticmethod
    def _domain_ok(email):
        allowed = settings.ALLOWED_EMAIL_DOMAINS
        return not allowed or email.rsplit("@", 1)[-1].lower() in allowed
