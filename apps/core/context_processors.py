from django.conf import settings


def shiksha(request):
    user = getattr(request, "user", None)
    plants = user.accessible_plants() if user and user.is_authenticated else []
    return {
        "current_plant": getattr(request, "plant", None),
        "available_plants": plants,
        "LANGUAGE_CHOICES": settings.LANGUAGES,
        "APP_VERSION": "v0.1.0",
        "SSO_ENABLED": settings.SSO_ENABLED,
        "view_as_learner": getattr(request, "view_as_learner", False),
        "can_toggle_view": bool(user and user.is_authenticated and user.real_admin),
    }
