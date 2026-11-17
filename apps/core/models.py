from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    """Append-only audit trail for status changes, approvals and admin actions."""

    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=60)
    object_type = models.CharField(max_length=60)
    object_id = models.CharField(max_length=40)
    detail = models.JSONField(default=dict, blank=True)
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-at"]

    def __str__(self):
        return f"{self.at:%Y-%m-%d %H:%M} {self.actor} {self.action} {self.object_type}#{self.object_id}"

    @classmethod
    def record(cls, actor, action, obj, **detail):
        return cls.objects.create(actor=actor, action=action,
                                  object_type=obj._meta.label if obj is not None else "", object_id=str(obj.pk) if obj is not None else "",
                                  detail=detail)


class Notification(models.Model):
    """One message in a user's notification bell. `kind` + `data` are turned into text when shown, so it follows the reader's language;
    announcements written by an admin keep their own title/body."""

    class Kind(models.TextChoices):
        ASSIGNED = "assigned", "Required item assigned"
        DUE_SOON = "due_soon", "Due soon"
        OVERDUE = "overdue", "Overdue"
        CERTIFICATE = "certificate", "Certificate issued"
        ANNOUNCEMENT = "announcement", "Announcement"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    kind = models.CharField(max_length=20, choices=Kind.choices)
    data = models.JSONField(default=dict, blank=True)          # e.g. {"what": "module", "name": "Ageing", "due": "2026-11-20"}
    title = models.CharField(max_length=160, blank=True)       # announcements only
    body = models.TextField(blank=True)
    url = models.CharField(max_length=300, blank=True)
    key = models.CharField(max_length=120, blank=True, db_index=True)   # stops the same alert being created twice
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["user", "is_read"])]

    def __str__(self):
        return f"{self.user} · {self.kind}"
