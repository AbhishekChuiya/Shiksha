"""Notification bell: creating messages, keeping duty reminders up to date, and turning a stored message into text."""
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.translation import get_language, gettext as _

from .models import Notification

SYNC_EVERY = timedelta(minutes=15)
SESSION_KEY = "duty_sync_at"


def notify(user, kind, *, data=None, title="", body="", url="", key=""):
    """Create one notification. With a `key`, the same alert is never created twice for a user."""
    if key and Notification.objects.filter(user=user, key=key).exists():
        return None
    return Notification.objects.create(user=user, kind=kind, data=data or {}, title=title, body=body, url=url, key=key)


def _names(obj):
    return {"name": obj.title, "name_hi": getattr(obj, "title_hi", ""), "name_gu": getattr(obj, "title_gu", "")}


def _what_names(duty):
    return {"what": duty["kind"], **_names(duty["module"]), "due": duty["due"].isoformat() if duty["due"] else "",
            "days": duty["days"] if duty["days"] is not None else ""}


def sync_duties(user, plant):
    """Create 'assigned', 'due soon' and 'overdue' notices for the user's required items (each only once)."""
    from apps.learning.duties import pending_duties
    made = 0
    for d in pending_duties(user, plant):
        base = f"{d['kind']}:{d['pk']}"
        data = _what_names(d)
        if notify(user, Notification.Kind.ASSIGNED, data=data, url=d["url"], key=f"assigned:{base}"):
            made += 1
        if d["status"] == "due_soon" and notify(user, Notification.Kind.DUE_SOON, data=data, url=d["url"], key=f"due_soon:{base}:{d['due']}"):
            made += 1
        if d["status"] == "overdue" and notify(user, Notification.Kind.OVERDUE, data=data, url=d["url"], key=f"overdue:{base}:{d['due']}"):
            made += 1
    return made


def maybe_sync(request):
    """Run sync_duties at most every 15 minutes per browser session (cheap enough for every page)."""
    user, plant = request.user, getattr(request, "plant", None)
    if plant is None:
        return
    now = timezone.now()
    last = request.session.get(SESSION_KEY)
    if last and now - timezone.datetime.fromisoformat(last) < SYNC_EVERY:
        return
    request.session[SESSION_KEY] = now.isoformat()
    try:
        sync_duties(user, plant)
    except Exception:  # noqa: BLE001 — the bell must never break a page
        import logging
        logging.getLogger(__name__).exception("duty sync failed")


def certificate_issued(cert):
    notify(cert.user, Notification.Kind.CERTIFICATE, data=_names(cert.module), url=cert.get_absolute_url(), key=f"certificate:{cert.pk}")


def _name(data):
    lang = (get_language() or "en")[:2]
    return data.get(f"name_{lang}") or data.get("name", "")


def _date(iso):
    from datetime import date
    try:
        return date_format(date.fromisoformat(iso), "j M Y")
    except (TypeError, ValueError):
        return ""


def text_for(n):
    """(title, body) of a notification in the reader's language."""
    d, name = n.data or {}, _name(n.data or {})
    what_module = d.get("what", "module") == "module"
    if n.kind == Notification.Kind.ANNOUNCEMENT:
        return n.title, n.body
    if n.kind == Notification.Kind.CERTIFICATE:
        return _("Certificate ready: %(name)s") % {"name": name}, _("Well done! You can download it now.")
    when = _date(d.get("due", ""))
    if n.kind == Notification.Kind.ASSIGNED:
        title = (_("New required module: %(name)s") if what_module else _("New required quiz: %(name)s")) % {"name": name}
        return title, (_("Please complete it by %(date)s.") % {"date": when}) if when else _("Please complete it as soon as you can.")
    if n.kind == Notification.Kind.DUE_SOON:
        title = (_("Due soon: %(name)s") if what_module else _("Quiz due soon: %(name)s")) % {"name": name}
        return title, _("Due on %(date)s.") % {"date": when}
    if n.kind == Notification.Kind.OVERDUE:
        title = (_("Overdue: %(name)s") if what_module else _("Quiz overdue: %(name)s")) % {"name": name}
        return title, _("This was due on %(date)s. Please complete it now.") % {"date": when}
    return n.title, n.body
