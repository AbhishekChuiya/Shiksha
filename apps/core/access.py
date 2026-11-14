from django.core.exceptions import PermissionDenied


def require_plant(request):
    """Return the current plant or 404 if the user has no plant access at all."""
    if request.plant is None:
        raise PermissionDenied("No plant assigned to your account.")
    return request.plant


def check_plant_access(user, plant):
    if not user.accessible_plants().filter(pk=plant.pk).exists():
        raise PermissionDenied("You do not have access to this plant.")
