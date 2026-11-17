import re

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model, password_validation
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import UploadedFile
from django.utils.text import slugify

from apps.core.images import ImageRejected, optimize_image
from apps.learning.models import Module
from apps.plants.models import Department, Plant, Process
from apps.quizzes.models import Question, Quiz
from apps.sops.models import SOPDocument

User = get_user_model()


class PanelForm(forms.ModelForm):
    """ModelForm that (1) shrinks uploaded photos, (2) offers 'remove current file', (3) cleans up replaced files."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._file_fields = [n for n, f in self.fields.items() if isinstance(f, forms.FileField)]
        for n in self._file_fields:
            f = self.fields[n]
            f.widget = forms.FileInput(attrs={"accept": "image/*" if isinstance(f, forms.ImageField) else "*/*"})
            if self.instance.pk and getattr(self.instance, n):
                self.fields[f"{n}__clear"] = forms.BooleanField(required=False, label="Remove current image" if isinstance(f, forms.ImageField) else "Remove current file")

    def clean(self):
        data = super().clean()
        for n in self._file_fields:
            up = data.get(n)
            if isinstance(up, UploadedFile) and isinstance(self.fields[n], forms.ImageField):
                try:
                    data[n] = optimize_image(up)
                except ImageRejected as exc:
                    self.add_error(n, str(exc))
        return data

    def save(self, commit=True):
        olds = {n: self.initial.get(n) for n in self._file_fields}
        obj = super().save(commit=False)
        stale = []
        for n in self._file_fields:
            up = self.cleaned_data.get(n)
            replaced = isinstance(up, (UploadedFile, ContentFile))
            if self.cleaned_data.get(f"{n}__clear") and not replaced:
                setattr(obj, n, "")
                if olds[n]:
                    stale.append(olds[n])
            elif replaced and olds[n]:
                stale.append(olds[n])
        if commit:
            obj.save()
            self.save_m2m()
            for old in stale:
                try:
                    old.storage.delete(old.name)
                except Exception:
                    pass
        return obj


class DeptChoice(forms.ModelChoiceField):
    def label_from_instance(self, d):
        return f"{d.plant.name} · {d.name}"


class ProcChoice(forms.ModelChoiceField):
    def label_from_instance(self, p):
        return f"{p.department.plant.name} · {p.department.name} · {p.name}"


def _unique_slug(model, base, field="slug", instance=None, sep="_"):
    base = re.sub(r"[^a-z0-9]+", sep, base.lower()).strip(sep) or "item"
    slug, n = base, 2
    qs = model.objects.all()
    if instance is not None and instance.pk:
        qs = qs.exclude(pk=instance.pk)
    while qs.filter(**{field: slug}).exists():
        slug = f"{base}{sep}{n}"
        n += 1
    return slug


# --------------------------------------------------------------------- plant
class PlantForm(PanelForm):
    class Meta:
        model = Plant
        fields = ["name", "company", "location", "location_hi", "location_gu", "tagline", "tagline_hi", "tagline_gu", "about", "about_hi", "about_gu", "banner", "order", "is_active", "code"]
        labels = {"name": "Plant name", "company": "Company (legal name)", "location_hi": "Location (Hindi)", "location_gu": "Location (Gujarati)", "banner": "Banner photo",
                  "order": "Position in lists", "is_active": "Active (visible to learners)", "code": "Short web name"}
        help_texts = {"name": "Shown everywhere, e.g. VMPL P1.", "tagline": "One line under the plant name on the Plant Overview page.",
                      "about": "A few paragraphs. Press Enter twice for a new paragraph.", "banner": "Wide photo (landscape) works best. It is resized automatically.",
                      "order": "Lower numbers appear first.", "code": "Used in web addresses. Leave blank to create it from the name."}
        widgets = {"about": forms.Textarea(attrs={"rows": 7}), "about_hi": forms.Textarea(attrs={"rows": 7}), "about_gu": forms.Textarea(attrs={"rows": 7}), "tagline": forms.TextInput, }

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.fields["code"].required = False
        self.fields["code"].disabled = bool(self.instance.pk)  # changing it later would break existing links

    def clean_code(self):
        if self.instance.pk:
            return self.instance.code
        code = slugify(self.cleaned_data.get("code") or self.data.get("name", ""))[:20] or "plant"
        return _unique_slug(Plant, code, "code", self.instance, sep="-")[:20]


# -------------------------------------------------------------------- module
class ModuleForm(PanelForm):
    department = DeptChoice(queryset=Department.objects.select_related("plant"), label="Department")
    process = ProcChoice(queryset=Process.objects.select_related("department__plant"), required=False, label="Process (optional)")

    class Meta:
        model = Module
        fields = ["title", "title_hi", "title_gu", "plant", "department", "process", "category", "category_hi", "category_gu", "library", "summary", "summary_hi", "summary_gu",
                  "overview", "overview_hi", "overview_gu", "purpose", "purpose_hi", "purpose_gu", "objectives", "objectives_hi", "objectives_gu", "cover", "est_minutes", "instructor", "sop_document", "status", "is_mandatory", "due_date", "order", "slug"]
        labels = {"title": "Module title", "est_minutes": "Estimated time (minutes)", "sop_document": "Linked SOP", "cover": "Cover photo",
                  "library": "Library", "is_mandatory": "Required for every learner", "due_date": "Complete by (date)", "category": "Category (filter chip)", "status": "Status", "order": "Position in lists", "slug": "Web address name"}
        help_texts = {"title": "e.g. Melt & Cast", "summary": "One or two lines shown on the module card.", "overview": "Shown on the Overview tab. Press Enter twice for a new paragraph.",
                      "objectives": "One learning objective per line.", "cover": "Shown on the module card and at the top of the Overview tab.",
                      "status": "Draft = hidden from learners. Published = visible.", "is_mandatory": "Learners see a Required badge and an alert on their dashboard until they finish it.", "due_date": "Optional. Learners are reminded as the date gets close, and told when it has passed.", "slug": "Leave blank to create it from the title.",
                      "category": "Learners can filter by this, e.g. Extrusion.", "order": "Lower numbers appear first inside a department."}
        widgets = {"due_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"), "overview": forms.Textarea(attrs={"rows": 7}), "overview_hi": forms.Textarea(attrs={"rows": 7}), "overview_gu": forms.Textarea(attrs={"rows": 7}), "objectives": forms.Textarea(attrs={"rows": 4}),
                   "objectives_hi": forms.Textarea(attrs={"rows": 4}), "objectives_gu": forms.Textarea(attrs={"rows": 4}), "purpose": forms.Textarea(attrs={"rows": 3}), "purpose_hi": forms.Textarea(attrs={"rows": 3}), "purpose_gu": forms.Textarea(attrs={"rows": 3}), "summary": forms.Textarea(attrs={"rows": 2}), "summary_hi": forms.Textarea(attrs={"rows": 2}), "summary_gu": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.fields["slug"].required = False
        self.fields["sop_document"].queryset = SOPDocument.objects.select_related("plant")
        self.fields["sop_document"].label_from_instance = lambda s: f"{s.plant.name} · {s.code} — {s.title}"
        self.fields["sop_document"].required = False
        if not self.instance.pk:                        # unfinished modules must not go live by accident
            self.initial.setdefault("status", Module.Status.DRAFT)

    def clean(self):
        data = super().clean()
        plant, dept, proc = data.get("plant"), data.get("department"), data.get("process")
        if plant and dept and dept.plant_id != plant.pk:
            self.add_error("department", "This department belongs to a different plant. Pick one from the selected plant.")
        if dept and proc and proc.department_id != dept.pk:
            self.add_error("process", "This process belongs to a different department.")
        return data

    def clean_slug(self):
        slug = (self.cleaned_data.get("slug") or "").strip()
        if not slug:
            return _unique_slug(Module, self.data.get("title", "module"), "slug", self.instance)
        slug = re.sub(r"[^a-z0-9_-]+", "_", slug.lower())
        if Module.objects.exclude(pk=self.instance.pk).filter(slug=slug).exists():
            raise forms.ValidationError("Another module already uses this web address name.")
        return slug


class QuizSettingsForm(forms.ModelForm):
    class Meta:
        model = Quiz
        fields = ["title", "pass_percent", "questions_per_attempt", "time_limit_minutes", "max_attempts", "shuffle_questions", "shuffle_choices", "requires_all_steps", "is_mandatory", "due_date", "is_active"]
        widgets = {"due_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}
        labels = {"is_mandatory": "Required for every learner", "due_date": "Pass by (date)", "title": "Quiz title (optional)", "pass_percent": "Pass mark (%)", "questions_per_attempt": "Questions per attempt",
                  "time_limit_minutes": "Time limit (minutes)", "max_attempts": "Maximum attempts", "shuffle_questions": "Change question order every attempt",
                  "shuffle_choices": "Shuffle answer options every attempt", "requires_all_steps": "Learner must finish all SOP steps first", "is_active": "Quiz is active"}
        help_texts = {"is_mandatory": "Shown as Required with an alert on the learner dashboard until it is passed.", "due_date": "Optional. Learners are reminded as it gets close.", "questions_per_attempt": "Leave blank to ask every question. If you set a smaller number, questions the learner has not seen recently are chosen first.",
                      "time_limit_minutes": "Leave blank for no time limit.", "max_attempts": "Leave blank for unlimited attempts."}

    def clean_pass_percent(self):
        v = self.cleaned_data["pass_percent"]
        if not 1 <= v <= 100:
            raise forms.ValidationError("Enter a number between 1 and 100.")
        return v


class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ["text", "text_hi", "text_gu", "kind", "explanation", "explanation_hi", "explanation_gu", "keep_choice_order"]
        labels = {"text": "Question", "kind": "Label above the question", "explanation": "Explanation (shown after answering)",
                  "keep_choice_order": 'Keep options in the order below (for "All of the above" style questions)'}
        help_texts = {"kind": 'Small heading, e.g. "Diagnostic" or "Safety".'}
        widgets = {"text": forms.Textarea(attrs={"rows": 3}), "text_hi": forms.Textarea(attrs={"rows": 3}), "text_gu": forms.Textarea(attrs={"rows": 3}),
                   "explanation": forms.Textarea(attrs={"rows": 2}), "explanation_hi": forms.Textarea(attrs={"rows": 2}), "explanation_gu": forms.Textarea(attrs={"rows": 2})}


# ----------------------------------------------------------------------- SOP
class SOPForm(PanelForm):
    department = DeptChoice(queryset=Department.objects.select_related("plant"), label="Department")
    process = ProcChoice(queryset=Process.objects.select_related("department__plant"), required=False, label="Process (optional)")

    class Meta:
        model = SOPDocument
        fields = ["title", "title_hi", "title_gu", "code", "plant", "department", "process", "category", "tags", "owner", "language", "allow_download"]
        labels = {"code": "Document number", "allow_download": "Learners may download the file", "owner": "Content owner"}
        help_texts = {"code": "Your controlled document number, e.g. VMPL/PRD/SOP/01.", "tags": "Comma separated, e.g. furnace, safety.",
                      "language": "Language of the document (used for read-aloud)."}

    def clean(self):
        data = super().clean()
        plant, dept = data.get("plant"), data.get("department")
        if plant and dept and dept.plant_id != plant.pk:
            self.add_error("department", "This department belongs to a different plant.")
        return data


# --------------------------------------------------------------------- users
class UserForm(forms.ModelForm):
    new_password = forms.CharField(required=False, widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}), label="Set a password now (optional)",
                                   help_text="Leave blank and the user is emailed a link to choose their own password.")
    plants = forms.ModelMultipleChoiceField(queryset=Plant.objects.all(), required=False, widget=forms.CheckboxSelectMultiple, label="Restrict to these plants",
                                            help_text="Leave all unticked to give access to every plant.")

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "employee_id", "designation", "role", "department", "plants", "default_plant", "is_active"]
        labels = {"employee_id": "Employee ID", "role": "Role", "default_plant": "Starting plant", "is_active": "Account is active (can sign in)"}
        help_texts = {"role": "Admins can open this panel. Learners cannot.", "designation": 'Job title shown to them, e.g. "Production Operator".'}

    def __init__(self, *a, acting_user=None, **kw):
        super().__init__(*a, **kw)
        self.acting_user = acting_user
        self.fields["department"].queryset = Department.objects.select_related("plant")
        self.fields["department"].label_from_instance = lambda d: f"{d.plant.name} · {d.name}"
        self.fields["department"].required = False
        self.fields["default_plant"].required = False
        if self.instance.pk:
            self.fields["new_password"].label = "Set a new password (optional)"
            self.fields["new_password"].help_text = "Leave blank to keep the current password."

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        domains = settings.ALLOWED_EMAIL_DOMAINS
        if domains and email.rsplit("@", 1)[-1] not in domains:
            raise forms.ValidationError("Use a company address: " + ", ".join("@" + d for d in domains))
        return email

    def clean_employee_id(self):
        eid = (self.cleaned_data.get("employee_id") or "").strip()
        if not eid:
            return None
        if User.objects.exclude(pk=self.instance.pk).filter(employee_id__iexact=eid).exists():
            raise forms.ValidationError("Another user already has this Employee ID.")
        return eid

    def clean_new_password(self):
        pw = self.cleaned_data.get("new_password")
        if pw:
            password_validation.validate_password(pw, self.instance)
        return pw

    def clean(self):
        data = super().clean()
        inst = self.instance
        if inst.pk:
            becoming_non_admin = data.get("role") != User.Role.ADMIN or not data.get("is_active")
            if inst.role == User.Role.ADMIN and becoming_non_admin:
                others = User.objects.filter(role=User.Role.ADMIN, is_active=True).exclude(pk=inst.pk).count()
                if self.acting_user and inst.pk == self.acting_user.pk:
                    raise forms.ValidationError("You can't remove your own admin access or deactivate yourself. Ask another admin.")
                if others == 0:
                    raise forms.ValidationError("This is the last active admin. Make another admin first.")
        return data


# ----------------------------------------------------------- knowledge base
from apps.knowledge.models import KBItem  # noqa: E402


class KBItemForm(PanelForm):
    class Meta:
        model = KBItem
        fields = ["title", "title_hi", "title_gu", "category", "plant", "file", "url", "description", "description_hi", "description_gu", "is_active", "order"]
        labels = {"file": "File (PDF, Word, Excel, PowerPoint, video…)", "url": "…or a web / YouTube link", "plant": "Show at", "is_active": "Visible to learners",
                  "order": "Sort order"}
        help_texts = {"plant": "Leave on “Every plant” to show at all plants.", "file": "Upload the file, or give a link below. Large videos are better as a YouTube link.",
                      "order": "Smaller numbers come first."}
        widgets = {"description": forms.Textarea(attrs={"rows": 3}), "description_hi": forms.Textarea(attrs={"rows": 3}), "description_gu": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["plant"].empty_label = "Every plant"

    def clean(self):
        data = super().clean()
        has_file = data.get("file") or (self.instance.pk and self.instance.file and not data.get("file__clear"))
        if not has_file and not data.get("url"):
            raise forms.ValidationError("Upload a file or paste a link.")
        return data


class QuizCreateForm(forms.Form):
    """Create the quiz of a module — plant, category (department) and module are chosen step by step."""

    plant = forms.ModelChoiceField(Plant.objects.all(), label="Plant")
    department = forms.ModelChoiceField(Department.objects.all(), label="Category (department)")
    module = forms.ModelChoiceField(Module.objects.filter(quiz__isnull=True), label="Module")
    title = forms.CharField(required=False, max_length=160, label="Quiz title (optional)", help_text="Leave empty to use “<module name> — SOP Quiz”.")
    pass_percent = forms.IntegerField(min_value=1, max_value=100, initial=80, label="Pass mark (%)")
    questions_per_attempt = forms.IntegerField(required=False, min_value=1, label="Questions per attempt (optional)", help_text="Leave empty to ask every question.")
    time_limit_minutes = forms.IntegerField(required=False, min_value=1, label="Time limit in minutes (optional)")
    max_attempts = forms.IntegerField(required=False, min_value=1, label="Maximum attempts (optional)", help_text="Leave empty for unlimited attempts.")

    def clean(self):
        data = super().clean()
        plant, dept, module = data.get("plant"), data.get("department"), data.get("module")
        if plant and dept and dept.plant_id != plant.pk:
            self.add_error("department", "This department belongs to a different plant.")
        if module and plant and module.plant_id != plant.pk:
            self.add_error("module", "This module belongs to a different plant.")
        if module and dept and module.department_id != dept.pk:
            self.add_error("module", "This module is in a different department.")
        return data
