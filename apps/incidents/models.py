from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Incident(models.Model):
    class Category(models.TextChoices):
        SAFETY = "safety", _("Safety / near miss")
        QUALITY = "quality", _("Quality")
        EQUIPMENT = "equipment", _("Equipment / breakdown")
        ENVIRONMENT = "environment", _("Environment / spillage")
        PROCESS = "process", _("Process deviation")
        OTHER = "other", _("Other")

    class Status(models.TextChoices):
        OPEN = "open", _("Open")
        REVIEW = "review", _("Under review")
        ACTION = "action", _("Action in progress")
        CLOSED = "closed", _("Closed")

    plant = models.ForeignKey("plants.Plant", on_delete=models.PROTECT, related_name="incidents")
    department = models.ForeignKey("plants.Department", null=True, blank=True,
                                   on_delete=models.SET_NULL)
    process = models.ForeignKey("plants.Process", null=True, blank=True,
                                on_delete=models.SET_NULL)
    module = models.ForeignKey("learning.Module", null=True, blank=True,
                               on_delete=models.SET_NULL,
                               help_text="Set when reported from a module page")
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.SAFETY)
    title = models.CharField(_("title"), max_length=200)
    description = models.TextField(_("description"))
    occurred_at = models.DateTimeField(_("date & time"), default=timezone.now)
    attachment = models.FileField(_("photo / document"), upload_to="incidents/%Y/%m/",
                                  blank=True)
    reported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                    related_name="incidents")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    closure_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"#{self.pk} {self.title}"

    def get_absolute_url(self):
        return reverse("incidents:detail", args=[self.pk])
