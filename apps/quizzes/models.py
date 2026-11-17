from django.conf import settings
from django.db import models

from django.utils.translation import gettext as _

from apps.core.i18n import localized


class Quiz(models.Model):
    module = models.OneToOneField("learning.Module", on_delete=models.CASCADE, related_name="quiz")
    title = models.CharField(max_length=160, blank=True)
    pass_percent = models.PositiveSmallIntegerField(default=80)
    time_limit_minutes = models.PositiveSmallIntegerField(null=True, blank=True)
    max_attempts = models.PositiveSmallIntegerField(null=True, blank=True,
                                                    help_text="Blank = unlimited")
    questions_per_attempt = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="Random subset per attempt; blank = all")
    requires_all_steps = models.BooleanField(default=True,
                                             help_text="Lock quiz until all SOP steps are viewed")
    shuffle_questions = models.BooleanField(default=True, help_text="New question order on every attempt")
    shuffle_choices = models.BooleanField(default=True, help_text="New answer-option order on every attempt")
    is_active = models.BooleanField(default=True)
    is_mandatory = models.BooleanField("required", default=False, help_text="Every learner must pass this quiz")
    due_date = models.DateField(null=True, blank=True, help_text="Last day to pass a required quiz")

    class Meta:
        verbose_name_plural = "quizzes"

    def __str__(self):
        return self.display_title

    @property
    def display_title(self):
        return self.title or _("%(m)s — SOP Quiz") % {"m": self.module.display_title}

    @property
    def question_count(self):
        n = self.questions.count()
        return min(n, self.questions_per_attempt) if self.questions_per_attempt else n


class Question(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="questions")
    kind = models.CharField(max_length=40, default="Diagnostic",
                            help_text="Label shown above the question")
    text = models.TextField()
    text_hi = models.TextField("text (Hindi)", blank=True)
    text_gu = models.TextField("text (Gujarati)", blank=True)
    keep_choice_order = models.BooleanField(default=False, help_text='Never shuffle this question\'s options (e.g. "All of the above")')
    explanation = models.TextField(blank=True, help_text="Shown after answering")
    explanation_hi = models.TextField("explanation (Hindi)", blank=True)
    explanation_gu = models.TextField("explanation (Gujarati)", blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.text[:80]

    @property
    def display_text(self):
        return localized(self, "text")

    @property
    def display_explanation(self):
        return localized(self, "explanation")


class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="choices")
    text = models.CharField(max_length=300)
    text_hi = models.CharField("text (Hindi)", max_length=300, blank=True)
    text_gu = models.CharField("text (Gujarati)", max_length=300, blank=True)
    is_correct = models.BooleanField(default=False)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.text

    @property
    def display_text(self):
        return localized(self, "text")


class Attempt(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="attempts")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="quiz_attempts")
    question_ids = models.JSONField(default=list)
    choice_orders = models.JSONField(default=dict, blank=True)   # {"<question id>": [choice ids in shown order]}
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    score_percent = models.PositiveSmallIntegerField(null=True, blank=True)
    passed = models.BooleanField(default=False)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.user} — {self.quiz} ({self.score_percent}%)"


class Answer(models.Model):
    attempt = models.ForeignKey(Attempt, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    choice = models.ForeignKey(Choice, on_delete=models.CASCADE)
    is_correct = models.BooleanField()

    class Meta:
        unique_together = [("attempt", "question")]
