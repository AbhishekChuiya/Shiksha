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
