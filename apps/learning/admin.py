from django.contrib import admin

from .models import (DiscussionPost, Module, ModuleProgress, ProblemSolution, SafetyGuideline,
                     SOPStep, VideoLesson)


class StepInline(admin.StackedInline):
    model = SOPStep
    extra = 0
    fields = [("number", "image"), "text", "text_hi"]


class VideoInline(admin.TabularInline):
    model = VideoLesson
    extra = 0
    fields = ["order", "title", "file", "url", "duration_minutes"]


class ProblemInline(admin.StackedInline):
    model = ProblemSolution
    extra = 0


class GuidelineInline(admin.TabularInline):
    model = SafetyGuideline
    fk_name = "module"
    extra = 0
    fields = ["section", "order", "text", "text_hi"]


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ["title", "plant", "department", "category", "library", "step_count",
                    "status", "order"]
    list_filter = ["plant", "department", "library", "status", "category"]
    list_editable = ["status", "order"]
    search_fields = ["title", "slug", "summary"]
    prepopulated_fields = {"slug": ["title"]}
    autocomplete_fields = ["process", "sop_document"]
    inlines = [GuidelineInline, StepInline, VideoInline, ProblemInline]
    fieldsets = (
        (None, {"fields": ("title", "slug", "status", "order")}),
        ("Placement", {"fields": ("plant", "department", "process", "category", "library",
                                  "sop_document")}),
        ("Content", {"fields": ("cover", "summary", "overview", "objectives",
                                "est_minutes", "instructor")}),
        ("Hindi", {"classes": ("collapse",),
                   "fields": ("title_hi", "summary_hi", "overview_hi", "objectives_hi")}),
    )

    @admin.display(description="Steps")
    def step_count(self, obj):
        return obj.steps.count()


@admin.register(SafetyGuideline)
class SafetyGuidelineAdmin(admin.ModelAdmin):
    list_display = ["__str__", "section", "plant", "module", "order"]
    list_filter = ["section", "plant"]


@admin.register(ModuleProgress)
class ModuleProgressAdmin(admin.ModelAdmin):
    list_display = ["user", "module", "steps_done", "seconds_spent", "safety_ack_at",
                    "completed_at", "last_seen_at"]
    list_filter = ["module__plant", "module"]
    search_fields = ["user__email", "user__first_name", "module__title"]
    readonly_fields = ["completed_steps"]


@admin.register(DiscussionPost)
class DiscussionPostAdmin(admin.ModelAdmin):
    list_display = ["module", "author", "created_at", "is_hidden"]
    list_editable = ["is_hidden"]
    list_filter = ["is_hidden", "module__plant"]
