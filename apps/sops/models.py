from django.conf import settings
from django.db import models
from django.urls import reverse

from apps.core.i18n import localized


class SOPDocument(models.Model):
    """A controlled SOP. Its content lives in versions; only one is active."""

    plant = models.ForeignKey("plants.Plant", on_delete=models.CASCADE, related_name="sops")
    department = models.ForeignKey("plants.Department", on_delete=models.PROTECT,
                                   related_name="sops")
    process = models.ForeignKey("plants.Process", null=True, blank=True,
                                on_delete=models.SET_NULL, related_name="sops")
    code = models.CharField(max_length=40, help_text="Document number, e.g. VMPL/PRD/SOP/01")
    title = models.CharField(max_length=200)
    title_hi = models.CharField("title (Hindi)", max_length=200, blank=True)
    category = models.CharField(max_length=80, blank=True)
    tags = models.CharField(max_length=200, blank=True, help_text="Comma separated")
    owner = models.CharField(max_length=120, blank=True, help_text="Content owner")
    language = models.CharField(max_length=10, default="en",
                                choices=[("en", "English"), ("hi", "Hindi"), ("gu", "Gujarati")])
    allow_download = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["plant", "code"]
        unique_together = [("plant", "code")]
        verbose_name = "SOP"

    def __str__(self):
        return f"{self.code} — {self.title}"

    display_title = property(lambda self: localized(self, "title"))

    def get_absolute_url(self):
        return reverse("sops:detail", args=[self.pk])

    @property
    def active_version(self):
        return (self.versions.filter(status=SOPVersion.Status.APPROVED)
                .order_by("-effective_date", "-id").first())

    @property
    def tag_list(self):
        return [t.strip() for t in self.tags.split(",") if t.strip()]


class SOPVersion(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        APPROVED = "approved", "Approved (active)"
        SUPERSEDED = "superseded", "Superseded"

    sop = models.ForeignKey(SOPDocument, on_delete=models.CASCADE, related_name="versions")
    version = models.CharField(max_length=20, help_text="e.g. 03")
    file = models.FileField(upload_to="sops/%Y/", blank=True)
    content = models.TextField(blank=True, help_text="Extracted/plain text, used for search & AI")
    effective_date = models.DateField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    change_summary = models.TextField(blank=True)
    approved_by = models.CharField(max_length=120, blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-effective_date", "-id"]
        unique_together = [("sop", "version")]

    def __str__(self):
        return f"{self.sop.code} v{self.version} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Approving a version supersedes every other approved version.
        if self.status == self.Status.APPROVED:
            (SOPVersion.objects.filter(sop=self.sop, status=self.Status.APPROVED)
             .exclude(pk=self.pk).update(status=self.Status.SUPERSEDED))


class SOPAccess(models.Model):
    """Records SOP views/downloads for reporting."""

    sop = models.ForeignKey(SOPDocument, on_delete=models.CASCADE, related_name="accesses")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    action = models.CharField(max_length=10, choices=[("view", "View"), ("download", "Download")])
    at = models.DateTimeField(auto_now_add=True)
