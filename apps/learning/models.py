from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _


from apps.core.i18n import has_hindi, localized  # noqa: F401  (re-exported for other apps)


class Module(models.Model):
    class Library(models.TextChoices):
        PRODUCTION = "production", "Production SOPs"
        DEPARTMENT = "department", "Department SOPs"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    slug = models.SlugField(max_length=80, unique=True, help_text="e.g. vmpl_melt_cast")
    plant = models.ForeignKey("plants.Plant", on_delete=models.CASCADE, related_name="modules")
    department = models.ForeignKey("plants.Department", on_delete=models.PROTECT,
                                   related_name="modules")
    process = models.ForeignKey("plants.Process", null=True, blank=True,
                                on_delete=models.SET_NULL, related_name="modules")
    category = models.CharField(max_length=80, blank=True,
                                help_text="Filter chip, e.g. Melt & Cast, Extrusion")
    category_hi = models.CharField("category (Hindi)", max_length=80, blank=True)
    category_gu = models.CharField("category (Gujarati)", max_length=80, blank=True)
    library = models.CharField(max_length=20, choices=Library.choices,
                               default=Library.PRODUCTION)
    title = models.CharField(max_length=160)
    title_hi = models.CharField("title (Hindi)", max_length=160, blank=True)
    title_gu = models.CharField("title (Gujarati)", max_length=160, blank=True)
    summary = models.CharField(max_length=300, blank=True)
    summary_hi = models.CharField("summary (Hindi)", max_length=300, blank=True)
    summary_gu = models.CharField("summary (Gujarati)", max_length=300, blank=True)
    overview = models.TextField(blank=True)
    overview_hi = models.TextField("overview (Hindi)", blank=True)
    overview_gu = models.TextField("overview (Gujarati)", blank=True)
    objectives = models.TextField(blank=True, help_text="One learning objective per line")
    objectives_hi = models.TextField("objectives (Hindi)", blank=True)
    objectives_gu = models.TextField("objectives (Gujarati)", blank=True)
    cover = models.ImageField(upload_to="modules/covers/", blank=True)
    est_minutes = models.PositiveSmallIntegerField("estimated time (min)", default=20)
    instructor = models.CharField(max_length=120, blank=True)
    sop_document = models.ForeignKey("sops.SOPDocument", null=True, blank=True,
                                     on_delete=models.SET_NULL, related_name="modules",
                                     help_text="Approved SOP this module teaches")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PUBLISHED)
    order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["plant", "order", "title"]

    def __str__(self):
        return f"{self.title} ({self.plant.name})"

    def get_absolute_url(self):
        return reverse("learning:module_detail", args=[self.slug])

    @property
    def display_title(self):
        return localized(self, "title")

    @property
    def display_category(self):
        return localized(self, "category")

    @property
    def display_summary(self):
        return localized(self, "summary")

    @property
    def display_overview(self):
        return localized(self, "overview")

    @property
    def objective_list(self):
        return [o.strip() for o in localized(self, "objectives").splitlines() if o.strip()]

    def safety_guidelines(self):
        return SafetyGuideline.objects.filter(
            models.Q(module=self) | models.Q(module__isnull=True, plant=self.plant)
            | models.Q(module__isnull=True, plant__isnull=True)
        )


class SafetyGuideline(models.Model):
    """Shown before SOP steps; learner must agree before steps unlock.

    Leave `module` empty to apply to every module of `plant`; leave both
    empty to apply everywhere.
    """

    class Section(models.TextChoices):
        PPE = "ppe", "PPE required"
        HAZARDS = "hazards", "Hazards — high-risk areas"
        PRACTICES = "practices", "Safe operating practices"
        DOS = "dos", "Do's"
        DONTS = "donts", "Don'ts"
        SAFETY = "safety", "Safety (general)"
        ENVIRONMENT = "environment", "Environment, Quality & Discipline"

    plant = models.ForeignKey("plants.Plant", null=True, blank=True, on_delete=models.CASCADE)
    module = models.ForeignKey(Module, null=True, blank=True, on_delete=models.CASCADE,
                               related_name="own_guidelines")
    section = models.CharField(max_length=20, choices=Section.choices, default=Section.SAFETY)
    text = models.TextField()
    text_hi = models.TextField("text (Hindi)", blank=True)
    text_gu = models.TextField("text (Gujarati)", blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["section", "order", "id"]

    def __str__(self):
        return self.text[:60]

    @property
    def display_text(self):
        return localized(self, "text")


class SOPStep(models.Model):
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name="steps")
    number = models.PositiveSmallIntegerField()
    text = models.TextField()
    text_hi = models.TextField("text (Hindi)", blank=True)
    text_gu = models.TextField("text (Gujarati)", blank=True)
    image = models.ImageField(upload_to="modules/steps/", blank=True)

    class Meta:
        ordering = ["module", "number"]
        unique_together = [("module", "number")]

    def __str__(self):
        return f"{self.module.title} — step {self.number}"

    @property
    def display_text(self):
        return localized(self, "text")


class VideoLesson(models.Model):
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name="videos")
    title = models.CharField(max_length=160)
    title_hi = models.CharField("title (Hindi)", max_length=160, blank=True)
    title_gu = models.CharField("title (Gujarati)", max_length=160, blank=True)
    file = models.FileField(upload_to="modules/videos/", blank=True)
    url = models.URLField(blank=True, help_text="External/CDN URL, used if no file uploaded")
    duration_minutes = models.PositiveSmallIntegerField(null=True, blank=True)
    transcript = models.TextField(blank=True, help_text="Used for search and the AI assistant")
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.title

    @property
    def source(self):
        return self.file.url if self.file else self.url

    display_title = property(lambda self: localized(self, "title"))


class ProblemSolution(models.Model):
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name="problems")
    problem = models.TextField()
    problem_hi = models.TextField("problem (Hindi)", blank=True)
    problem_gu = models.TextField("problem (Gujarati)", blank=True)
    cause = models.TextField(blank=True)
    cause_hi = models.TextField("cause (Hindi)", blank=True)
    cause_gu = models.TextField("cause (Gujarati)", blank=True)
    solution = models.TextField()
    solution_hi = models.TextField("solution (Hindi)", blank=True)
    solution_gu = models.TextField("solution (Gujarati)", blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.problem[:60]

    @property
    def display_problem(self):
        return localized(self, "problem")

    @property
    def display_cause(self):
        return localized(self, "cause")

    @property
    def display_solution(self):
        return localized(self, "solution")


class ModuleImage(models.Model):
    """Photos shown in a module's Overview tab (equipment, process, safety signage…)."""

    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="modules/gallery/")
    caption = models.CharField(max_length=200, blank=True)
    caption_hi = models.CharField("caption (Hindi)", max_length=200, blank=True)
    caption_gu = models.CharField("caption (Gujarati)", max_length=200, blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    display_caption = property(lambda self: localized(self, "caption"))


class DiscussionPost(models.Model):
    """One global discussion space. A post may be tagged to a module; replies point at their parent."""

    module = models.ForeignKey(Module, null=True, blank=True, on_delete=models.SET_NULL, related_name="posts",
                               help_text="Optional topic tag")
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE, related_name="replies")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="discussion_posts")
    body = models.TextField()
    is_hidden = models.BooleanField(default=False, help_text="Hidden by moderator")
    is_pinned = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.author}: {self.body[:50]}"


class ModuleProgress(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="module_progress")
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name="progress")
    safety_ack_at = models.DateTimeField(null=True, blank=True)
    completed_steps = models.ManyToManyField(SOPStep, blank=True, related_name="+")
    seconds_spent = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True,
                                        help_text="Set when all steps done and quiz passed")

    class Meta:
        unique_together = [("user", "module")]
        verbose_name_plural = "module progress"

    def __str__(self):
        return f"{self.user} — {self.module}"

    @property
    def steps_done(self):
        return self.completed_steps.count()

    @property
    def steps_total(self):
        return self.module.steps.count()

    @property
    def all_steps_done(self):
        total = self.steps_total
        return total > 0 and self.steps_done >= total

    @property
    def percent(self):
        total = self.steps_total
        return round(100 * self.steps_done / total) if total else 0
