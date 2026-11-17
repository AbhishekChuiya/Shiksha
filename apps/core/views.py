from django.contrib.auth.decorators import login_required

from .analytics import learner_analytics
from .charts import learner_charts
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.certificates.models import Certificate
from apps.learning.duties import pending_duties
from apps.learning.models import Module, ModuleProgress, VideoLesson
from apps.plants.journey_view import build_journey
from apps.plants.models import Plant
from apps.quizzes.models import Attempt
from apps.sops.models import SOPDocument

from .access import require_plant
from .models import Notification
from .notify import text_for
from .middleware import SESSION_KEY, VIEW_AS_KEY


def _safe_next(request, fallback="core:dashboard"):
    nxt = request.POST.get("next") or request.GET.get("next")
    if nxt and url_has_allowed_host_and_scheme(nxt, {request.get_host()}):
        return nxt
    return fallback


def _safe(fn, *args):
    """Optional widgets (charts) must never take a whole page down."""
    try:
        return fn(*args)
    except Exception:  # noqa: BLE001
        import logging
        logging.getLogger(__name__).exception("dashboard widget failed")
        return {"has_data": False}


@login_required
def dashboard(request):
    plant = require_plant(request)
    modules = Module.objects.filter(plant=plant, status=Module.Status.PUBLISHED)
    total = modules.count()
    progress = (ModuleProgress.objects.filter(user=request.user, module__in=modules)
                .select_related("module").order_by("-last_seen_at"))
    completed = progress.filter(completed_at__isnull=False).count()
    seconds = progress.aggregate(s=Sum("seconds_spent"))["s"] or 0
    attempts = Attempt.objects.filter(user=request.user, finished_at__isnull=False,
                                      quiz__module__plant=plant)
    best = {}
    for a in attempts:
        best[a.quiz_id] = max(best.get(a.quiz_id, 0), a.score_percent or 0)
    in_progress = [p for p in progress if p.completed_at is None and p.steps_done > 0]
    started_ids = {p.module_id for p in progress}
    recommended = [m for m in modules.select_related("department") if m.pk not in started_ids][:3]
    hour = timezone.localtime().hour
    greeting = "Good morning" if hour < 12 else "Good afternoon" if hour < 17 else "Good evening"
    return render(request, "core/dashboard.html", {
        "greeting": greeting,
        "total_modules": total,
        "completed_modules": completed,
        "pending_modules": total - completed,
        "overall_percent": round(100 * completed / total) if total else 0,
        "learning_minutes": seconds // 60,
        "certificate_count": Certificate.objects.filter(user=request.user).count(),
        "avg_best_score": round(sum(best.values()) / len(best)) if best else None,
        "resume": in_progress[0] if in_progress else None,
        "in_progress": in_progress[1:5],
        "recommended": recommended,
        "charts": _safe(learner_charts, request.user, plant),
        "duties": pending_duties(request.user, plant),
        "journey": build_journey(request.user, plant),
        "recent_certs": Certificate.objects.filter(user=request.user, module__plant=plant).select_related("module")[:3],
        "plant_facts": {"departments": plant.departments.count(), "modules": total, "sops": plant.sops.count()},
    })


@login_required
def plant_overview(request):
    plant = require_plant(request)
    return render(request, "core/plant_overview.html", {
        "plant": plant,
        "departments": plant.departments.prefetch_related("processes"),
        "module_count": plant.modules.filter(status=Module.Status.PUBLISHED).count(),
        "sop_count": plant.sops.count(),
        "videos": plant.videos.all(),
    })


@login_required
@require_POST
def set_plant(request):
    plant = get_object_or_404(request.user.accessible_plants(), pk=request.POST.get("plant"))
    request.session[SESSION_KEY] = plant.pk
    nxt = _safe_next(request)
    # Detail pages (a module, an SOP, a quiz attempt…) belong to one plant — go to the dashboard instead.
    list_pages = ("/", "/plant/", "/modules/", "/quizzes/", "/sops/", "/certificates/", "/incidents/")
    path = nxt.split("?")[0] if isinstance(nxt, str) else ""
    return redirect(nxt if path in list_pages else "core:dashboard")


@login_required
def search(request):
    plant = require_plant(request)
    q = (request.GET.get("q") or "").strip()
    results = {"modules": [], "sops": [], "videos": []}
    if len(q) >= 2:
        results["modules"] = Module.objects.filter(
            Q(title__icontains=q) | Q(title_hi__icontains=q) | Q(summary__icontains=q)
            | Q(overview__icontains=q) | Q(category__icontains=q) | Q(steps__text__icontains=q),
            plant=plant, status=Module.Status.PUBLISHED).distinct()[:20]
        results["sops"] = SOPDocument.objects.filter(
            Q(title__icontains=q) | Q(code__icontains=q) | Q(tags__icontains=q)
            | Q(category__icontains=q) | Q(versions__content__icontains=q),
            plant=plant).distinct()[:20]
        results["videos"] = VideoLesson.objects.filter(
            Q(title__icontains=q) | Q(transcript__icontains=q),
            module__plant=plant).select_related("module")[:20]
    return render(request, "core/search.html", {"q": q, **results,
                  "total": sum(len(v) for v in results.values())})


@login_required
def coming_soon(request, feature):
    return render(request, "core/coming_soon.html", {"feature": feature})


ICON_MODULE = '<path d="m12 3 9 5-9 5-9-5 9-5z"/><path d="m3 13 9 5 9-5"/>'
ICON_SOP = '<path d="M14 3H6v18h12V7l-4-4z"/><path d="M14 3v4h4"/>'
ICON_VIDEO = '<rect x="3" y="6" width="13" height="12" rx="2"/><path d="m16 10 5-3v10l-5-3"/>'


@login_required
def suggest(request):
    """Live search suggestions for the top-bar search box (JSON)."""
    plant = request.plant
    q = (request.GET.get("q") or "").strip()
    out = []
    if plant is not None and len(q) >= 2:
        for m in Module.objects.filter(Q(title__icontains=q) | Q(title_hi__icontains=q) | Q(category__icontains=q),
                                       plant=plant, status=Module.Status.PUBLISHED).select_related("department")[:4]:
            out.append({"type": "module", "title": m.display_title, "sub": f"Module · {m.department.name}",
                        "url": m.get_absolute_url(), "icon": ICON_MODULE})
        for sop in SOPDocument.objects.filter(Q(title__icontains=q) | Q(code__icontains=q) | Q(tags__icontains=q),
                                              plant=plant, versions__status="approved").distinct()[:3]:
            out.append({"type": "sop", "title": sop.title, "sub": f"SOP · {sop.code}",
                        "url": sop.get_absolute_url(), "icon": ICON_SOP})
        for v in VideoLesson.objects.filter(Q(title__icontains=q) | Q(transcript__icontains=q),
                                            module__plant=plant).select_related("module")[:3]:
            out.append({"type": "video", "title": v.title, "sub": f"Video · {v.module.display_title}",
                        "url": f"{v.module.get_absolute_url()}?tab=videos", "icon": ICON_VIDEO})
    return JsonResponse({"results": out[:8]})


@login_required
@require_POST
def set_view_mode(request):
    """Admins can preview the app exactly as a learner sees it, then switch back."""
    if not request.user.real_admin:
        return redirect("core:dashboard")
    if request.POST.get("mode") == "learner":
        request.session[VIEW_AS_KEY] = True
    else:
        request.session.pop(VIEW_AS_KEY, None)
    return redirect(_safe_next(request))


@login_required
def notifications(request):
    items = [{"n": n, "title": text_for(n)[0], "body": text_for(n)[1]} for n in Notification.objects.filter(user=request.user)[:60]]
    return render(request, "core/notifications.html", {"items": items, "unread": sum(1 for i in items if not i["n"].is_read)})


@login_required
def notification_open(request, pk):
    n = get_object_or_404(Notification, pk=pk, user=request.user)
    if not n.is_read:
        n.is_read = True
        n.save(update_fields=["is_read"])
    if n.url and url_has_allowed_host_and_scheme(n.url, {request.get_host()}):
        return redirect(n.url)
    return redirect("core:notifications")


@login_required
@require_POST
def notifications_read_all(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return redirect(_safe_next(request, "core:notifications"))


@login_required
def progress(request):
    """My progress: learning time, quiz scores and module progress, with charts (opened from the dashboard cards)."""
    plant = require_plant(request)
    return render(request, "core/progress.html", {"a": learner_analytics(request.user, plant), "focus": request.GET.get("focus", "")})
