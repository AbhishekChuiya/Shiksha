from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import F, Q
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

from .models import DiscussionPost, Module, ModuleProgress, ModuleSOP, StudyDay, SOPAcknowledgement, SOPStep
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
        has_quiz = hasattr(module, "quiz") and module.quiz.is_active and module.quiz.questions.exists()
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
    ("prestart", _l("Pre-start checks"), "check-circle", "g-pre"),
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


def _tag_required(mods, user, plant):
    """Put `duty` ({due, status, done}) on the required modules, so cards can show a Required / Due badge."""
    from .duties import required_flags
    flags, _quiz = required_flags(user, plant)
    for m in mods:
        m.duty = flags.get(m.pk)
    return mods


def _module_duty(user, module, quiz):
    """Required-module / required-quiz notes for the module header (only the ones still to do)."""
    from apps.quizzes.models import Attempt
    from .duties import status_for
    out = {}
    if module.is_mandatory and not ModuleProgress.objects.filter(user=user, module=module, completed_at__isnull=False).exists():
        out["module"] = {"due": module.due_date, "status": status_for(module.due_date)}
    if quiz is not None and quiz.is_active and quiz.is_mandatory and not Attempt.objects.filter(user=user, quiz=quiz, passed=True).exists():
        out["quiz"] = {"due": quiz.due_date, "status": status_for(quiz.due_date)}
    return out


NO_CATEGORY = "__none__"
STATUS_CHOICES = [("required", _l("Required")), ("todo", _l("Not started")), ("progress", _l("In progress")), ("done", _l("Completed"))]


@login_required
def module_list(request):
    plant = require_plant(request)
    all_mods = Module.objects.filter(plant=plant, status=Module.Status.PUBLISHED)
    qs = (all_mods.select_related("department").prefetch_related("steps", "sops")
          .order_by("order", "department__order", "title"))
    dept = request.GET.get("dept") or ""
    library = request.GET.get("library") or ""
    category = request.GET.get("category") or ""
    status = request.GET.get("status") or ""
    q = (request.GET.get("q") or "").strip()
    grid = True      # one flat, numbered card list (flow order) on every device
    progress = {p.module_id: p for p in request.user.module_progress
                .filter(module__plant=plant).prefetch_related("completed_steps")}
    done_ids = {i for i, p in progress.items() if p.completed_at}
    prog_ids = {i for i, p in progress.items() if not p.completed_at and p.steps_done}
    req_ids = set(all_mods.filter(is_mandatory=True).values_list("pk", flat=True)) - done_ids
    if status not in dict(STATUS_CHOICES):
        status = ""
    if library not in dict(Module.Library.choices):
        library = ""
    if not dept.isdigit():
        dept = ""

    # Filters narrow step by step: type (Production / Department SOPs) → department → category → status.
    # Every row below shows counts for what is left after the rows above it.
    scope = all_mods.filter(library=library) if library else all_mods
    dept_scope = scope
    if dept:
        scope = scope.filter(department_id=dept)
    cat_scope = scope
    if category == NO_CATEGORY:
        scope = scope.filter(category="")
    elif category:
        scope = scope.filter(category=category)
    scope_ids = set(scope.values_list("pk", flat=True))
    qs = qs.filter(pk__in=scope_ids)
    if status == "todo":
        qs = qs.exclude(pk__in=done_ids | prog_ids)
    elif status:
        qs = qs.filter(pk__in={"required": req_ids, "progress": prog_ids, "done": done_ids}[status])
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(title_hi__icontains=q) | Q(summary__icontains=q)
                       | Q(summary_hi__icontains=q) | Q(category__icontains=q) | Q(category_hi__icontains=q))

    def url(**over):
        """Current filters + overrides, as a link. Empty values are dropped; paging resets."""
        params = {"dept": dept, "library": library, "category": category, "status": status, "q": q, "view": "grid" if grid else ""}
        params.update(over)
        qstr = urlencode({k: v for k, v in params.items() if v})
        return "?" + qstr if qstr else request.path

    total = qs.count()
    n_all = scope.count()
    depts = list(Department.objects.filter(plant=plant, modules__in=dept_scope).distinct())
    dept_count = {d.pk: dept_scope.filter(department=d).count() for d in depts}
    cats, uncategorised = {}, 0
    for m in cat_scope.select_related("department").order_by("department__order", "department__name", "order", "title"):     # chips follow the order modules appear in
        if not m.category:
            uncategorised += 1
            continue
        row = cats.setdefault(m.category, [m.display_category, 0])
        row[1] += 1
    if uncategorised:
        cats[NO_CATEGORY] = [_("Uncategorised"), uncategorised]
    n_status = {"": n_all, "required": len(req_ids & scope_ids), "todo": len(scope_ids - done_ids - prog_ids),
                "progress": len(prog_ids & scope_ids), "done": len(done_ids & scope_ids)}
    ctx = {
        "count": total, "grid": grid, "q": q, "status": status,
        "sel": {"dept": dept, "library": library, "category": category, "status": status},
        "lib_tabs": [(_("All"), url(library="", dept="", category=""), not library, all_mods.count())] + [
            (label, url(library=val, dept="", category=""), library == val, all_mods.filter(library=val).count())
            for val, label in Module.Library.choices],
        "dept_tabs": [(_("All"), url(dept="", category=""), not dept, dept_scope.count())] + [
            (d.display_name, url(dept=str(d.pk), category=""), dept == str(d.pk), dept_count[d.pk]) for d in depts],
        "cat_chips": [(_("All"), url(category=""), not category, cat_scope.count())] + [
            (label, url(category=val), category == val, n) for val, (label, n) in cats.items()],
        "status_chips": [(_("All"), url(status=""), not status, n_status[""], "")] + [
            (label, url(status=key), status == key, n_status[key], key) for key, label in STATUS_CHOICES],
        "grid_url": url(view="grid"), "rows_url": url(view=""),
        "has_filters": bool(dept or library or category or status or q),
        "clear_url": request.path + ("?view=grid" if grid else ""),
        "current_dept": Department.objects.filter(pk=dept, plant=plant).first() if dept else None,
    }
    if grid:
        page = Paginator(qs, PAGE_SIZE).get_page(request.GET.get("page"))
        ctx["page_obj"] = page
        _tag_required(page.object_list, request.user, plant)
        ctx["cards"] = [{"module": m, "progress": progress.get(m.id), "n": page.start_index() + i} for i, m in enumerate(page)]
        ctx["prev_url"] = url(page=page.previous_page_number()) if page.has_previous() else ""
        ctx["next_url"] = url(page=page.next_page_number()) if page.has_next() else ""
    else:
        sections = []
        for m in _tag_required(list(qs), request.user, plant):
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
        "quiz": quiz if quiz and quiz.is_active and quiz.questions.exists() else None,
        "quiz_unlocked": (not quiz) or (not quiz.requires_all_steps) or progress.all_steps_done,
        "problem_count": module.problems.count(),
        "video_count": module.videos.count(),
    }
    # "Your learning journey": what is done, what to do now, what comes next.
    from apps.quizzes.models import Attempt
    quiz_on = ctx["quiz"]
    quiz_passed = bool(quiz_on and Attempt.objects.filter(quiz=quiz_on, user=request.user, passed=True).exists())
    safety_done = bool(progress.safety_ack_at)
    steps_done_all = bool(steps) and len(done_ids) == len(steps)
    finished = bool(progress.completed_at)
    # The quiz step is always shown (every module is meant to have one). Until the admin has added questions it reads "coming soon" and does not block the certificate.
    flags = [("safety", safety_done), ("steps", steps_done_all)] + ([("quiz", quiz_passed)] if quiz_on else []) + [("cert", finished)]
    journey, found = {}, False
    for key, done in flags:
        journey[key] = "done" if done else ("todo" if found else "now")
        found = found or not done
    if not quiz_on:
        journey["quiz"] = "soon"
    if finished:
        cta = ("review", "?tab=sops")
    elif steps_done_all and quiz_on and not quiz_passed:
        cta = ("quiz", "?tab=quiz")
    elif safety_done and done_ids:
        cta = ("continue", "?tab=sops")
    else:
        cta = ("start", "?tab=sops")
    ctx.update(journey=journey, cta_key=cta[0], cta_url=cta[1], quiz_passed=quiz_passed, duty=_module_duty(request.user, module, quiz))
    if tab == "overview":
        gallery = [{"url": module.cover.url, "caption": module.display_title}] if module.cover else []
        gallery += [{"url": im.image.url, "caption": im.display_caption} for im in module.images.all()]
        ctx["gallery"] = gallery
        ctx.update(roles=list(module.roles.all()), escalations=list(module.escalations.all()), records=list(module.records.all()),
                   accountable=module.accountable_summary)
    if tab == "sops":
        sops = list(module.sops.all())
        sel = None
        if sops:                                   # a module can hold several procedures (SOPs)
            try:
                sid = int(request.GET.get("sop", 0))
            except ValueError:
                sid = 0
            sel = (next((x for x in sops if x.id == sid), None)
                   or next((x for x in sops if any(st.sop_id == x.id and st.id not in done_ids for st in steps)), None) or sops[0])
        sop_steps = [x for x in steps if x.sop_id == (sel.id if sel else None)]
        sop_done = sum(1 for x in sop_steps if x.id in done_ids)
        acks = set(SOPAcknowledgement.objects.filter(user=request.user, sop__module=module).values_list("sop_id", flat=True))
        guidelines = list(module.safety_guidelines()) + (list(sel.guidelines.all()) if sel else [])
        cards = []
        for x in sops:
            xs = [st for st in steps if st.sop_id == x.id]
            cards.append({"sop": x, "number": len(cards) + 1, "total": len(xs), "done": sum(1 for st in xs if st.id in done_ids), "current": sel is not None and x.id == sel.id})
        ctx.update(sel_sop=sel, sop_cards=cards, sopq=f"&sop={sel.id}" if sel else "",
                   safety_ok=(sel.id in acks) if sel else bool(progress.safety_ack_at),
                   sop_total=len(sop_steps), sop_done=sop_done, sop_percent=round(100 * sop_done / len(sop_steps)) if sop_steps else 0,
                   guideline_groups=guideline_groups(guidelines), has_guidelines=bool(guidelines))
        if sop_steps:
            try:
                n = int(request.GET.get("step", 0))
            except ValueError:
                n = 0
            if not n:  # resume at first unfinished step
                n = next((x.number for x in sop_steps if x.id not in done_ids), sop_steps[-1].number)
            idx = next((i for i, x in enumerate(sop_steps) if x.number == n), 0)
            step = sop_steps[idx]
            ctx.update(step_dots=[{"number": x.number, "done": x.id in done_ids, "current": x.id == step.id,
                                   "preview": Truncator(x.display_text).chars(70)} for x in sop_steps],
                       mark_percent=round(100 * (idx + 0.5) / len(sop_steps), 1),
                       step=step, step_index=idx + 1, step_done=step.id in done_ids,
                       prev_step=sop_steps[idx - 1] if idx > 0 else None,
                       next_step=sop_steps[idx + 1] if idx + 1 < len(sop_steps) else None)
    elif tab == "videos":
        ctx["videos"] = module.videos.all()
    elif tab == "problems":
        ctx["problems"] = module.problems.all()
    elif tab == "discussion":
        ctx.update(feed_context(request, module, False, request.GET.get("page")))
    elif tab == "quiz" and quiz:
        ctx["attempts"] = quiz.attempts.filter(user=request.user, finished_at__isnull=False)[:5]
    return render(request, "learning/module_detail.html", ctx)


def _posted_sop(request, module):
    sid = request.POST.get("sop") or request.GET.get("sop") or ""
    return module.sops.filter(pk=sid).first() if sid.isdigit() else None


def _sop_query(sop):
    return f"&sop={sop.pk}" if sop else ""


@login_required
@require_POST
def acknowledge_safety(request, slug):
    module = _module_for(request, slug)
    progress = get_progress(request.user, module)
    sop = _posted_sop(request, module)
    if sop:
        SOPAcknowledgement.objects.get_or_create(user=request.user, sop=sop)
    if not progress.safety_ack_at:
        progress.safety_ack_at = timezone.now()
        progress.save(update_fields=["safety_ack_at"])
    return redirect(f"{reverse('learning:module_detail', args=[slug])}?tab=sops{_sop_query(sop)}")


@login_required
@require_POST
def toggle_step(request, slug, number):
    module = _module_for(request, slug)
    sop = _posted_sop(request, module)
    step = get_object_or_404(SOPStep, module=module, sop=sop, number=number)
    progress = get_progress(request.user, module)
    acked = SOPAcknowledgement.objects.filter(user=request.user, sop=sop).exists() if sop else bool(progress.safety_ack_at)
    if not acked:
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
        nxt = module.steps.filter(sop=sop, number__gt=number).first()
        if nxt:
            number = nxt.number
    return redirect(f"{reverse('learning:module_detail', args=[slug])}?tab=sops{_sop_query(sop)}&step={number}")


@login_required
@require_POST
def heartbeat(request, slug):
    """Called every 30 s by the module page while visible — tracks learning time."""
    module = _module_for(request, slug)
    progress = get_progress(request.user, module)
    progress.seconds_spent += 30
    progress.last_seen_at = timezone.now()
    progress.save(update_fields=["seconds_spent", "last_seen_at"])
    day, _created = StudyDay.objects.get_or_create(user=request.user, module=module, day=timezone.localdate())
    StudyDay.objects.filter(pk=day.pk).update(seconds=F("seconds") + 30)
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
    plant = module.plant if module is not None else getattr(request, "plant", None)
    if plant is not None:
        qs = qs.filter(plant=plant)          # every plant has its own space
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
        module = Module.objects.filter(slug=slug, status=Module.Status.PUBLISHED, plant=request.plant).first()
    mine = request.GET.get("mine") == "1"
    ctx = feed_context(request, module, mine, request.GET.get("page"))
    ctx.update({
        "module_filter": module, "mine": mine,
        "topics": Module.objects.filter(status=Module.Status.PUBLISHED, plant=request.plant).select_related("plant").order_by("title") if request.plant else Module.objects.none(),
        "total": DiscussionPost.objects.filter(parent__isnull=True, is_hidden=False, plant=request.plant).count() if request.plant else 0,
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
    plant = parent.plant if parent else (module.plant if module else getattr(request, "plant", None))
    DiscussionPost.objects.create(author=request.user, body=body, parent=parent, plant=plant, module=module or (parent.module if parent else None))
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
