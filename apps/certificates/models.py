import uuid

from django.conf import settings
from django.db import models
from django.urls import reverse


class Certificate(models.Model):
    code = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="certificates")
    module = models.ForeignKey("learning.Module", on_delete=models.CASCADE,
                               related_name="certificates")
    attempt = models.ForeignKey("quizzes.Attempt", null=True, blank=True,
                                on_delete=models.SET_NULL)
    score_percent = models.PositiveSmallIntegerField(null=True, blank=True)
    issued_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-issued_at"]
        unique_together = [("user", "module")]

    def __str__(self):
        return f"{self.user} — {self.module.title}"

    def get_absolute_url(self):
        return reverse("certificates:detail", args=[self.code])

    @property
    def holder_name(self):
        """Name printed on the certificate: full name from the profile, else the mailbox name."""
        name = self.user.get_full_name().strip()
        if name:
            return name
        return self.user.email.split("@")[0].replace(".", " ").replace("_", " ").title()

    @property
    def short_code(self):
        return str(self.code).split("-")[0].upper()
