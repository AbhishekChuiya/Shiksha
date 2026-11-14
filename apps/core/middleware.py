from django.db.models import Count

SESSION_KEY = "current_plant_id"
VIEW_AS_KEY = "view_as_learner"


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
