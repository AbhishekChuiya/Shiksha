"""Personal learning analytics for one learner in one plant: time spent, quiz scores and module progress."""
from collections import defaultdict
from datetime import timedelta

from django.db.models import Sum
from django.utils import timezone
from django.utils.text import Truncator

from apps.learning.duties import pending_duties
from apps.learning.models import Module, ModuleProgress, StudyDay
from apps.quizzes.models import Attempt

from .charts import _donut


def _minutes(seconds):
    return round(seconds / 60)


def learner_analytics(user, plant):
    today = timezone.localdate()
    modules = list(Module.objects.filter(plant=plant, status=Module.Status.PUBLISHED).select_related("department").prefetch_related("steps"))
    by_id = {m.pk: m for m in modules}
    progress = {p.module_id: p for p in ModuleProgress.objects.filter(user=user, module__in=modules).prefetch_related("completed_steps")}

    # ---- time
    days = [today - timedelta(days=i) for i in range(13, -1, -1)]
    per_day = defaultdict(int)
    per_module = defaultdict(int)
    per_dept = defaultdict(int)
    for sd in StudyDay.objects.filter(user=user, module__in=modules, day__gte=days[0]):
        per_day[sd.day] += sd.seconds
    for p in progress.values():
        per_module[p.module_id] += p.seconds_spent
        per_dept[by_id[p.module_id].department.display_name] += p.seconds_spent
    total_seconds = sum(per_module.values())
    week_seconds = sum(per_day[d] for d in days[-7:])
    time_bars = [{"label": str(d.day), "value": _minutes(per_day[d]), "tone": "brand", "title": f"{d:%d %b}: {_minutes(per_day[d])} min"} for d in days]
    top_modules = sorted(((by_id[mid], s) for mid, s in per_module.items() if s), key=lambda x: -x[1])[:6]
    top_max = max([s for _, s in top_modules] + [1])
    time_modules = [{"label": m.display_title, "pct": round(100 * s / top_max), "note": f"{_minutes(s)} min", "pct_text": f"{_minutes(s)}m"} for m, s in top_modules]
    dept_total = max(list(per_dept.values()) + [1])
    time_depts = [{"label": name, "pct": round(100 * s / dept_total), "note": f"{_minutes(s)} min", "pct_text": f"{_minutes(s)}m"} for name, s in sorted(per_dept.items(), key=lambda x: -x[1]) if s]
    active_days = sum(1 for d in days[-7:] if per_day[d])

    # ---- scores
    attempts = list(Attempt.objects.filter(user=user, finished_at__isnull=False, quiz__module__plant=plant).select_related("quiz__module").order_by("-finished_at"))
    best = {}
    for a in reversed(attempts):
        cur = best.get(a.quiz.module_id)
        if cur is None or (a.score_percent or 0) >= (cur.score_percent or 0):
            best[a.quiz.module_id] = a
    best_list = sorted(best.values(), key=lambda a: a.score_percent or 0)
    avg_best = round(sum(a.score_percent or 0 for a in best_list) / len(best_list)) if best_list else None
    passed_modules = sum(1 for a in best_list if a.passed)
    score_bars = [{"label": Truncator(a.quiz.module.display_title).chars(12), "value": a.score_percent or 0, "tone": "ok" if a.passed else "warn",
                   "title": f"{a.quiz.module.title}: best {a.score_percent}%"} for a in reversed(best_list[-8:])]
    trend = [{"label": f"{timezone.localtime(a.finished_at):%d/%m}", "value": a.score_percent or 0, "tone": "ok" if a.passed else "warn",
              "title": f"{a.quiz.module.title}: {a.score_percent}%"} for a in reversed(attempts[:10])]
    weakest = [a for a in best_list if not a.passed][:3] or best_list[:3]

    # ---- modules
    done = sum(1 for m in modules if progress.get(m.pk) and progress[m.pk].completed_at)
    started = sum(1 for m in modules if progress.get(m.pk) and not progress[m.pk].completed_at and progress[m.pk].completed_steps.count())
    status = _donut([("Completed", done, "#16a34a"), ("In progress", started, "#f59e0b"), ("Not started", len(modules) - done - started, "#d9dce3")])
    dept_rows = defaultdict(lambda: [0, 0, 0, None])
    for m in modules:
        r = dept_rows[m.department_id]
        r[3] = m.department
        r[1] += 1
        if progress.get(m.pk) and progress[m.pk].completed_at:
            r[0] += 1
    depts = [{"label": r[3].display_name, "pct": round(100 * r[0] / r[1]), "note": f"{r[0]}/{r[1]}"} for r in dept_rows.values() if r[1]]
    in_progress = [{"module": p.module, "percent": p.percent} for p in sorted((p for p in progress.values() if not p.completed_at and p.completed_steps.count()),
                                                                            key=lambda p: p.last_seen_at, reverse=True)[:6]]
    return {
        "total_minutes": _minutes(total_seconds), "week_minutes": _minutes(week_seconds), "active_days": active_days,
        "avg_per_active_day": _minutes(week_seconds / active_days) if active_days else 0,
        "time_bars": time_bars, "time_max": max([b["value"] for b in time_bars] + [1]), "time_modules": time_modules, "time_depts": time_depts,
        "attempt_count": len(attempts), "avg_best": avg_best, "passed_modules": passed_modules, "quizzed_modules": len(best_list),
        "pass_rate": round(100 * passed_modules / len(best_list)) if best_list else None,
        "score_bars": score_bars, "trend": trend, "attempts": attempts[:8], "weakest": weakest,
        "modules_done": done, "modules_started": started, "modules_not_started": len(modules) - done - started, "modules_total": len(modules), "status": status, "depts": depts, "in_progress": in_progress,
        "duties": pending_duties(user, plant),
    }
