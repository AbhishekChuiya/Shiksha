import os

from django.conf import settings
from django.contrib.staticfiles import finders


def _asset_version():
    """Changes whenever shiksha.css / shiksha.js change, so browsers never keep a stale copy after an update."""
    stamp = 0
    for name in ("css/shiksha.css", "js/shiksha.js"):
        path = finders.find(name)
        if path:
            stamp = max(stamp, int(os.stat(path).st_mtime))
    return stamp


def shiksha(request):
    user = getattr(request, "user", None)
    plants = user.accessible_plants() if user and user.is_authenticated else []
    return {
        "current_plant": getattr(request, "plant", None),
        "available_plants": plants,
        "LANGUAGE_CHOICES": settings.LANGUAGES,
        "APP_VERSION": "v0.1.0",
        "ASSET_V": _asset_version(),
        "SSO_ENABLED": settings.SSO_ENABLED,
        "view_as_learner": getattr(request, "view_as_learner", False),
        "can_toggle_view": bool(user and user.is_authenticated and user.real_admin),
    }
