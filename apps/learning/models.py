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
    purpose = models.TextField(blank=True, help_text="Why this process exists — shown on the Overview tab")
    purpose_hi = models.TextField("purpose (Hindi)", blank=True)
    purpose_gu = models.TextField("purpose (Gujarati)", blank=True)
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
    is_mandatory = models.BooleanField("required", default=False, help_text="Every learner of this plant must complete it")
    due_date = models.DateField(null=True, blank=True, help_text="Last day to complete a required module")
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
    def display_purpose(self):
        return localized(self, "purpose")

    @property
    def accountable_summary(self):
        """Everyone named as 'Accountable' in the Who-does-what table, each name once, in order."""
        seen, out = set(), []
        for role in self.roles.all():
            for part in localized(role, "accountable").split("/"):
                part = part.strip()
                if part and part.lower() not in seen:
                    seen.add(part.lower())
                    out.append(part)
        return " / ".join(out)

    @property
    def objective_list(self):
        return [o.strip() for o in localized(self, "objectives").splitlines() if o.strip()]

    def safety_guidelines(self):
        return SafetyGuideline.objects.filter(
            models.Q(module=self) | models.Q(module__isnull=True, plant=self.plant)
            | models.Q(module__isnull=True, plant__isnull=True)
        ).filter(sop__isnull=True)      # rules that belong to ONE SOP are shown only inside that SOP


class SafetyGuideline(models.Model):
    """Shown before SOP steps; learner must agree before steps unlock.

    Leave `module` empty to apply to every module of `plant`; leave both
    empty to apply everywhere.
    """

    class Section(models.TextChoices):
        PPE = "ppe", "PPE required"
        PRESTART = "prestart", "Pre-start checks"
        HAZARDS = "hazards", "Hazards — high-risk areas"
        PRACTICES = "practices", "Safe operating practices"
        DOS = "dos", "Do's"
        DONTS = "donts", "Don'ts"
        SAFETY = "safety", "Safety (general)"
        ENVIRONMENT = "environment", "Environment, Quality & Discipline"

    plant = models.ForeignKey("plants.Plant", null=True, blank=True, on_delete=models.CASCADE)
    module = models.ForeignKey(Module, null=True, blank=True, on_delete=models.CASCADE,
                               related_name="own_guidelines")
    sop = models.ForeignKey("learning.ModuleSOP", null=True, blank=True, on_delete=models.CASCADE, related_name="guidelines",
                            help_text="Leave empty for rules shared by the whole module")
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
    sop = models.ForeignKey("learning.ModuleSOP", null=True, blank=True, on_delete=models.CASCADE, related_name="steps")
    number = models.PositiveSmallIntegerField()
    text = models.TextField()
    text_hi = models.TextField("text (Hindi)", blank=True)
    text_gu = models.TextField("text (Gujarati)", blank=True)
    image = models.ImageField(upload_to="modules/steps/", blank=True)

    class Meta:
        ordering = ["module", "sop", "number"]
        constraints = [
            models.UniqueConstraint(fields=["sop", "number"], condition=models.Q(sop__isnull=False), name="uniq_step_per_sop"),
            models.UniqueConstraint(fields=["module", "number"], condition=models.Q(sop__isnull=True), name="uniq_step_per_module_without_sop"),
        ]

    def __str__(self):
        return f"{self.module.title} — step {self.number}"

    @property
    def display_text(self):
        return localized(self, "text")



class ModuleSOP(models.Model):
    """One procedure inside a module. A process often has several (e.g. Extrusion has 4); each has its own
    steps, PPE, pre-start checks, hazards and safe-operating rules, and is acknowledged separately."""

    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name="sops")
    title = models.CharField(max_length=200)
    title_hi = models.CharField("title (Hindi)", max_length=200, blank=True)
    title_gu = models.CharField("title (Gujarati)", max_length=200, blank=True)
    code = models.CharField("document number", max_length=60, blank=True, help_text="e.g. VRPL-MANF-SOP-04")
    revision = models.CharField(max_length=20, blank=True)
    doc_date = models.DateField("document date", null=True, blank=True)
    languages = models.CharField(max_length=80, blank=True, help_text="e.g. English + हिंदी")
    intro = models.TextField("safety statement", blank=True, help_text="Shown above the “I agree” box")
    intro_hi = models.TextField("safety statement (Hindi)", blank=True)
    intro_gu = models.TextField("safety statement (Gujarati)", blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["module", "order", "id"]
        verbose_name = "SOP in module"
        verbose_name_plural = "SOPs in module"

    def __str__(self):
        return f"{self.module.title} — {self.title}"

    display_title = property(lambda self: localized(self, "title"))
    display_intro = property(lambda self: localized(self, "intro"))

    @property
    def intro_paragraphs(self):
        return [p.strip() for p in self.display_intro.split("\n") if p.strip()]


class SOPAcknowledgement(models.Model):
    """A learner agreed to the safety rules of one SOP."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sop_acks")
    sop = models.ForeignKey(ModuleSOP, on_delete=models.CASCADE, related_name="acks")
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("user", "sop")]


class ModuleRole(models.Model):
    """'Who does what': one row of the responsibility table."""

    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name="roles")
    activity = models.TextField()
    activity_hi = models.TextField("activity (Hindi)", blank=True)
    activity_gu = models.TextField("activity (Gujarati)", blank=True)
    responsible = models.CharField(max_length=200, blank=True)
    responsible_hi = models.CharField("responsible (Hindi)", max_length=200, blank=True)
    responsible_gu = models.CharField("responsible (Gujarati)", max_length=200, blank=True)
    accountable = models.CharField(max_length=200, blank=True)
    accountable_hi = models.CharField("accountable (Hindi)", max_length=200, blank=True)
    accountable_gu = models.CharField("accountable (Gujarati)", max_length=200, blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["module", "order", "id"]

    display_activity = property(lambda self: localized(self, "activity"))
    display_responsible = property(lambda self: localized(self, "responsible"))
    display_accountable = property(lambda self: localized(self, "accountable"))


class ModuleEscalation(models.Model):
    """'Who to call': a situation and what to do about it."""

    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name="escalations")
    situation = models.CharField(max_length=200)
    situation_hi = models.CharField("situation (Hindi)", max_length=200, blank=True)
    situation_gu = models.CharField("situation (Gujarati)", max_length=200, blank=True)
    action = models.CharField(max_length=200, default="Escalate immediately")
    action_hi = models.CharField("action (Hindi)", max_length=200, blank=True)
    action_gu = models.CharField("action (Gujarati)", max_length=200, blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["module", "order", "id"]

    display_situation = property(lambda self: localized(self, "situation"))
    display_action = property(lambda self: localized(self, "action"))


class ModuleRecord(models.Model):
    """A form or record that belongs to this process, with its document number."""

    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name="records")
    name = models.CharField(max_length=200)
    name_hi = models.CharField("name (Hindi)", max_length=200, blank=True)
    name_gu = models.CharField("name (Gujarati)", max_length=200, blank=True)
    code = models.CharField("document number", max_length=80, blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["module", "order", "id"]

    display_name = property(lambda self: localized(self, "name"))


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
    """One discussion space per plant (shared by every module of that plant). A post may be tagged to a module; replies point at their parent."""

    module = models.ForeignKey(Module, null=True, blank=True, on_delete=models.SET_NULL, related_name="posts",
                               help_text="Optional topic tag")
    plant = models.ForeignKey("plants.Plant", null=True, blank=True, on_delete=models.CASCADE, related_name="discussion_posts",
                              help_text="Each plant has its own discussion space")
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


class StudyDay(models.Model):
    """Learning time per learner, module and day (fed by the module page's 30-second heartbeat) — drives the analytics page."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="study_days")
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name="study_days")
    day = models.DateField()
    seconds = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = [("user", "module", "day")]
        indexes = [models.Index(fields=["user", "day"])]
