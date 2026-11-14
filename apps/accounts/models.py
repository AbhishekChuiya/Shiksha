from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.update(is_staff=True, is_superuser=True, role=User.Role.ADMIN)
        return self._create_user(email, password, **extra)


class User(AbstractUser):
    """Shiksha user. Logs in with company email (or employee ID)."""

    class Role(models.TextChoices):
        LEARNER = "learner", _("Learner")
        ADMIN = "admin", _("Admin")

    username = None
    email = models.EmailField(_("company email"), unique=True)
    employee_id = models.CharField(max_length=32, unique=True, null=True, blank=True)
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.LEARNER)
    designation = models.CharField(max_length=120, blank=True,
                                   help_text="e.g. Production Operator")
    plants = models.ManyToManyField("plants.Plant", blank=True, related_name="users",
                                    help_text="Plants this user may access. Admins see all.")
    department = models.ForeignKey("plants.Department", null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="users")
    default_plant = models.ForeignKey("plants.Plant", null=True, blank=True,
                                      on_delete=models.SET_NULL, related_name="+")
    preferred_language = models.CharField(max_length=10, default="en")
    photo = models.ImageField(upload_to="avatars/", blank=True, help_text="Profile photo (square, auto-resized)")

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.get_full_name() or self.email

    def save(self, *args, **kwargs):
        # Django's "Advanced admin" is for superusers made with `createsuperuser` only.
        # A Shiksha "Admin" role never grants it, however the account was created.
        if not self.is_superuser:
            self.is_staff = False
        super().save(*args, **kwargs)

    @property
    def real_admin(self):
        return self.is_superuser or self.role == self.Role.ADMIN

    @property
    def is_shiksha_admin(self):
        """True for admins — except while they are previewing the learner view."""
        return self.real_admin and not getattr(self, "_view_as_learner", False)

    @property
    def photo_url(self):
        return self.photo.url if self.photo else ""

    @property
    def initial(self):
        return (self.first_name or self.email)[:1].upper()

    def accessible_plants(self):
        """Every signed-in user can open every active plant, unless an admin has
        explicitly restricted them to specific plants (Users → Plants in /admin/)."""
        from apps.plants.models import Plant
        qs = Plant.objects.filter(is_active=True)
        if self.is_shiksha_admin or not self.plants.exists():
            return qs
        return qs.filter(pk__in=self.plants.values("pk"))


class ApprovalScope(models.Model):
    """Manager/HOD approval permission scoped to a plant (and optionally a department).

    Per the plan, approvers are not a third role — they are users with scoped
    permissions (used in Phase 3 for feedback & SOP-change approvals).
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="approval_scopes")
    plant = models.ForeignKey("plants.Plant", on_delete=models.CASCADE)
    department = models.ForeignKey("plants.Department", null=True, blank=True,
                                   on_delete=models.CASCADE)

    class Meta:
        unique_together = [("user", "plant", "department")]

    def __str__(self):
        return f"{self.user} → {self.plant}{' / ' + str(self.department) if self.department else ''}"
