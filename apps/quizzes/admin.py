from django.contrib import admin

from .models import Attempt, Choice, Question, Quiz


class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 4
    max_num = 6


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ["text", "quiz", "kind", "order"]
    list_filter = ["quiz__module__plant", "quiz"]
    inlines = [ChoiceInline]


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 0
    fields = ["order", "kind", "text"]
    show_change_link = True


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ["__str__", "pass_percent", "question_total", "max_attempts", "is_active"]
    list_filter = ["module__plant", "is_active"]
    autocomplete_fields = ["module"]
    inlines = [QuestionInline]

    @admin.display(description="Questions")
    def question_total(self, obj):
        return obj.questions.count()


@admin.register(Attempt)
class AttemptAdmin(admin.ModelAdmin):
    list_display = ["user", "quiz", "score_percent", "passed", "started_at", "finished_at"]
    list_filter = ["passed", "quiz__module__plant", "quiz"]
    search_fields = ["user__email", "user__first_name"]
    date_hierarchy = "started_at"
