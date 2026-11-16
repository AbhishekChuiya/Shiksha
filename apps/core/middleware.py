from django.db.models import Count

SESSION_KEY = "current_plant_id"
VIEW_AS_KEY = "view_as_learner"


class EnglishDefaultLocaleMiddleware:
    """Language comes only from the language chosen in the app (cookie). Nothing chosen yet -> English.

    Django's stock LocaleMiddleware would also read the browser's Accept-Language header, so a phone set to Hindi
    or Gujarati would open the app in that language. We want English first, for everyone.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from django.conf import settings
        from django.utils import translation
        from django.utils.cache import patch_vary_headers
        lang = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)
        if lang not in dict(settings.LANGUAGES):
            lang = settings.LANGUAGE_CODE
        translation.activate(lang)
        request.LANGUAGE_CODE = translation.get_language()
        response = self.get_response(request)
        patch_vary_headers(response, ("Cookie",))
        response.headers.setdefault("Content-Language", translation.get_language())
        return response


class CurrentPlantMiddleware:
    """Attach `request.plant` — the plant selected in the header switcher.

    Falls back to the user's default plant, then their first accessible plant.
    A plant the user may not access is never selected.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.plant = None
        user = getattr(request, "user", None)
        request.view_as_learner = False
        if user is not None and user.is_authenticated and user.real_admin \
                and request.session.get(VIEW_AS_KEY):
            user._view_as_learner = True  # admin is previewing what learners see
            request.view_as_learner = True
        if user is not None and user.is_authenticated:
            allowed = user.accessible_plants()
            plant = None
            pid = request.session.get(SESSION_KEY)
            if pid:
                plant = allowed.filter(pk=pid).first()
            if plant is None and user.default_plant_id:
                plant = allowed.filter(pk=user.default_plant_id).first()
            if plant is None:  # land on the plant that actually has learning content
                plant = allowed.annotate(n=Count("modules")).order_by("-n", "order", "name").first()
            if plant is not None:
                request.session[SESSION_KEY] = plant.pk
            request.plant = plant
        return self.get_response(request)
