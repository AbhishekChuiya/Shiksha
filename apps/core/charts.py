"""Numbers for the dashboard charts (learner and admin). Plain dicts; the templates draw them with CSS/SVG — no chart library needed."""
from collections import defaultdict
from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone
from django.utils.text import Truncator

from apps.certificates.models import Certificate
from apps.learning.models import Module, ModuleProgress
from apps.plants.models import Department
from apps.quizzes.models import Attempt


def _donut(parts):
    """parts: [(label, value, css-colour)] -> dict with conic-gradient stops."""
    total = sum(v for _, v, _ in parts) or 1
    acc, stops, legend = 0.0, [], []
    for label, v, colour in parts:
        start, acc = acc, acc + 100 * v / total
        if v:
            stops.append(f"{colour} {start:.2f}% {acc:.2f}%")
        legend.append({"label": label, "value": v, "colour": colour})
    return {"gradient": ", ".join(stops) or "#e5e7eb 0 100%", "legend": legend, "total": sum(v for _, v, _ in parts)}


def learner_charts(user, plant):
    modules = list(Module.objects.filter(plant=plant, status=Module.Status.PUBLISHED).select_related("department").prefetch_related("steps"))
    prog = {p.module_id: p for p in ModuleProgress.objects.filter(user=user, module__in=modules).prefetch_related("completed_steps")}
    done = sum(1 for m in modules if prog.get(m.pk) and prog[m.pk].completed_at)
    started = sum(1 for m in modules if prog.get(m.pk) and not prog[m.pk].completed_at and prog[m.pk].completed_steps.count())
    status = _donut([("Completed", done, "#16a34a"), ("In progress", started, "#f59e0b"), ("Not started", len(modules) - done - started, "#d9dce3")])

    by_dept = defaultdict(lambda: [0, 0, None])
    for m in modules:
        d = by_dept[m.department_id]
        d[2] = m.department
        d[1] += len(m.steps.all())
        if m.pk in prog:
            d[0] += prog[m.pk].completed_steps.count()
    depts = [{"label": d[2].display_name, "pct": round(100 * d[0] / d[1]) if d[1] else 0, "note": f"{d[0]}/{d[1]}"} for d in by_dept.values() if d[1]]

    # One bar per module, showing the BEST score — retakes never lower it.
    best = {}
    for a in Attempt.objects.filter(user=user, finished_at__isnull=False, quiz__module__plant=plant).select_related("quiz__module").order_by("finished_at"):
        cur = best.get(a.quiz.module_id)
        if cur is None or (a.score_percent or 0) >= cur.score_percent:
            best[a.quiz.module_id] = a
    scores = [{"label": Truncator(a.quiz.module.display_title).chars(12), "value": a.score_percent or 0, "tone": "ok" if a.passed else "warn",
               "title": f"{a.quiz.module.title}: best {a.score_percent}%"} for a in list(best.values())[-8:]]
    return {"status": status, "depts": depts, "scores": scores, "has_data": bool(modules)}


def admin_charts():
    now = timezone.now()
    days = [(now - timedelta(days=i)).date() for i in range(13, -1, -1)]
    active = defaultdict(set)
    for uid, seen in ModuleProgress.objects.filter(last_seen_at__gte=now - timedelta(days=14)).values_list("user_id", "last_seen_at"):
        active[timezone.localtime(seen).date()].add(uid)
    daily = [{"label": str(d.day), "value": len(active[d]), "tone": "brand", "title": f"{d:%d %b}: {len(active[d])} active learner(s)"} for d in days]

    weeks = []
    for i in range(7, -1, -1):
        end = now - timedelta(days=7 * i)
        n = Certificate.objects.filter(issued_at__gt=end - timedelta(days=7), issued_at__lte=end).count()
        weeks.append({"label": (end - timedelta(days=6)).strftime("%d/%m"), "value": n, "tone": "ok", "title": f"Week to {end:%d %b}: {n} certificate(s)"})

    dept_rows = []
    for d in Department.objects.select_related("plant").annotate(
            started=Count("modules__progress", distinct=True), finished=Count("modules__progress", filter=Q(modules__progress__completed_at__isnull=False), distinct=True)):
        if d.started:
            dept_rows.append({"label": f"{d.name} · {d.plant.name}", "pct": round(100 * d.finished / d.started), "note": f"{d.finished}/{d.started}"})
    dept_rows.sort(key=lambda r: -r["pct"])

    allp = ModuleProgress.objects.filter(module__status=Module.Status.PUBLISHED)
    finished = allp.filter(completed_at__isnull=False).count()
    status = _donut([("Completed", finished, "#16a34a"), ("In progress", allp.count() - finished, "#f59e0b")])

    hard = []
    for m in Module.objects.filter(status=Module.Status.PUBLISHED).annotate(
            n=Count("quiz__attempts__user", filter=Q(quiz__attempts__finished_at__isnull=False), distinct=True),
            ok=Count("quiz__attempts__user", filter=Q(quiz__attempts__passed=True), distinct=True)).filter(n__gte=1):
        hard.append({"label": m.title, "pct": round(100 * m.ok / m.n), "note": f"{m.ok}/{m.n} learners passed"})
    hard.sort(key=lambda r: r["pct"])
    return {"daily": daily, "daily_max": max([d["value"] for d in daily] + [1]), "weeks": weeks, "weeks_max": max([w["value"] for w in weeks] + [1]), "depts": dept_rows[:6], "status": status, "hard": hard[:5]}
