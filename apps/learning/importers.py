"""Bulk import of SOP steps and quiz questions from CSV rows (used by the admin panel and the manage.py commands)."""
from django.db import transaction

from apps.quizzes.models import Choice, Question, Quiz

from .models import SOPStep


class ImportError_(ValueError):
    """Message is safe to show to the admin."""


@transaction.atomic
def import_steps(module, rows, replace=True):
    rows = [r for r in rows if (r.get("text") or "").strip()]
    if not rows:
        raise ImportError_("No steps found. The file needs a header row with: step, text (and optionally text_hi).")
    start = 0
    if replace:
        module.steps.all().delete()
    else:
        start = module.steps.count()
    for i, r in enumerate(rows, start=1):
        SOPStep.objects.create(module=module, number=start + i, text=r["text"].strip(), text_hi=(r.get("text_hi") or "").strip())
    return len(rows)


@transaction.atomic
def import_quiz(module, rows, pass_percent=None, replace=True):
    quiz, _ = Quiz.objects.get_or_create(module=module)
    if pass_percent is not None:
        quiz.pass_percent = pass_percent
        quiz.save()
    rows = [r for r in rows if (r.get("question") or "").strip()]
    if not rows:
        raise ImportError_("No questions found. The file needs a header row with: question, option_a, option_b, option_c, option_d, correct.")
    if replace:
        quiz.questions.all().delete()
    base = quiz.questions.count()
    for i, r in enumerate(rows):
        letters = [k for k in "abcdef" if (r.get(f"option_{k}") or "").strip()]
        correct = (r.get("correct") or "").strip().lower()
        if len(letters) < 2:
            raise ImportError_(f"Row {i + 2}: a question needs at least two options.")
        if correct not in letters:
            raise ImportError_(f"Row {i + 2}: 'correct' must be one of {', '.join(x.upper() for x in letters)}.")
        q = Question.objects.create(quiz=quiz, order=base + i, text=r["question"].strip(), text_hi=(r.get("question_hi") or "").strip(),
                                    kind=(r.get("kind") or "Diagnostic").strip(), explanation=(r.get("explanation") or "").strip())
        for j, k in enumerate(letters):
            Choice.objects.create(question=q, order=j, text=r[f"option_{k}"].strip(), text_hi=(r.get(f"option_{k}_hi") or "").strip(), is_correct=(k == correct))
    return len(rows)
