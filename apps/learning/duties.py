"""Required ("mandatory") modules and quizzes: what a learner still has to do, and how urgent it is."""
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from apps.learning.models import Module, ModuleProgress

SOON_DAYS = 3                       # "due soon" = due within this many days
ORDER = {"overdue": 0, "due_soon": 1, "pending": 2}


def status_for(due, today=None):
    today = today or timezone.localdate()
    if due is None:
        return "pending"
    if due < today:
        return "overdue"
    if due <= today + timedelta(days=SOON_DAYS):
        return "due_soon"
    return "pending"


def _item(kind, obj, module, due, today):
    return {"kind": kind, "obj": obj, "module": module, "due": due, "status": status_for(due, today),
            "days": (due - today).days if due else None, "pk": obj.pk,
            "url": module.get_absolute_url() + ("?tab=sops" if kind == "module" else "?tab=quiz")}


def pending_duties(user, plant, today=None):
    """Required modules not yet completed and required quizzes not yet passed, most urgent first."""
    from apps.quizzes.models import Attempt, Quiz
    today = today or timezone.localdate()
    done = set(ModuleProgress.objects.filter(user=user, completed_at__isnull=False).values_list("module_id", flat=True))
    out = []
    for m in Module.objects.filter(plant=plant, status=Module.Status.PUBLISHED, is_mandatory=True).select_related("department"):
        if m.pk not in done:
            out.append(_item("module", m, m, m.due_date, today))
    passed = set(Attempt.objects.filter(user=user, passed=True).values_list("quiz_id", flat=True))
    for q in (Quiz.objects.filter(module__plant=plant, module__status=Module.Status.PUBLISHED, is_active=True, is_mandatory=True)
              .select_related("module", "module__department")):
        if q.pk not in passed:
            out.append(_item("quiz", q, q.module, q.due_date, today))
    out.sort(key=lambda d: (ORDER[d["status"]], d["due"] or today + timedelta(days=9999), d["kind"]))
    return out


def required_flags(user, plant):
    """{module_id: {"module": due-status-or-'done'}, ...} helper for badges on lists: returns (module_map, quiz_map) of
    {id: {"due": date|None, "status": str, "done": bool}} for every required item of the plant."""
    from apps.quizzes.models import Attempt, Quiz
    today = timezone.localdate()
    done = set(ModuleProgress.objects.filter(user=user, completed_at__isnull=False).values_list("module_id", flat=True))
    mods = {m.pk: {"due": m.due_date, "status": status_for(m.due_date, today), "done": m.pk in done}
            for m in Module.objects.filter(plant=plant, is_mandatory=True)}
    passed = set(Attempt.objects.filter(user=user, passed=True).values_list("quiz_id", flat=True))
    quizzes = {q.module_id: {"due": q.due_date, "status": status_for(q.due_date, today), "done": q.pk in passed}
               for q in Quiz.objects.filter(module__plant=plant, is_mandatory=True)}
    return mods, quizzes
