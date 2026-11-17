import random

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.core.access import check_plant_access, require_plant
from apps.learning.models import Module
from apps.learning.services import get_progress, refresh_completion

from .models import Answer, Attempt, Choice, Quiz
from .rotation import build_attempt, ordered_choices


def _quiz_state(user, quiz):
    progress = get_progress(user, quiz.module, create=False)
    unlocked = (not quiz.requires_all_steps) or bool(progress and progress.all_steps_done)
    finished = quiz.attempts.filter(user=user, finished_at__isnull=False)
    used = finished.count()
    attempts_left = None if quiz.max_attempts is None else max(quiz.max_attempts - used, 0)
    best = max((a.score_percent or 0 for a in finished), default=None)
    return {"unlocked": unlocked, "progress": progress, "attempts_left": attempts_left,
            "best": best, "passed": finished.filter(passed=True).exists()}


@login_required
def quiz_list(request):
    plant = require_plant(request)
    quizzes = (Quiz.objects.filter(module__plant=plant, is_active=True,
                                   module__status=Module.Status.PUBLISHED)
               .select_related("module").order_by("module__order", "module__title"))
    from apps.learning.duties import required_flags
    _mods, qflags = required_flags(request.user, plant)
    rows = [{"quiz": q, "duty": qflags.get(q.module_id), **_quiz_state(request.user, q)} for q in quizzes.select_related("module__department")]
    # categories = the module's department (Production, QC, Maintenance …)
    cats = {}
    for r in rows:
        d = r["quiz"].module.department
        c = cats.setdefault(d.pk, {"dept": d, "key": str(d.pk), "rows": [], "passed": 0})
        c["rows"].append(r)
        c["passed"] += 1 if r["passed"] else 0
    cats = sorted(cats.values(), key=lambda c: (c["dept"].order, c["dept"].name))
    for c in cats:
        c["tone"] = {"production": "red", "qc": "blue", "maintenance": "amber"}.get(c["dept"].name.strip().lower(), "teal")
        c["count"] = len(c["rows"])
    chosen = request.GET.get("dept") or ""
    shown = [c for c in cats if c["key"] == chosen] or cats
    if not any(c["key"] == chosen for c in cats):
        chosen = ""
    return render(request, "quizzes/quiz_list.html", {"cats": cats, "groups": shown, "chosen": chosen, "total": len(rows), "rows": rows})


@login_required
@require_POST
def start(request, slug):
    quiz = get_object_or_404(Quiz, module__slug=slug, is_active=True)
    check_plant_access(request.user, quiz.module.plant)
    state = _quiz_state(request.user, quiz)
    if not state["unlocked"]:
        messages.error(request, _("Complete all SOP steps to unlock this quiz."))
        return redirect(f"{quiz.module.get_absolute_url()}?tab=sops")
    if state["attempts_left"] == 0:
        messages.error(request, _("No attempts left for this quiz."))
        return redirect(f"{quiz.module.get_absolute_url()}?tab=quiz")
    ids, choice_orders = build_attempt(quiz, request.user)
    if not ids:
        messages.error(request, _("This quiz has no questions yet."))
        return redirect(f"{quiz.module.get_absolute_url()}?tab=quiz")
    attempt = Attempt.objects.create(quiz=quiz, user=request.user, question_ids=ids, choice_orders=choice_orders)
    return redirect("quizzes:take", attempt.pk)


def _own_open_attempt(request, pk):
    attempt = get_object_or_404(Attempt.objects.select_related("quiz__module"),
                                pk=pk, user=request.user)
    return attempt


@login_required
def take(request, pk):
    attempt = _own_open_attempt(request, pk)
    if attempt.finished_at:
        return redirect("quizzes:result", attempt.pk)
    answered = set(attempt.answers.values_list("question_id", flat=True))
    remaining = [qid for qid in attempt.question_ids if qid not in answered]
    if not remaining:
        return _finish(attempt, request)
    quiz = attempt.quiz
    if quiz.time_limit_minutes:
        elapsed = (timezone.now() - attempt.started_at).total_seconds()
        if elapsed > quiz.time_limit_minutes * 60:
            messages.warning(request, _("Time is up."))
            return _finish(attempt, request)
    question = quiz.questions.prefetch_related("choices").get(pk=remaining[0])

    if request.method == "POST":
        choice = Choice.objects.filter(question=question, pk=request.POST.get("choice")).first()
        if choice is None:
            messages.error(request, _("Please choose an answer."))
        else:
            Answer.objects.get_or_create(attempt=attempt, question=question,
                                         defaults={"choice": choice,
                                                   "is_correct": choice.is_correct})
            return redirect("quizzes:take", attempt.pk)

    number = len(answered) + 1
    total = len(attempt.question_ids)
    return render(request, "quizzes/take.html", {
        "attempt": attempt, "quiz": quiz, "question": question,
        "choices": ordered_choices(attempt, question),
        "number": number, "total": total, "percent": round(100 * (number - 1) / total),
    })


@transaction.atomic
def _finish(attempt, request=None):
    total = len(attempt.question_ids)
    correct = attempt.answers.filter(is_correct=True).count()
    attempt.score_percent = round(100 * correct / total) if total else 0
    attempt.passed = attempt.score_percent >= attempt.quiz.pass_percent
    attempt.finished_at = timezone.now()
    attempt.save()
    if attempt.passed:
        refresh_completion(get_progress(attempt.user, attempt.quiz.module))
        if request is not None:
            request.session["celebrate"] = "quiz"
    return redirect("quizzes:result", attempt.pk)


@login_required
def result(request, pk):
    attempt = _own_open_attempt(request, pk)
    if not attempt.finished_at:
        return redirect("quizzes:take", attempt.pk)
    answers = attempt.answers.select_related("question", "choice")
    correct_choices = {c.question_id: c for c in
                       Choice.objects.filter(question_id__in=attempt.question_ids, is_correct=True)}
    review = [{"answer": a, "correct": correct_choices.get(a.question_id)} for a in answers]
    cert = attempt.user.certificates.filter(module=attempt.quiz.module).first()
    celebrate = None
    if request.session.get("celebrate") == "quiz" and attempt.passed:
        request.session.pop("celebrate", None)
        celebrate = {"kind": "quiz", "title": _("You passed!"),
                     "text": _("Your certificate is ready to download."),
                     "cta_label": _("View certificate") if cert else "",
                     "cta_url": cert.get_absolute_url() if cert else ""}
    return render(request, "quizzes/result.html", {"celebrate": celebrate,
        "attempt": attempt, "quiz": attempt.quiz, "review": review,
        "correct_count": sum(1 for a in answers if a.is_correct),
        "certificate": cert, "state": _quiz_state(request.user, attempt.quiz),
    })
