from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, render

from apps.core.access import check_plant_access, require_plant

from .models import SOPAccess, SOPDocument, SOPVersion


@login_required
def sop_list(request):
    plant = require_plant(request)
    qs = SOPDocument.objects.filter(plant=plant).select_related("department", "process")
    q = (request.GET.get("q") or "").strip()
    dept = request.GET.get("dept")
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(code__icontains=q) | Q(tags__icontains=q)
                       | Q(category__icontains=q))
    if dept:
        qs = qs.filter(department_id=dept)
    # Only SOPs with an approved version are shown to learners.
    qs = qs.filter(versions__status=SOPVersion.Status.APPROVED).distinct()
    return render(request, "sops/list.html", {
        "sops": qs, "q": q, "dept": dept,
        "departments": plant.departments.filter(sops__isnull=False).distinct(),
    })


@login_required
def sop_detail(request, pk):
    sop = get_object_or_404(SOPDocument.objects.select_related("plant", "department"), pk=pk)
    check_plant_access(request.user, sop.plant)
    request.session["current_plant_id"] = sop.plant_id
    request.plant = sop.plant
    active = sop.active_version
    if active is None and not request.user.is_shiksha_admin:
        raise Http404
    SOPAccess.objects.create(sop=sop, user=request.user, action="view")
    history = sop.versions.exclude(status=SOPVersion.Status.DRAFT)
    return render(request, "sops/detail.html", {"sop": sop, "active": active, "history": history})


@login_required
def sop_download(request, pk):
    sop = get_object_or_404(SOPDocument, pk=pk)
    check_plant_access(request.user, sop.plant)
    if not sop.allow_download and not request.user.is_shiksha_admin:
        raise PermissionDenied
    active = sop.active_version
    if not active or not active.file:
        raise Http404
    SOPAccess.objects.create(sop=sop, user=request.user, action="download")
    return FileResponse(active.file.open("rb"), as_attachment=True,
                        filename=f"{sop.code.replace('/', '-')}_v{active.version}"
                                 f"{active.file.name[active.file.name.rfind('.'):]}")
