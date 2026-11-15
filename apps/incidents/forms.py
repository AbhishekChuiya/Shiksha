from django import forms
from django.utils.translation import gettext_lazy as _

from apps.plants.models import Department, Process

from .models import Incident

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}


class IncidentForm(forms.ModelForm):
    class Meta:
        model = Incident
        fields = ["category", "department", "process", "title", "description",
                  "occurred_at", "attachment"]
        labels = {"category": _("Category"), "department": _("Department"), "process": _("Process"), "title": _("Title"),
                  "description": _("Description"), "occurred_at": _("Date & time"), "attachment": _("Photo / document")}
        widgets = {
            "occurred_at": forms.DateTimeInput(attrs={"type": "datetime-local"},
                                               format="%Y-%m-%dT%H:%M"),
            "description": forms.Textarea(attrs={"rows": 5}),
        }

    def __init__(self, *args, plant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["department"].queryset = Department.objects.filter(plant=plant)
        self.fields["process"].queryset = Process.objects.filter(department__plant=plant)
        self.fields["department"].label_from_instance = lambda d: f"{d.display_name} ({d.plant.name})"
        self.fields["process"].label_from_instance = lambda p: p.display_name

    def clean_attachment(self):
        f = self.cleaned_data.get("attachment")
        if f:
            ext = f.name[f.name.rfind("."):].lower() if "." in f.name else ""
            if ext not in ALLOWED_EXT:
                raise forms.ValidationError("Allowed files: JPG, PNG, WEBP, PDF.")
            if f.size > 10 * 1024 * 1024:
                raise forms.ValidationError("File must be under 10 MB.")
        return f
