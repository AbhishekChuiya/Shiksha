from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils.http import url_has_allowed_host_and_scheme, urlencode
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.text import Truncator
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _l
from django.views.decorators.http import require_POST

from apps.core.access import check_plant_access, require_plant
from apps.core.models import AuditLog
from apps.plants.models import Department

from .models import DiscussionPost, Module, SOPStep
from .services import get_progress, refresh_completion

TABS = ["overview", "videos", "sops", "quiz", "problems", "discussion"]


def _module_for(request, slug):
    qs = Module.objects.select_related("plant", "department", "process")
    if not request.user.is_shiksha_admin:           # admins may preview drafts
        qs = qs.filter(status=Module.Status.PUBLISHED)
    module = get_object_or_404(qs, slug=slug)
    check_plant_access(request.user, module.plant)
    request.session["current_plant_id"] = module.plant_id
    request.plant = module.plant
    return module


def _category_chips(mods):
    seen = {}
    for m in mods.exclude(category="").order_by("category"):
        seen.setdefault(m.category, m.display_category)
    return list(seen.items())


def _celebration(request, module):
    """One-shot 'well done' popup data, set by the view that completed something."""
    kind = request.session.pop("celebrate", None)
    if kind == "steps":
        has_quiz = hasattr(module, "quiz") and module.quiz.is_active
        return {"kind": "steps", "title": _("All steps complete!"),
                "text": _("Great work. The quiz is now unlocked.") if has_quiz else _("Great work."),
                "cta_label": _("Take the quiz") if has_quiz else "",
                "cta_url": reverse("learning:module_detail", args=[module.slug]) + "?tab=quiz" if has_quiz else ""}
    if kind == "module":
        from apps.certificates.models import Certificate
        cert = Certificate.objects.filter(user=request.user, module=module).first()
        return {"kind": "module", "title": _("Module complete!"),
                "text": _("Your certificate is ready."),
                "cta_label": _("View certificate") if cert else "",
                "cta_url": cert.get_absolute_url() if cert else ""}
    return None


PAGE_SIZE = 24


# (section key, label, icon, colour class) — the colour tells the learner at a glance what kind of rule it is.
GUIDELINE_STYLES = [
    ("ppe", _l("PPE required"), "shield", "g-ppe"),
    ("hazards", _l("Hazards — high-risk areas"), "zap", "g-hazard"),
    ("practices", _l("Safe operating practices"), "shield", "g-good"),
    ("dos", _l("Do's"), "check-circle", "g-do"),
    ("donts", _l("Don'ts"), "alert", "g-dont"),
    ("safety", _l("Safety"), "shield", "g-good"),
    ("environment", _l("Environment, quality & discipline"), "leaf", "g-env"),
]


def guideline_groups(guidelines):
    out = []
    for key, label, icon, css in GUIDELINE_STYLES:
        items = [g for g in guidelines if g.section == key]
        if items:
            out.append({"key": key, "label": label, "icon": icon, "css": css, "items": items, "chips": key == "ppe"})
    return out


@login_required
def module_list(request):
    plant = require_plant(request)
    all_mods = Module.objects.filter(plant=plant, status=Module.Status.PUBLISHED)
    qs = (all_mods.select_related("department").prefetch_related("steps")
          .order_by("department__order", "department__name", "order", "title"))
    dept = request.GET.get("dept") or ""
    library = request.GET.get("library") or ""
    category = request.GET.get("category") or ""
    q = (request.GET.get("q") or "").strip()
    grid = request.GET.get("view") == "grid"
    if dept.isdigit():
        qs = qs.filter(department_id=dept)
    else:
        dept = ""
    if library:
        qs = qs.filter(library=library)
    if category:
        qs = qs.filter(category=category)
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(title_hi__icontains=q) | Q(summary__icontains=q)
                       | Q(summary_hi__icontains=q) | Q(category__icontains=q) | Q(category_hi__icontains=q))

    def url(**over):
        """Current filters + overrides, as a link. Empty values are dropped; paging resets."""
        params = {"dept": dept, "library": library, "category": category, "q": q, "view": "grid" if grid else ""}
        params.update(over)
        qstr = urlencode({k: v for k, v in params.items() if v})
        return "?" + qstr if qstr else request.path

    progress = {p.module_id: p for p in request.user.module_progress
                .filter(module__plant=plant).prefetch_related("completed_steps")}
    total = qs.count()
    ctx = {
        "count": total, "grid": grid, "q": q,
        "sel": {"dept": dept, "library": library, "category": category},
        "dept_chips": [(_("All"), url(dept=""), not dept)] + [
            (d.display_name, url(dept=str(d.pk)), dept == str(d.pk))
            for d in Department.objects.filter(plant=plant, modules__in=all_mods).distinct()],
        "lib_chips": [(_("All"), url(library=""), not library)] + [
            (label, url(library=val), library == val) for val, label in Module.Library.choices],
        "cat_chips": [(_("All"), url(category=""), not category)] + [
            (label, url(category=val), category == val) for val, label in _category_chips(all_mods)],
        "grid_url": url(view="grid"), "rows_url": url(view=""),
        "has_filters": bool(dept or library or category or q),
        "clear_url": request.path + ("?view=grid" if grid else ""),
        "current_dept": Department.objects.filter(pk=dept, plant=plant).first() if dept else None,
    }
    if grid:
        page = Paginator(qs, PAGE_SIZE).get_page(request.GET.get("page"))
        ctx["page_obj"] = page
        ctx["cards"] = [{"module": m, "progress": progress.get(m.id)} for m in page]
        ctx["prev_url"] = url(page=page.previous_page_number()) if page.has_previous() else ""
        ctx["next_url"] = url(page=page.next_page_number()) if page.has_next() else ""
    else:
        sections = []
        for m in qs:
            if not sections or sections[-1]["dept"].pk != m.department_id:
                sections.append({"dept": m.department, "cards": [], "view_all": url(dept=str(m.department_id), view="grid")})
            sections[-1]["cards"].append({"module": m, "progress": progress.get(m.id)})
        ctx["sections"] = sections
        ctx["cards"] = sections  # truthiness only (empty-state check)
    return render(request, "learning/module_list.html", ctx)


@login_required
def module_detail(request, slug):
    module = _module_for(request, slug)
    tab = request.GET.get("tab", "overview")
    if tab not in TABS:
        tab = "overview"
    progress = get_progress(request.user, module)
    progress.last_seen_at = timezone.now()
    progress.save(update_fields=["last_seen_at"])
    steps = list(module.steps.all())
    done_ids = set(progress.completed_steps.values_list("id", flat=True))
    quiz = getattr(module, "quiz", None)

    ctx = {
        "celebrate": _celebration(request, module),
        "module": module, "tab": tab, "progress": progress,
        "steps_total": len(steps), "steps_done": len(done_ids),
        "quiz": quiz if quiz and quiz.is_active else None,
        "quiz_unlocked": (not quiz) or (not quiz.requires_all_steps) or progress.all_steps_done,
        "problem_count": module.problems.count(),
        "video_count": module.videos.count(),
    }
    if tab == "overview":
        gallery = [{"url": module.cover.url, "caption": module.display_title}] if module.cover else []
        gallery += [{"url": im.image.url, "caption": im.display_caption} for im in module.images.all()]
        ctx["gallery"] = gallery
    if tab == "sops":
        guidelines = list(module.safety_guidelines())
        ctx["guideline_groups"] = guideline_groups(guidelines)
        ctx["has_guidelines"] = bool(guidelines)
        if steps:
            try:
                n = int(request.GET.get("step", 0))
            except ValueError:
                n = 0
            if not n:  # resume at first unfinished step
                n = next((s.number for s in steps if s.id not in done_ids), steps[-1].number)
            idx = next((i for i, s in enumerate(steps) if s.number == n), 0)
            step = steps[idx]
            ctx.update(step_dots=[{"number": x.number, "done": x.id in done_ids, "current": x.id == step.id,
                                   "preview": Truncator(x.display_text).chars(70)} for x in steps],
                       mark_percent=round(100 * (idx + 0.5) / len(steps), 1),
                       step=step, step_index=idx + 1, step_done=step.id in done_ids,
                       prev_step=steps[idx - 1] if idx > 0 else None,
                       next_step=steps[idx + 1] if idx + 1 < len(steps) else None)
    elif tab == "videos":
        ctx["videos"] = module.videos.all()
    elif tab == "problems":
        ctx["problems"] = module.problems.all()
    elif tab == "discussion":
        ctx.update(feed_context(request, module, False, request.GET.get("page")))
    elif tab == "quiz" and quiz:
        ctx["attempts"] = quiz.attempts.filter(user=request.user, finished_at__isnull=False)[:5]
    return render(request, "learning/module_detail.html", ctx)


@login_required
@require_POST
def acknowledge_safety(request, slug):
    module = _module_for(request, slug)
    progress = get_progress(request.user, module)
    if not progress.safety_ack_at:
        progress.safety_ack_at = timezone.now()
        progress.save(update_fields=["safety_ack_at"])
    return redirect(f"{reverse('learning:module_detail', args=[slug])}?tab=sops")


@login_required
@require_POST
def toggle_step(request, slug, number):
    module = _module_for(request, slug)
    step = get_object_or_404(SOPStep, module=module, number=number)
    progress = get_progress(request.user, module)
    if not progress.safety_ack_at:
        messages.error(request, _("Please acknowledge the safety guidelines first."))
    elif request.POST.get("action") == "unmark":
        progress.completed_steps.remove(step)
    else:
        was_all, was_done = progress.all_steps_done, progress.completed_at is not None
        progress.completed_steps.add(step)
        refresh_completion(progress)
        progress.refresh_from_db()
        if progress.completed_at and not was_done:
            request.session["celebrate"] = "module"
        elif progress.all_steps_done and not was_all:
            request.session["celebrate"] = "steps"
        nxt = module.steps.filter(number__gt=number).first()
        if nxt:
            number = nxt.number
    return redirect(f"{reverse('learning:module_detail', args=[slug])}?tab=sops&step={number}")


@login_required
@require_POST
def heartbeat(request, slug):
    """Called every 30 s by the module page while visible — tracks learning time."""
    module = _module_for(request, slug)
    progress = get_progress(request.user, module)
    progress.seconds_spent += 30
    progress.last_seen_at = timezone.now()
    progress.save(update_fields=["seconds_spent", "last_seen_at"])
    return JsonResponse({"ok": True})


# ---------------------------------------------------------------------------
# Global discussion — one community space for every plant and module
# ---------------------------------------------------------------------------
DISCUSSION_PAGE = 15


def _visible_posts(user):
    qs = DiscussionPost.objects.select_related("author", "module")
    return qs if user.is_shiksha_admin else qs.filter(is_hidden=False)


def feed_context(request, module=None, mine=False, page=1):
    """Top-level posts (newest first, pinned on top) with their replies, for one page."""
    qs = _visible_posts(request.user).filter(parent__isnull=True)
    if module is not None:
        qs = qs.filter(module=module)
    if mine:
        qs = qs.filter(author=request.user)
    qs = qs.order_by("-is_pinned", "-created_at")
    pager = Paginator(qs, DISCUSSION_PAGE).get_page(page)
    posts = list(pager)
    replies = {}
    for r in _visible_posts(request.user).filter(parent__in=posts).order_by("created_at"):
        replies.setdefault(r.parent_id, []).append(r)
    for p in posts:
        p.reply_list = replies.get(p.id, [])
    return {"posts": posts, "pager": pager}


@login_required
def discussion(request):
    module = None
    slug = request.GET.get("module")
    if slug:
        module = Module.objects.filter(slug=slug, status=Module.Status.PUBLISHED).first()
    mine = request.GET.get("mine") == "1"
    ctx = feed_context(request, module, mine, request.GET.get("page"))
    ctx.update({
        "module_filter": module, "mine": mine,
        "topics": Module.objects.filter(status=Module.Status.PUBLISHED).select_related("plant").order_by("plant__name", "title"),
        "total": DiscussionPost.objects.filter(parent__isnull=True, is_hidden=False).count(),
    })
    return render(request, "learning/discussion.html", ctx)


@login_required
@require_POST
def discussion_post(request):
    body = (request.POST.get("body") or "").strip()[:4000]
    back = request.POST.get("next") or reverse("discussion:feed")
    if not url_has_allowed_host_and_scheme(back, {request.get_host()}):
        back = reverse("discussion:feed")
    if not body:
        messages.error(request, _("Please write something first."))
        return redirect(back)
    parent = None
    if request.POST.get("parent"):
        parent = DiscussionPost.objects.filter(pk=request.POST["parent"], parent__isnull=True).first()
        if parent is None or (parent.is_hidden and not request.user.is_shiksha_admin):
            messages.error(request, _("That post is no longer available."))
            return redirect(back)
    module = None
    if parent is None and request.POST.get("module"):
        module = Module.objects.filter(slug=request.POST["module"], status=Module.Status.PUBLISHED).first()
    DiscussionPost.objects.create(author=request.user, body=body, parent=parent, module=module or (parent.module if parent else None))
    messages.success(request, _("Reply posted.") if parent else _("Posted."))
    return redirect(back)


@login_required
@require_POST
def discussion_delete(request, pk):
    post = get_object_or_404(DiscussionPost, pk=pk)
    if post.author_id != request.user.id and not request.user.is_shiksha_admin:
        raise PermissionDenied
    post.delete()
    messages.success(request, _("Post deleted."))
    back = request.POST.get("next") or reverse("discussion:feed")
    return redirect(back if url_has_allowed_host_and_scheme(back, {request.get_host()}) else reverse("discussion:feed"))


@login_required
@require_POST
def discussion_moderate(request, pk):
    """Admins: hide / unhide / pin / unpin a post."""
    if not request.user.is_shiksha_admin:
        raise PermissionDenied
    post = get_object_or_404(DiscussionPost, pk=pk)
    action = request.POST.get("action")
    if action in ("hide", "unhide"):
        post.is_hidden = action == "hide"
    elif action in ("pin", "unpin"):
        post.is_pinned = action == "pin"
    post.save(update_fields=["is_hidden", "is_pinned"])
    AuditLog.record(request.user, f"discussion.{action}", post)
    back = request.POST.get("next") or reverse("discussion:feed")
    return redirect(back if url_has_allowed_host_and_scheme(back, {request.get_host()}) else reverse("discussion:feed"))
