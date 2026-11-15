from django.utils.translation import get_language

LANG_NAMES = {"en": "English", "hi": "हिन्दी", "gu": "ગુજરાતી"}


def current_lang():
    return (get_language() or "en").lower().split("-")[0]


def localized(obj, field):
    """Return `<field>_hi` / `<field>_gu` for a Hindi / Gujarati UI when it is filled in, else the English value."""
    lang = current_lang()
    if lang in ("hi", "gu"):
        value = getattr(obj, f"{field}_{lang}", "")
        if value:
            return value
    return getattr(obj, field)


def has_hindi(obj, field):
    return bool(getattr(obj, f"{field}_hi", ""))


def has_translation(obj, field):
    """True when the UI is English, or the current language has its own text for this field."""
    lang = current_lang()
    return lang not in ("hi", "gu") or bool(getattr(obj, f"{field}_{lang}", ""))
