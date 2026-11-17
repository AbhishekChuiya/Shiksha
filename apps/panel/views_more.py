import csv
import io
from datetime import timedelta

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from apps.accounts.forms import AnyPasswordResetForm
from django.db.models import Avg, Count, Max, Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.certificates.models import Certificate
from apps.core.models import AuditLog
from apps.incidents.models import Incident
from apps.learning.models import DiscussionPost, Module, ModuleProgress
from apps.plants.models import Plant
from apps.quizzes.models import Attempt
from apps.sops.models import SOPDocument, SOPVersion

from .decorators import admin_required
from .editor import Editor, F
from .forms import SOPForm, UserForm
from .views import _editor_page, audit, crumbs, paginate, qurl, render_panel


# ----------------------------------------------------------------------------- SOP library
@admin_required
def sop_list(request):
    q = (request.GET.get("q") or "").strip()
    plant, issue = request.GET.get("plant") or "", request.GET.get("issue") or ""
    qs = SOPDocument.objects.select_related("plant", "department").annotate(n_versions=Count("versions")).order_by("plant__name", "code")
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(code__icontains=q) | Q(tags__icontains=q))
    if plant.isdigit():
        qs = qs.filter(plant_id=plant)
    if issue == "unapproved":
        qs = qs.exclude(versions__status="approved")
    page = paginate(request, qs)
    return render_panel(request, "panel/sop_list.html", page_title="SOP library", page=page, q=q, plant=plant, issue=issue, plants=Plant.objects.all(), total=page.paginator.count)


@admin_required
def sop_edit(request, pk=None):
    sop = get_object_or_404(SOPDocument.objects.select_related("plant"), pk=pk) if pk else None
    form = SOPForm(request.POST or None, instance=sop, initial={"plant": request.GET.get("plant")} if not sop and request.GET.get("plant") else None)
    ctx = {"sop": sop, "form": form, "page_title": sop.code if sop else "New SOP",
           "crumbs": crumbs(("SOP library", reverse("panel:sops")), (sop.code if sop else "New SOP", None)),
           "groups": [("Document", ["code", "title", "plant", "department", "process", "category", "tags", "owner", "language", "allow_download"]), ("Hindi (optional)", ["title_hi"]), ("Gujarati (optional)", ["title_gu"])]}
    if sop is None:
        if request.method == "POST" and form.is_valid():
            obj = form.save()
            audit(request, "sop.save", obj)
            messages.success(request, "SOP created. Now upload its first version below.")
            return redirect("panel:sop_edit", pk=obj.pk)
        return render_panel(request, "panel/sop_edit.html", **ctx)

    def stamp(obj, row):
        if not obj.uploaded_by_id:
            obj.uploaded_by = request.user

    versions = Editor("versions", SOPVersion,
                      [F("version", "Version", required=True, placeholder="01", width="half"), F("effective_date", "Effective date", "date", required=True, width="half"),
                       F("status", "Status", "select", required=True, choices=SOPVersion.Status.choices),
                       F("file", "Document file (PDF / Word / Excel)", "file"), F("change_summary", "What changed", "textarea", rows=2),
                       F("approved_by", "Approved by"), F("content", "Text for search & read-aloud (optional)", "textarea", rows=4)],
                      {"sop": sop}, order_field=None, ordering=("-effective_date", "-id"), pre_save=stamp, title="Versions", noun="version", add_label="Add new version",
                      info="Only ONE version is active for learners: the newest with status “Approved”. Approving a version automatically marks the older approved one as Superseded.",
                      empty_hint="No versions yet — add the first one.")
    if request.method == "POST" and request.POST.get("form") == "details":
        if form.is_valid():
            form.save()
            audit(request, "sop.save", sop)
            messages.success(request, "SOP details saved.")
            return redirect("panel:sop_edit", pk=sop.pk)
        messages.error(request, "Please fix the highlighted items.")
        ctx["editors"] = [versions.context()]
        return render_panel(request, "panel/sop_edit.html", **ctx)
    old = {v.pk: v.status for v in sop.versions.all()}

    def validate(parsed):
        versions_ = [r["vals"]["version"] for r in parsed["versions"]]
        if len(versions_) != len(set(versions_)):
            return "Two versions have the same version number."
        return None

    if request.method == "POST":
        response = _editor_page(request, "panel/sop_edit.html", [versions], ctx, redirect_name="panel:sop_edit", redirect_kwargs={"pk": sop.pk},
                                saved="Versions saved.", log=("sop.versions", sop), extra_validate=validate)
        for v in sop.versions.all():
            if old.get(v.pk) != v.status:
                AuditLog.record(request.user, "sop.version_status", v, sop=sop.code, version=v.version, old=old.get(v.pk), new=v.status)
        return response
    ctx["editors"] = [versions.context()]
    return render_panel(request, "panel/sop_edit.html", **ctx)


@admin_required
def sop_delete(request, pk):
    sop = get_object_or_404(SOPDocument, pk=pk)
    if request.method == "POST":
        audit(request, "sop.delete", sop, code=sop.code)
        sop.delete()
        messages.success(request, f"{sop.code} deleted.")
        return redirect("panel:sops")
    return render_panel(request, "panel/confirm.html", page_title="Delete SOP", obj_name=f"{sop.code} — {sop.title}", back=reverse("panel:sop_edit", args=[pk]),
                        warning=f"This permanently deletes the SOP and all {sop.versions.count()} version(s) including uploaded files. Modules linked to it keep working but lose the link.")


# ----------------------------------------------------------------------------- users
@admin_required
def user_list(request):
    q = (request.GET.get("q") or "").strip()
    role, active, plant = request.GET.get("role") or "", request.GET.get("active") or "", request.GET.get("plant") or ""
    qs = User.objects.annotate(n_certs=Count("certificates", distinct=True)).order_by("first_name", "last_name", "email")
    if q:
        qs = qs.filter(Q(email__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(employee_id__icontains=q))
    if role in ("learner", "admin"):
        qs = qs.filter(role=role)
    if active in ("1", "0"):
        qs = qs.filter(is_active=active == "1")
    if plant.isdigit():
        qs = qs.filter(plants__id=plant)
    page = paginate(request, qs.distinct())
    return render_panel(request, "panel/user_list.html", page_title="Users", page=page, q=q, role=role, active=active, plant=plant, plants=Plant.objects.all(), total=page.paginator.count)


def _guard_superuser(request, target):
    """Only a superuser may touch another superuser's account (role, password, access)."""
    if target is not None and target.is_superuser and not request.user.is_superuser:
        raise PermissionDenied("Only a superuser can change a superuser account.")


@admin_required
def user_edit(request, pk=None):
    user = get_object_or_404(User, pk=pk) if pk else None
    _guard_superuser(request, user)
    form = UserForm(request.POST or None, instance=user, acting_user=request.user)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        pw = form.cleaned_data.get("new_password")
        creating = obj.pk is None
        if pw:
            obj.set_password(pw)
        elif creating:
            obj.set_unusable_password()
        obj.save()
        form.save_m2m()
        audit(request, "user.save", obj, created=creating)
        if creating and not pw:
            sent = _send_reset(request, obj)
            messages.success(request, f"{obj.email} created." + (" A link to choose a password was emailed to them." if sent else " Email could not be sent — use “Send password link” on their page."))
        else:
            messages.success(request, f"{obj.get_full_name() or obj.email} saved.")
        return redirect("panel:user_edit", pk=obj.pk)
    ctx = {"u": user, "form": form, "page_title": (user.get_full_name() or user.email) if user else "New user",
           "crumbs": crumbs(("Users", reverse("panel:users")), ((user.get_full_name() or user.email) if user else "New user", None)),
           "groups": [("Who they are", ["first_name", "last_name", "email", "employee_id", "designation"]), ("Access", ["role", "is_active", "plants", "default_plant", "department"]),
                      ("Password", ["new_password"])]}
    return render_panel(request, "panel/user_edit.html", **ctx)


def _send_reset(request, user):
    try:
        form = AnyPasswordResetForm({"email": user.email})
        if form.is_valid():
            form.save(request=request, use_https=request.is_secure(), email_template_name="accounts/emails/password_reset.txt",
                      html_email_template_name="accounts/emails/password_reset.html", subject_template_name="accounts/emails/password_reset_subject.txt")
        return True
    except Exception:
        return False


@admin_required
@require_POST
def user_reset(request, pk):
    user = get_object_or_404(User, pk=pk)
    _guard_superuser(request, user)
    ok = _send_reset(request, user)
    audit(request, "user.reset_link", user)
    messages.success(request, f"Password link emailed to {user.email}.") if ok else messages.error(request, "Email could not be sent. Check the email settings.")
    return redirect("panel:user_edit", pk=pk)


@admin_required
def user_import(request):
    if request.method == "POST":
        upload = request.FILES.get("csv")
        if not upload:
            messages.error(request, "Choose a CSV file first.")
            return redirect("panel:user_import")
        try:
            text = upload.read().decode("utf-8-sig")
            rows = list(csv.DictReader(io.StringIO(text)))
        except (UnicodeDecodeError, csv.Error):
            messages.error(request, "Couldn't read that file. Save it as “CSV UTF-8”.")
            return redirect("panel:user_import")
        from django.conf import settings
        domains = settings.ALLOWED_EMAIL_DOMAINS
        created, skipped = 0, []
        for i, r in enumerate(rows, start=2):
            email = (r.get("email") or "").strip().lower()
            if not email:
                continue
            if domains and email.rsplit("@", 1)[-1] not in domains:
                skipped.append(f"line {i}: {email} (not a company address)")
                continue
            if User.objects.filter(email__iexact=email).exists():
                skipped.append(f"line {i}: {email} (already exists)")
                continue
            eid = (r.get("employee_id") or "").strip() or None
            if eid and User.objects.filter(employee_id__iexact=eid).exists():
                eid = None
            role = "admin" if (r.get("role") or "").strip().lower() == "admin" else "learner"
            u = User(email=email, first_name=(r.get("first_name") or "").strip(), last_name=(r.get("last_name") or "").strip(), employee_id=eid,
                     designation=(r.get("designation") or "").strip(), role=role)
            u.set_unusable_password()
            u.save()
            created += 1
        audit(request, "user.import", request.user, created=created, skipped=len(skipped))
        messages.success(request, f"{created} user(s) created. They can sign in with Microsoft, or use “Forgot password” to set one.")
        request.session["import_skipped"] = skipped[:50]
        return redirect("panel:user_import")
    return render_panel(request, "panel/user_import.html", page_title="Import users", skipped=request.session.pop("import_skipped", []),
                        crumbs=crumbs(("Users", reverse("panel:users")), ("Import", None)))


def sample_users_csv(request):
    resp = HttpResponse("﻿email,first_name,last_name,employee_id,designation,role\nrahul.sharma@vishakha.com,Rahul,Sharma,90001234,Production Operator,learner\n", content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = 'attachment; filename="sample_users.csv"'
    return resp


# ----------------------------------------------------------------------------- discussion moderation
@admin_required
def discussion_list(request):
    q = (request.GET.get("q") or "").strip()
    show = request.GET.get("show") or ""
    qs = DiscussionPost.objects.select_related("author", "module", "plant", "parent__author").order_by("-created_at")
    plant = request.GET.get("plant") or ""
    if plant.isdigit():
        qs = qs.filter(plant_id=plant)
    if q:
        qs = qs.filter(Q(body__icontains=q) | Q(author__email__icontains=q) | Q(author__first_name__icontains=q))
    if show == "hidden":
        qs = qs.filter(is_hidden=True)
    elif show == "pinned":
        qs = qs.filter(is_pinned=True)
    elif show == "posts":
        qs = qs.filter(parent__isnull=True)
    page = paginate(request, qs)
    return render_panel(request, "panel/discussion_list.html", page_title="Discussion", page=page, q=q, show=show, plant=plant, plants=Plant.objects.all(), total=page.paginator.count, base=qurl(request))


# ----------------------------------------------------------------------------- incidents
@admin_required
def incident_list(request):
    q = (request.GET.get("q") or "").strip()
    status, plant, cat = request.GET.get("status") or "", request.GET.get("plant") or "", request.GET.get("category") or ""
    qs = Incident.objects.select_related("plant", "reported_by", "department").order_by("-created_at")
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q) | Q(reported_by__email__icontains=q))
    if status in dict(Incident.Status.choices):
        qs = qs.filter(status=status)
    if plant.isdigit():
        qs = qs.filter(plant_id=plant)
    if cat in dict(Incident.Category.choices):
        qs = qs.filter(category=cat)
    counts = {s: Incident.objects.filter(status=s).count() for s, _ in Incident.Status.choices}
    page = paginate(request, qs)
    return render_panel(request, "panel/incident_list.html", page_title="Incidents", page=page, q=q, status=status, plant=plant, category=cat, plants=Plant.objects.all(),
                        statuses=Incident.Status.choices, categories=Incident.Category.choices, counts=counts, total=page.paginator.count, base=qurl(request))


@admin_required
@require_POST
def incident_status(request, pk):
    inc = get_object_or_404(Incident, pk=pk)
    new = request.POST.get("status")
    if new in dict(Incident.Status.choices):
        old = inc.status
        inc.status = new
        if request.POST.get("closure_notes"):
            inc.closure_notes = request.POST["closure_notes"].strip()
        inc.save()
        AuditLog.record(request.user, "incident.status", inc, old=old, new=new)
        messages.success(request, f"Incident #{inc.pk} → {inc.get_status_display()}.")
    back = request.POST.get("next") or ""
    return redirect(back if back.startswith("/manage/") else reverse("panel:incidents"))


# ----------------------------------------------------------------------------- certificates
@admin_required
def certificate_list(request):
    q = (request.GET.get("q") or "").strip()
    qs = Certificate.objects.select_related("user", "module__plant").order_by("-issued_at")
    if q:
        qs = qs.filter(Q(user__first_name__icontains=q) | Q(user__last_name__icontains=q) | Q(user__email__icontains=q) | Q(module__title__icontains=q))
    page = paginate(request, qs)
    return render_panel(request, "panel/certificate_list.html", page_title="Certificates", page=page, q=q, total=page.paginator.count)


@admin_required
@require_POST
def certificate_revoke(request, pk):
    cert = get_object_or_404(Certificate, pk=pk)
    audit(request, "certificate.revoke", cert, user=cert.user.email, module=cert.module.title)
    messages.success(request, f"Certificate for {cert.holder_name} ({cert.module.title}) revoked. It is reissued only if they pass the quiz again.")
    cert.delete()
    return redirect("panel:certificates")


# ----------------------------------------------------------------------------- reports
def _module_report(plant=None):
    mods = Module.objects.select_related("plant", "department").filter(status="published")
    if plant:
        mods = mods.filter(plant_id=plant)
    rows = []
    for m in mods.order_by("plant__name", "department__name", "title"):
        prog = ModuleProgress.objects.filter(module=m)
        started, done = prog.count(), prog.filter(completed_at__isnull=False).count()
        att = Attempt.objects.filter(quiz__module=m, finished_at__isnull=False)
        n = att.count()
        rows.append({"module": m, "started": started, "completed": done, "rate": round(100 * done / started) if started else None,
                     "attempts": n, "avg": round(att.aggregate(a=Avg("score_percent"))["a"] or 0) if n else None,
                     "pass_rate": round(100 * att.filter(passed=True).count() / n) if n else None,
                     "hours": round((prog.aggregate(s=Sum("seconds_spent"))["s"] or 0) / 3600, 1)})
    return rows


def _learner_report(plant=None):
    users = User.objects.filter(is_active=True, role="learner")
    if plant:
        users = users.filter(Q(plants__id=plant) | Q(plants__isnull=True)).distinct()
    out = []
    for u in users.order_by("first_name", "email"):
        prog = ModuleProgress.objects.filter(user=u)
        att = Attempt.objects.filter(user=u, finished_at__isnull=False)
        best = [a["m"] for a in att.values("quiz").annotate(m=Max("score_percent"))]
        out.append({"user": u, "started": prog.count(), "completed": prog.filter(completed_at__isnull=False).count(),
                    "hours": round((prog.aggregate(s=Sum("seconds_spent"))["s"] or 0) / 3600, 1), "avg_best": round(sum(best) / len(best)) if best else None,
                    "certs": u.certificates.count(), "last": prog.aggregate(m=Max("last_seen_at"))["m"]})
    return out


@admin_required
def reports(request):
    plant = request.GET.get("plant") or ""
    plant = plant if plant.isdigit() else ""
    modules = _module_report(plant)
    learners = _learner_report(plant)
    return render_panel(request, "panel/reports.html", page_title="Reports", plant=plant, plants=Plant.objects.all(), modules=modules, learners=learners[:200], learner_total=len(learners),
                        totals={"started": sum(r["started"] for r in modules), "completed": sum(r["completed"] for r in modules),
                                "hours": round(sum(r["hours"] for r in modules), 1), "certs": Certificate.objects.count()})


@admin_required
def report_export(request, kind):
    plant = request.GET.get("plant") or ""
    plant = plant if plant.isdigit() else ""
    buf = io.StringIO()
    w = csv.writer(buf)
    if kind == "modules":
        w.writerow(["Plant", "Department", "Module", "Learners started", "Completed", "Completion %", "Quiz attempts", "Average score %", "Pass rate %", "Learning hours"])
        for r in _module_report(plant):
            m = r["module"]
            w.writerow([m.plant.name, m.department.name, m.title, r["started"], r["completed"], r["rate"] if r["rate"] is not None else "", r["attempts"],
                        r["avg"] if r["avg"] is not None else "", r["pass_rate"] if r["pass_rate"] is not None else "", r["hours"]])
    elif kind == "learners":
        w.writerow(["Name", "Email", "Employee ID", "Designation", "Modules started", "Modules completed", "Learning hours", "Average best score %", "Certificates", "Last active"])
        for r in _learner_report(plant):
            u = r["user"]
            w.writerow([u.get_full_name(), u.email, u.employee_id or "", u.designation, r["started"], r["completed"], r["hours"], r["avg_best"] if r["avg_best"] is not None else "",
                        r["certs"], timezone.localtime(r["last"]).strftime("%Y-%m-%d %H:%M") if r["last"] else ""])
    else:
        raise Http404
    resp = HttpResponse("﻿" + buf.getvalue(), content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="shiksha_{kind}_{timezone.localdate()}.csv"'
    return resp


# ----------------------------------------------------------------------------- help
@admin_required
def announce(request):
    """Send a message to every learner's notification bell (everyone, or the people of one plant)."""
    from apps.core.models import Notification
    plants = Plant.objects.filter(is_active=True).order_by("order", "name")
    if request.method == "POST":
        title, body, link = (request.POST.get(k, "").strip() for k in ("title", "body", "url"))
        audience = request.POST.get("audience", "all")
        if not title:
            messages.error(request, "Write a short title for the message.")
        elif link and not link.startswith("/"):
            messages.error(request, "A link must start with / — for example /modules/ — or be left empty.")
        else:
            users = User.objects.filter(is_active=True)
            if audience.isdigit():
                plant = get_object_or_404(Plant, pk=audience)
                users = users.filter(Q(plants__isnull=True) | Q(plants=plant)).distinct()
            Notification.objects.bulk_create([Notification(user=u, kind=Notification.Kind.ANNOUNCEMENT, title=title[:160], body=body, url=link[:300]) for u in users])
            audit(request, "announcement.send", None, count=users.count(), title=title)
            messages.success(request, f"Sent to {users.count()} people. They will see it in their notification bell.")
            return redirect("panel:announce")
    sent = (Notification.objects.filter(kind=Notification.Kind.ANNOUNCEMENT).values("title", "created_at__date").annotate(n=Count("id")).order_by("-created_at__date")[:8])
    return render_panel(request, "panel/announce.html", page_title="Send a notification", plants=plants, sent=sent)


@admin_required
def help_page(request):
    return render_panel(request, "panel/help.html", page_title="How to use this panel")


from django.http import Http404  # noqa: E402  (used by report_export)
