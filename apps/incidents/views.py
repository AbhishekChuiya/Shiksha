from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from apps.core.access import require_plant
from apps.core.models import AuditLog
from apps.learning.models import Module

from .forms import IncidentForm
from .models import Incident


@login_required
def incident_list(request):
    qs = Incident.objects.select_related("plant", "department")
    if not request.user.is_shiksha_admin:
        qs = qs.filter(reported_by=request.user)
    return render(request, "incidents/list.html", {"incidents": qs[:200]})


@login_required
def incident_create(request):
    plant = require_plant(request)
    module = None
    if request.GET.get("module"):
        module = Module.objects.filter(slug=request.GET["module"], plant=plant).first()
    initial = {}
    if module:
        initial = {"department": module.department_id, "process": module.process_id,
                   "title": f"{module.title}: "}
    form = IncidentForm(request.POST or None, request.FILES or None, plant=plant, initial=initial)
    if request.method == "POST" and form.is_valid():
        incident = form.save(commit=False)
        incident.plant = plant
        incident.reported_by = request.user
        incident.module = module
        incident.save()
        AuditLog.record(request.user, "incident.created", incident)
        messages.success(request, _("Incident reported. Reference #%(id)s") % {"id": incident.pk})
        return redirect(incident)
    return render(request, "incidents/form.html", {"form": form, "module": module})


@login_required
def incident_detail(request, pk):
    qs = Incident.objects.select_related("plant", "department", "process", "reported_by")
    if not request.user.is_shiksha_admin:
        qs = qs.filter(reported_by=request.user)
    incident = get_object_or_404(qs, pk=pk)
    if request.method == "POST" and request.user.is_shiksha_admin:
        old = incident.status
        status = request.POST.get("status")
        if status in Incident.Status.values:
            incident.status = status
            incident.closure_notes = request.POST.get("closure_notes", incident.closure_notes)
            incident.save()
            AuditLog.record(request.user, "incident.status", incident, old=old, new=status)
            messages.success(request, _("Incident updated."))
        return redirect(incident)
    history = AuditLog.objects.filter(object_type=Incident._meta.label, object_id=str(pk))
    return render(request, "incidents/detail.html", {"incident": incident, "history": history,
                                                      "statuses": Incident.Status.choices})
