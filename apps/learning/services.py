from django.utils import timezone

from .models import ModuleProgress


def get_progress(user, module, create=True):
    if create:
        return ModuleProgress.objects.get_or_create(user=user, module=module)[0]
    return ModuleProgress.objects.filter(user=user, module=module).first()


def refresh_completion(progress):
    """Mark a module complete when all steps are viewed and the quiz (if any) is passed.

    Issues the certificate at the same moment. Safe to call repeatedly.
    """
    from apps.certificates.models import Certificate
    from apps.quizzes.models import Attempt

    module = progress.module
    if not progress.all_steps_done:
        return False
    quiz = getattr(module, "quiz", None)
    best = None
    if quiz is not None and quiz.is_active and quiz.questions.exists():
        best = (Attempt.objects.filter(quiz=quiz, user=progress.user, passed=True)
                .order_by("-score_percent").first())
        if best is None:
            return False
    if progress.completed_at is None:
        progress.completed_at = timezone.now()
        progress.save(update_fields=["completed_at"])
    cert, created = Certificate.objects.get_or_create(
        user=progress.user, module=module,
        defaults={"attempt": best, "score_percent": best.score_percent if best else None})
    if created:
        from apps.core.notify import certificate_issued
        certificate_issued(cert)
    return True
