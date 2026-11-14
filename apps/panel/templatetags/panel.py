from django import template

register = template.Library()


@register.filter
def get(d, key):
    try:
        return d.get(key, "")
    except AttributeError:
        return ""


@register.filter
def kind(bound_field):
    """How the generic form template should draw a ModelForm field."""
    f, w = bound_field.field, bound_field.field.widget
    name = w.__class__.__name__
    if name in ("CheckboxInput",):
        return "check"
    if name in ("CheckboxSelectMultiple",):
        return "multi"
    if name in ("FileInput", "ClearableFileInput"):
        return "image" if f.__class__.__name__ == "ImageField" else "file"
    if name == "Textarea":
        return "textarea"
    if name in ("Select", "SelectMultiple"):
        return "select"
    return "input"


@register.filter
def initial(name):
    return (name or "?")[:1].upper()


@register.simple_tag(takes_context=True)
def pn_active(context, *prefixes):
    path = context["request"].path
    return "active" if any(path.startswith(p) for p in prefixes) else ""


@register.filter
def field(form, name):
    try:
        return form[name]
    except KeyError:
        return None


@register.filter
def clearfield(form, name):
    try:
        return form[f"{name}__clear"]
    except KeyError:
        return None


@register.filter
def fileval(form, name):
    try:
        v = getattr(form.instance, name)
        return v if v else None
    except Exception:
        return None


@register.filter
def has_hindi_value(row, fields):
    return any(f.hindi and (row["vals"].get(f.name) or row["errors"].get(f.name)) for f in fields)


@register.filter
def selected(value, option):
    return str(value) == str(option)


_ACTIONS = {
    "plant.save": "saved plant", "plant.gallery": "updated photos of", "plant.structure": "updated departments of", "plant.delete": "deleted plant",
    "module.save": "saved module", "module.steps": "edited the steps of", "module.images": "edited the photos of", "module.safety": "edited safety rules of",
    "module.videos": "edited videos of", "module.problems": "edited problems of", "module.status": "changed visibility of", "module.delete": "deleted module",
    "module.import_steps": "imported steps into", "module.import_quiz": "imported quiz questions into",
    "quiz.settings": "changed quiz settings of", "quiz.question": "saved a quiz question in", "sop.save": "saved SOP", "sop.versions": "updated versions of",
    "sop.delete": "deleted SOP", "user.save": "saved user", "user.import": "imported users", "user.reset_link": "sent a password link to",
    "certificate.revoke": "revoked a certificate for", "incident.status": "updated incident", "incident.created": "reported incident",
    "discussion.hide": "hid a post", "discussion.unhide": "unhid a post", "discussion.pin": "pinned a post", "discussion.unpin": "unpinned a post",
    "sop.version_status": "changed a version status of",
}
_OBJECTS = {"learning.Module": "module", "plants.Plant": "plant", "sops.SOPDocument": "SOP", "sops.SOPVersion": "SOP version", "accounts.User": "user",
            "quizzes.Quiz": "quiz", "quizzes.Question": "question", "incidents.Incident": "incident", "learning.DiscussionPost": "post", "certificates.Certificate": "certificate"}


@register.filter
def describe_action(entry):
    act = entry.action.replace("panel.", "", 1)
    return _ACTIONS.get(act, act.replace(".", " ").replace("_", " "))


@register.filter
def describe_object(entry):
    return f"{_OBJECTS.get(entry.object_type, entry.object_type.split('.')[-1].lower())} #{entry.object_id}"
