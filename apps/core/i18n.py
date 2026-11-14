from django.utils.translation import get_language


def localized(obj, field):
    """Return `<field>_hi` when the UI is Hindi and it is filled in, else the English value."""
    if (get_language() or "en").lower() == "hi":
        hi = getattr(obj, f"{field}_hi", "")
        if hi:
            return hi
    return getattr(obj, field)


def has_hindi(obj, field):
    return bool(getattr(obj, f"{field}_hi", ""))
