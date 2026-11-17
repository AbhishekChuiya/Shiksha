import os

from django.conf import settings
from django.contrib.staticfiles import finders


def _asset_version():
    """Changes whenever shiksha.css / shiksha.js change, so browsers never keep a stale copy after an update."""
    stamp = 0
    for name in ("css/shiksha.css", "css/theme-v3.css", "js/shiksha.js"):
        path = finders.find(name)
        if path:
            stamp = max(stamp, int(os.stat(path).st_mtime))
    return stamp


def _bell(request, user):
    """Unread count and the latest few notifications for the bell in the top bar."""
    from .models import Notification
    from .notify import maybe_sync, text_for
    maybe_sync(request)
    mine = Notification.objects.filter(user=user)
    recent = [{"n": n, "title": text_for(n)[0], "body": text_for(n)[1]} for n in mine[:6]]
    return {"notif_unread": mine.filter(is_read=False).count(), "notif_recent": recent}


def shiksha(request):
    user = getattr(request, "user", None)
    plants = user.accessible_plants() if user and user.is_authenticated else []
    bell = _bell(request, user) if user and user.is_authenticated else {}
    return {
        **bell,
        "current_plant": getattr(request, "plant", None),
        "available_plants": plants,
        "LANGUAGE_CHOICES": settings.LANGUAGES,
        "APP_VERSION": "v0.1.0",
        "ASSET_V": _asset_version(),
        "SSO_ENABLED": settings.SSO_ENABLED,
        "view_as_learner": getattr(request, "view_as_learner", False),
        "can_toggle_view": bool(user and user.is_authenticated and user.real_admin),
    }
