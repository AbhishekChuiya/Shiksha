import csv
import io
from datetime import timedelta

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Avg, Count, Max, Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import urlencode
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.certificates.models import Certificate
from apps.core.charts import admin_charts
from apps.core.models import AuditLog
from apps.incidents.models import Incident
from apps.learning.importers import ImportError_, import_quiz, import_steps
from apps.learning.tables import TableError, read_table
from apps.learning.models import (DiscussionPost, Module, ModuleImage, ModuleProgress, ProblemSolution, SafetyGuideline, SOPStep, VideoLesson)
from apps.plants.models import Department, Plant, PlantPhoto, Process
from apps.quizzes.models import Attempt, Choice, Question, Quiz
from apps.sops.models import SOPDocument

from .decorators import admin_required
from .editor import Editor, F
from .forms import ModuleForm, PlantForm, QuestionForm, QuizSettingsForm

PER_PAGE = 25


# ----------------------------------------------------------------------------- helpers
def paginate(request, qs, per=PER_PAGE):
    return Paginator(qs, per).get_page(request.GET.get("page"))


def qurl(request, **over):
    """Current query string with overrides; empty values dropped; paging reset unless given."""
    params = {k: v for k, v in request.GET.items() if k != "page"}
    params.update(over)
    q = urlencode({k: v for k, v in params.items() if v not in ("", None)})
    return request.path + ("?" + q if q else "")


def audit(request, action, obj, **detail):
    AuditLog.record(request.user, f"panel.{action}", obj, **detail)


def render_panel(request, template, **ctx):
    ctx.setdefault("page_title", "")
    return render(request, template, ctx)


def crumbs(*items):
    return [{"label": l, "url": u} for l, u in items]


# ----------------------------------------------------------------------------- dashboard
@admin_required
def dashboard(request):
    now = timezone.now()
    published = Module.objects.filter(status=Module.Status.PUBLISHED)
    stats = [
        {"label": "Active users", "value": User.objects.filter(is_active=True).count(), "icon": "users", "url": reverse("panel:users")},
        {"label": "Published modules", "value": published.count(), "icon": "layers", "url": reverse("panel:modules") + "?status=published"},
        {"label": "SOP documents", "value": SOPDocument.objects.count(), "icon": "file", "url": reverse("panel:sops")},
        {"label": "Open incidents", "value": Incident.objects.exclude(status="closed").count(), "icon": "alert", "url": reverse("panel:incidents") + "?status=open"},
        {"label": "Certificates (30 days)", "value": Certificate.objects.filter(issued_at__gte=now - timedelta(days=30)).count(), "icon": "award", "url": reverse("panel:certificates")},
        {"label": "Quiz pass rate", "value": _pass_rate(), "icon": "gauge", "url": reverse("panel:reports")},
    ]
    attention = []
    no_steps = published.annotate(n=Count("steps")).filter(n=0)
    if no_steps.exists():
        attention.append({"level": "warn", "text": f"{no_steps.count()} published module(s) have no SOP steps yet", "url": reverse("panel:modules") + "?issue=nosteps"})
    no_quiz = published.filter(quiz__isnull=True)
    if no_quiz.exists():
        attention.append({"level": "info", "text": f"{no_quiz.count()} published module(s) have no quiz", "url": reverse("panel:modules") + "?issue=noquiz"})
    no_hi = published.filter(title_hi="")
    if no_hi.exists():
        attention.append({"level": "info", "text": f"{no_hi.count()} module(s) have no Hindi title", "url": reverse("panel:modules") + "?issue=nohindi"})
    drafts = Module.objects.filter(status=Module.Status.DRAFT).count()
    if drafts:
        attention.append({"level": "info", "text": f"{drafts} draft module(s) are waiting to be published", "url": reverse("panel:modules") + "?status=draft"})
    no_sop = SOPDocument.objects.exclude(versions__status="approved")
    if no_sop.exists():
        attention.append({"level": "warn", "text": f"{no_sop.count()} SOP(s) have no approved version — learners can't see them", "url": reverse("panel:sops") + "?issue=unapproved"})
    open_inc = Incident.objects.filter(status="open").count()
    if open_inc:
        attention.append({"level": "warn", "text": f"{open_inc} incident(s) are waiting for review", "url": reverse("panel:incidents") + "?status=open"})
    hidden = DiscussionPost.objects.filter(is_hidden=True).count()
    return render_panel(request, "panel/dashboard.html", page_title="Overview", stats=stats, attention=attention,
                        charts=_safe_charts(), activity=AuditLog.objects.select_related("actor")[:8], new_users=User.objects.order_by("-date_joined")[:5], hidden_posts=hidden)


def _safe_charts():
    try:
        return admin_charts()
    except Exception:  # noqa: BLE001
        import logging
        logging.getLogger(__name__).exception("admin charts failed")
        return {"daily": [], "daily_max": 1, "weeks": [], "weeks_max": 1, "depts": [], "status": {"gradient": "#e5e7eb 0 100%", "legend": [], "total": 0}, "hard": []}


def _pass_rate():
    """Share of learner+quiz pairs that have passed at least once (a retake never counts against a learner)."""
    pairs = Attempt.objects.filter(finished_at__isnull=False).values("user", "quiz").annotate(ok=Count("id", filter=Q(passed=True)))
    n = pairs.count()
    return f"{round(100 * pairs.filter(ok__gt=0).count() / n)}%" if n else "—"


# ----------------------------------------------------------------------------- plants
@admin_required
def plant_list(request):
    q = (request.GET.get("q") or "").strip()
    qs = Plant.objects.annotate(n_modules=Count("modules", distinct=True), n_users=Count("users", distinct=True)).order_by("order", "name")
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(company__icontains=q) | Q(location__icontains=q))
    return render_panel(request, "panel/plant_list.html", page_title="Plants", plants=qs, q=q)


PLANT_TABS = [("details", "Details"), ("gallery", "Photos"), ("structure", "Departments & processes")]


@admin_required
def plant_edit(request, pk=None, tab="details"):
    plant = get_object_or_404(Plant, pk=pk) if pk else None
    if tab not in dict(PLANT_TABS) or (plant is None and tab != "details"):
        raise Http404
    ctx = {"plant": plant, "tab": tab, "tabs": PLANT_TABS, "page_title": plant.name if plant else "New plant",
           "crumbs": crumbs(("Plants", reverse("panel:plants")), (plant.name if plant else "New plant", None))}
    if tab == "details":
        form = PlantForm(request.POST or None, request.FILES or None, instance=plant)
        if request.method == "POST" and form.is_valid():
            obj = form.save()
            audit(request, "plant.save", obj)
            messages.success(request, f"{obj.name} saved.")
            return redirect("panel:plant_tab", pk=obj.pk, tab="details")
        ctx.update(form=form, groups=[("Basics", ["name", "company", "location", "tagline", "about", "banner"]),
                                        ("Hindi (optional)", ["location_hi", "tagline_hi", "about_hi"]), ("Gujarati (optional)", ["location_gu", "tagline_gu", "about_gu"]), ("Settings", ["is_active", "order", "code"])])
        return render_panel(request, "panel/plant_edit.html", **ctx)

    if tab == "gallery":
        eds = [Editor("photos", PlantPhoto, [F("image", "Photo", "image", required=True), F("caption", "Caption"), F("caption_hi", "Caption (Hindi)", hindi=True)],
                      {"plant": plant}, title="Plant photos", noun="photo",
                      info="These appear in the Photo gallery on the Plant Overview page. Learners can tap a photo to enlarge it. Drag order = up/down arrows.",
                      empty_hint="No photos yet — add some to bring the Plant Overview page to life.")]
    else:
        depts = list(plant.departments.order_by("order", "id"))
        eds = [Editor("depts", Department, [F("name", "Department name", required=True), F("name_hi", "Name (Hindi)", hindi=True)], {"plant": plant},
                      title="Departments", noun="department", empty_hint="Add your first department, e.g. Production, QC, Maintenance.")]
        if depts:
            eds.append(Editor("procs", Process, [F("department", "Department", "select", required=True, choices=[(d.pk, d.name) for d in depts], fk=True),
                                                 F("name", "Process name", required=True), F("name_hi", "Name (Hindi)", hindi=True)],
                              {}, filter={"department__plant": plant}, title="Processes", noun="process", info="A process is a step in production, e.g. Extrusion or Anodizing."))
    def no_duplicate_departments(parsed):
        names = [(r["vals"].get("name") or "").strip().lower() for r in parsed.get("depts", [])]
        dup = next((n for n in names if n and names.count(n) > 1), None)
        return f"There are two departments called “{dup}”. Each department name must be different." if dup else None

    return _editor_page(request, "panel/plant_edit.html", eds, ctx, redirect_name="panel:plant_tab", redirect_kwargs={"pk": plant.pk, "tab": tab},
                        saved=f"{plant.name} updated.", log=("plant." + tab, plant), extra_validate=no_duplicate_departments if tab == "structure" else None)


@admin_required
@require_POST
def plant_delete(request, pk):
    plant = get_object_or_404(Plant, pk=pk)
    if plant.incidents.exists():
        messages.error(request, f"{plant.name} has incident reports, so it can't be deleted. Untick 'Active' instead to hide it from learners.")
        return redirect("panel:plant_tab", pk=pk, tab="details")
    name = plant.name
    audit(request, "plant.delete", plant, name=name)
    plant.delete()
    messages.success(request, f"{name} deleted.")
    return redirect("panel:plants")


# ----------------------------------------------------------------------------- editor page helper
def _editor_page(request, template, editors, ctx, *, redirect_name, redirect_kwargs, saved="Saved.", log=None, extra_validate=None):
    parsed = {}
    if request.method == "POST":
        all_ok = True
        for ed in editors:
            rows, ok = ed.parse(request.POST, request.FILES)
            parsed[ed.key] = rows
            all_ok = all_ok and ok
        problem = extra_validate(parsed) if (all_ok and extra_validate) else None
        if all_ok and not problem:
            with transaction.atomic():
                for ed in editors:
                    ed.apply(parsed[ed.key])
            if log:
                audit(request, log[0], log[1])
            messages.success(request, saved)
            return redirect(redirect_name, **redirect_kwargs)
        messages.error(request, problem or "Some rows need attention — they are marked in red. Nothing was saved yet.")
    ctx["editors"] = [ed.context(parsed.get(ed.key)) for ed in editors]
    return render_panel(request, template, **ctx)


# ----------------------------------------------------------------------------- modules
MODULE_TABS = [("details", "Details"), ("images", "Photos"), ("steps", "SOP steps"), ("safety", "Safety rules"),
               ("videos", "Videos"), ("problems", "Problems & solutions"), ("quiz", "Quiz")]


@admin_required
def module_list(request):
    q = (request.GET.get("q") or "").strip()
    plant, status, issue = request.GET.get("plant") or "", request.GET.get("status") or "", request.GET.get("issue") or ""
    qs = (Module.objects.select_related("plant", "department").annotate(n_steps=Count("steps", distinct=True), n_q=Count("quiz__questions", distinct=True))
          .order_by("plant__order", "department__order", "order", "title"))
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(title_hi__icontains=q) | Q(category__icontains=q) | Q(slug__icontains=q))
    if plant.isdigit():
        qs = qs.filter(plant_id=plant)
    if status in ("draft", "published", "archived"):
        qs = qs.filter(status=status)
    if issue == "nosteps":
        qs = qs.filter(n_steps=0)
    elif issue == "noquiz":
        qs = qs.filter(quiz__isnull=True)
    elif issue == "nohindi":
        qs = qs.filter(title_hi="")
    page = paginate(request, qs)
    return render_panel(request, "panel/module_list.html", page_title="Modules", page=page, q=q, plant=plant, status=status, issue=issue,
                        plants=Plant.objects.all(), total=page.paginator.count, base=qurl(request))


@admin_required
@require_POST
def module_bulk(request):
    ids = request.POST.getlist("ids")
    action = request.POST.get("action")
    qs = Module.objects.filter(pk__in=[i for i in ids if i.isdigit()])
    if not qs:
        messages.error(request, "Tick at least one module first.")
    elif action == "publish":
        n = qs.update(status=Module.Status.PUBLISHED)
        messages.success(request, f"{n} module(s) published.")
    elif action == "unpublish":
        n = qs.update(status=Module.Status.DRAFT)
        messages.success(request, f"{n} module(s) moved to draft — hidden from learners.")
    back = request.POST.get("next") or reverse("panel:modules")
    return redirect(back if back.startswith("/manage/") else reverse("panel:modules"))


def _module_counts(module):
    if module is None:
        return {}
    quiz = getattr(module, "quiz", None)
    return {"steps": module.steps.count(), "images": module.images.count(), "videos": module.videos.count(), "problems": module.problems.count(),
            "safety": module.own_guidelines.count(), "quiz": quiz.questions.count() if quiz else 0}


def _module_ctx(module, tab, title=None):
    return {"module": module, "tab": tab, "tabs": MODULE_TABS, "counts": _module_counts(module), "page_title": title or (module.title if module else "New module"),
            "crumbs": crumbs(("Modules", reverse("panel:modules")), (module.title if module else "New module", None))}


@admin_required
def module_edit(request, pk=None, tab="details"):
    module = get_object_or_404(Module.objects.select_related("plant", "department"), pk=pk) if pk else None
    if tab not in dict(MODULE_TABS) or (module is None and tab != "details"):
        raise Http404
    ctx = _module_ctx(module, tab)
    if tab == "details":
        initial = {}
        if module is None and request.GET.get("plant", "").isdigit():
            initial["plant"] = request.GET["plant"]
        form = ModuleForm(request.POST or None, request.FILES or None, instance=module, initial=initial)
        if request.method == "POST" and form.is_valid():
            obj = form.save()
            audit(request, "module.save", obj)
            messages.success(request, f"“{obj.title}” saved." + ("" if pk else " Now add the SOP steps."))
            return redirect("panel:module_tab", pk=obj.pk, tab="details" if pk else "steps")
        ctx.update(form=form, groups=[("Basics", ["title", "plant", "department", "process", "category", "library", "est_minutes", "instructor"]),
                                        ("Cover photo", ["cover"]), ("What learners read", ["summary", "overview", "objectives"]),
                                        ("Hindi (optional)", ["title_hi", "category_hi", "summary_hi", "overview_hi", "objectives_hi"]), ("Gujarati (optional)", ["title_gu", "category_gu", "summary_gu", "overview_gu", "objectives_gu"]),
                                        ("Publishing", ["status", "sop_document", "order", "slug"])])
        return render_panel(request, "panel/module_edit.html", **ctx)

    if tab == "quiz":
        return _module_quiz(request, module, ctx)

    eds = _module_editors(module, tab)
    return _editor_page(request, "panel/module_edit.html", eds, ctx, redirect_name="panel:module_tab", redirect_kwargs={"pk": module.pk, "tab": tab},
                        saved="Saved.", log=(f"module.{tab}", module))


def _module_editors(module, tab):
    hindi = dict(hindi=True)
    if tab == "images":
        return [Editor("gallery", ModuleImage, [F("image", "Photo", "image", required=True), F("caption", "Caption"), F("caption_hi", "Caption (Hindi)", **hindi)],
                       {"module": module}, title="Overview photos", noun="photo",
                       info="Shown as a gallery at the top of the module's Overview tab. The cover photo (Details tab) is used as the first image.",
                       empty_hint="No photos yet. Add equipment, process or safety photos — learners can tap to enlarge them.")]
    if tab == "steps":
        return [Editor("steps", SOPStep, [F("text", "What the learner must do", "textarea", required=True, rows=3), F("text_hi", "Hindi text", "textarea", rows=3, **hindi),
                                          F("image", "Photo (optional)", "image")],
                       {"module": module}, order_field=None, number_field="number", title="SOP steps", noun="step",
                       info="Steps are numbered automatically in the order shown. Use the arrows to reorder. To add many at once, use “Paste or import” above.",
                       empty_hint="No steps yet — add the first one, or paste a whole list above.")]
    if tab == "safety":
        sec = list(SafetyGuideline.Section.choices)
        fields = [F("section", "Group", "select", required=True, choices=sec), F("text", "Rule", "textarea", required=True, rows=2), F("text_hi", "Hindi text", "textarea", rows=2, **hindi)]
        return [Editor("safe_mod", SafetyGuideline, fields, {"module": module}, title="Rules for this module only", noun="rule",
                       info="Learners must tick “I agree” on these before the SOP steps unlock."),
                Editor("safe_plant", SafetyGuideline, fields, {"plant": module.plant, "module": None}, title=f"Rules for every module at {module.plant.name}", noun="rule",
                       info="Shown on all modules of this plant. Changing them here changes every module.")]
    if tab == "videos":
        return [Editor("videos", VideoLesson, [F("title", "Title", required=True), F("title_hi", "Title (Hindi)", hindi=True), F("file", "Video file (MP4)", "file"), F("url", "…or video link", "text", placeholder="https://"),
                                                F("duration_minutes", "Minutes", "number"), F("transcript", "Transcript (helps search & the AI assistant)", "textarea", rows=3)],
                       {"module": module}, title="Video lessons", noun="video", max_file_mb=500,
                       info="Upload an MP4, or paste a link if the video is hosted elsewhere. Large files are best uploaded to your video host and linked.",
                       empty_hint="No videos yet.")]
    return [Editor("problems", ProblemSolution, [F("problem", "Problem", "textarea", required=True, rows=2), F("problem_hi", "Problem (Hindi)", "textarea", rows=2, **hindi),
                                                 F("cause", "Likely cause", "textarea", rows=2), F("cause_hi", "Cause (Hindi)", "textarea", rows=2, **hindi),
                                                 F("solution", "Solution", "textarea", required=True, rows=3), F("solution_hi", "Solution (Hindi)", "textarea", rows=3, **hindi)],
                   {"module": module}, title="Problem – solution statements", noun="statement", empty_hint="No statements yet.")]


@admin_required
@require_POST
def module_status(request, pk):
    module = get_object_or_404(Module, pk=pk)
    module.status = Module.Status.DRAFT if module.status == Module.Status.PUBLISHED else Module.Status.PUBLISHED
    module.save(update_fields=["status"])
    audit(request, "module.status", module, status=module.status)
    messages.success(request, f"“{module.title}” is now {'visible to learners' if module.status == 'published' else 'a draft (hidden from learners)'}.")
    back = request.POST.get("next") or ""
    return redirect(back if back.startswith("/manage/") else reverse("panel:module_tab", kwargs={"pk": pk, "tab": "details"}))


@admin_required
def module_delete(request, pk):
    module = get_object_or_404(Module, pk=pk)
    if request.method == "POST":
        title = module.title
        audit(request, "module.delete", module, title=title)
        module.delete()
        messages.success(request, f"“{title}” deleted.")
        return redirect("panel:modules")
    started = ModuleProgress.objects.filter(module=module).count()
    return render_panel(request, "panel/confirm.html", page_title="Delete module", obj_name=module.title, back=reverse("panel:module_tab", kwargs={"pk": pk, "tab": "details"}),
                        warning=f"This permanently deletes the module with its {module.steps.count()} steps, quiz, photos, videos and discussion tags. "
                                f"{started} learner(s) have progress on it and {module.certificates.count()} certificate(s) were issued from it — those are deleted too.",
                        alt=("Hide it instead (move to draft)", reverse("panel:module_status", args=[pk])) if module.status == "published" else None)


@admin_required
@require_POST
def module_import(request, pk, kind):
    """Bulk add steps — from pasted lines or a CSV file."""
    module = get_object_or_404(Module, pk=pk)
    back = reverse("panel:module_tab", kwargs={"pk": pk, "tab": "steps" if kind == "steps" else "quiz"})
    replace = request.POST.get("mode") == "replace"
    try:
        if kind == "steps":
            pasted = (request.POST.get("paste") or "").strip()
            upload = request.FILES.get("csv")
            if upload:
                rows = read_table(upload)
            elif pasted:
                lines = [l.strip().lstrip("0123456789.)- ").strip() if l.strip()[:3].replace(".", "").replace(")", "").strip().isdigit() else l.strip() for l in pasted.splitlines()]
                rows = [{"text": l} for l in lines if l]
            else:
                raise ImportError_("Paste some steps (one per line) or choose a CSV file.")
            n = import_steps(module, rows, replace=replace)
            messages.success(request, f"{n} step(s) {'replaced' if replace else 'added'}.")
        else:
            upload = request.FILES.get("csv")
            if not upload:
                raise ImportError_("Choose a CSV file first.")
            Quiz.objects.get_or_create(module=module)
            n = import_quiz(module, read_table(upload), replace=replace)
            messages.success(request, f"{n} question(s) {'replaced' if replace else 'added'}.")
        audit(request, f"module.import_{kind}", module, count=n)
    except (ImportError_, TableError) as exc:
        messages.error(request, str(exc))
    except (UnicodeDecodeError, csv.Error):
        messages.error(request, "Couldn't read that file. Save it as “CSV UTF-8” from Excel and try again.")
    return redirect(back)


def _read_csv(upload):
    text = upload.read().decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


def sample_csv(request, kind):
    buf = io.StringIO()
    w = csv.writer(buf)
    if kind == "steps":
        w.writerow(["step", "text", "text_hi"])
        w.writerow([1, "Inspect the furnace internally after cleaning.", "सफ़ाई के बाद फ़र्नेस का आंतरिक निरीक्षण करें।"])
        w.writerow([2, "Check the cooling water flow.", ""])
    else:
        w.writerow(["question", "option_a", "option_b", "option_c", "option_d", "correct", "kind", "explanation", "question_hi", "option_a_hi", "option_b_hi", "option_c_hi", "option_d_hi"])
        w.writerow(["What should be checked first?", "Gas pressure", "Furnace interior", "Billet speed", "Water temperature", "B", "Diagnostic", "Always inspect before heating.", "", "", "", "", ""])
    resp = HttpResponse("﻿" + buf.getvalue(), content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="sample_{kind}.csv"'
    return resp


# ----------------------------------------------------------------------------- quiz
def _module_quiz(request, module, ctx):
    quiz = getattr(module, "quiz", None)
    if request.method == "POST":
        if quiz is None:
            quiz = Quiz.objects.create(module=module)
        form = QuizSettingsForm(request.POST, instance=quiz)
        if form.is_valid():
            form.save()
            audit(request, "quiz.settings", quiz)
            messages.success(request, "Quiz settings saved.")
            return redirect("panel:module_tab", pk=module.pk, tab="quiz")
    else:
        form = QuizSettingsForm(instance=quiz) if quiz else None
    questions = list(quiz.questions.annotate(n_choices=Count("choices")).order_by("order", "id")) if quiz else []
    ctx.update(quiz=quiz, form=form, questions=questions)
    return render_panel(request, "panel/module_quiz.html", **ctx)


@admin_required
def question_edit(request, pk, qid=None):
    module = get_object_or_404(Module, pk=pk)
    quiz, _ = Quiz.objects.get_or_create(module=module)
    question = get_object_or_404(Question, pk=qid, quiz=quiz) if qid else None
    form = QuestionForm(request.POST or None, instance=question)
    holder = question or Question(quiz=quiz, order=quiz.questions.count())
    choice_editor = Editor("choices", Choice, [F("text", "Answer option", required=True), F("text_hi", "Option (Hindi)", hindi=True), F("is_correct", "Correct answer", "radio")],
                           {"question": holder} if question else {"question": None}, title="Answer options", noun="option",
                           info="Add 2–6 options and mark exactly one as correct. Learners see them in a different order each attempt (unless you turned that off).")
    if question is None:
        choice_editor.filter = {"pk__in": []}
    ctx = _module_ctx(module, "quiz", "Edit question" if question else "New question")
    ctx["crumbs"] = crumbs(("Modules", reverse("panel:modules")), (module.title, reverse("panel:module_tab", kwargs={"pk": pk, "tab": "quiz"})), ("Question", None))
    parsed = None
    if request.method == "POST":
        rows, ok = choice_editor.parse(request.POST, request.FILES)
        parsed = rows
        correct = [r for r in rows if r["vals"].get("is_correct") == "1"]
        problem = None
        if ok and len(rows) < 2:
            problem = "Add at least two answer options."
        elif ok and len(correct) != 1:
            problem = "Mark exactly one option as the correct answer."
        if form.is_valid() and ok and not problem:
            with transaction.atomic():
                q = form.save(commit=False)
                if question is None:
                    q.quiz = quiz
                    q.order = quiz.questions.count()
                q.save()
                choice_editor.scope = {"question": q}
                choice_editor.filter = None
                choice_editor.apply(rows)
            audit(request, "quiz.question", q)
            messages.success(request, "Question saved.")
            return redirect("panel:module_tab", pk=pk, tab="quiz")
        messages.error(request, problem or "Please fix the highlighted items.")
    ctx.update(form=form, question=question, editors=[choice_editor.context(parsed)], quiz=quiz)
    return render_panel(request, "panel/question_edit.html", **ctx)


@admin_required
@require_POST
def question_action(request, pk, qid, action):
    module = get_object_or_404(Module, pk=pk)
    q = get_object_or_404(Question, pk=qid, quiz__module=module)
    if action == "delete":
        q.delete()
        messages.success(request, "Question deleted.")
    elif action in ("up", "down"):
        qs = list(module.quiz.questions.order_by("order", "id"))
        i = next(n for n, x in enumerate(qs) if x.pk == q.pk)
        j = i - 1 if action == "up" else i + 1
        if 0 <= j < len(qs):
            qs[i], qs[j] = qs[j], qs[i]
            for n, x in enumerate(qs):
                if x.order != n:
                    x.order = n
                    x.save(update_fields=["order"])
    return redirect("panel:module_tab", pk=pk, tab="quiz")


@admin_required
def quiz_list(request):
    qs = (Quiz.objects.select_related("module__plant").annotate(n_q=Count("questions", distinct=True), tries=Count("attempts", distinct=True),
                                                                 passed=Count("attempts", filter=Q(attempts__passed=True), distinct=True)).order_by("module__plant__name", "module__title"))
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(module__title__icontains=q)
    no_quiz = Module.objects.filter(quiz__isnull=True).select_related("plant").order_by("plant__name", "title")
    return render_panel(request, "panel/quiz_list.html", page_title="Quizzes", quizzes=qs, q=q, no_quiz=no_quiz[:30], no_quiz_count=no_quiz.count())
