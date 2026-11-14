import mimetypes
from dataclasses import dataclass, field

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, render
from django.utils.translation import gettext as _

from apps.core.access import check_plant_access, require_plant
from apps.learning.models import Module, VideoLesson
from apps.sops.models import SOPDocument, SOPVersion

from .models import KBCategory, KBItem, kind_from_name

KIND_FILTERS = [("pdf", "PDFs"), ("doc", "Documents"), ("sheet", "Spreadsheets"), ("video", "Videos"), ("link", "Links")]
KIND_GROUP = {"slides": "doc", "image": "doc"}     # filter chips are grouped for simplicity


@dataclass
class Entry:
    title: str
    kind: str
    cat: str                 # "sops", "videos" or the category pk as text
    url: str
    meta: str = ""
    desc: str = ""
    search: str = ""
    external: bool = False


def _entries(plant):
    out = []
    sops = (SOPDocument.objects.filter(plant=plant, versions__status=SOPVersion.Status.APPROVED)
            .select_related("department").distinct())
    for s in sops:
        v = s.active_version
        kind = kind_from_name(v.file.name) if v and v.file else "pdf"
        out.append(Entry(s.display_title, kind, "sops", s.get_absolute_url(), f"{s.code} · v{v.version}", search=f"{s.title} {s.code} {s.tags} {s.title_hi}"))
    vids = VideoLesson.objects.filter(module__plant=plant, module__status=Module.Status.PUBLISHED).select_related("module")
    for v in vids:
        out.append(Entry(v.title, "video", "videos", v.module.get_absolute_url() + "?tab=videos", v.module.display_title,
                         search=f"{v.title} {v.module.title} {v.transcript[:300]}"))
    items = KBItem.objects.filter(is_active=True).filter(Q(plant__isnull=True) | Q(plant=plant)).select_related("category")
    for i in items:
        out.append(Entry(i.display_title, i.kind, str(i.category_id), i.get_absolute_url(), i.category.display_name, i.display_description,
                         f"{i.title} {i.title_hi} {i.description} {i.category.name}"))
    return out


@login_required
def home(request):
    plant = require_plant(request)
    q = (request.GET.get("q") or "").strip()
    cat = request.GET.get("cat") or ""
    kind = request.GET.get("kind") or ""
    entries = _entries(plant)
    cats = [{"key": "sops", "name": _("SOP documents"), "icon": "file", "color": "red"},
            {"key": "videos", "name": _("Training videos"), "icon": "video", "color": "violet"}]
    cats += [{"key": str(c.pk), "name": c.display_name, "icon": c.icon, "color": c.color} for c in KBCategory.objects.all()]
    for c in cats:
        c["count"] = sum(1 for e in entries if e.cat == c["key"])
    cats = [c for c in cats if c["count"]]
    by_key = {c["key"]: c for c in cats}
    shown = entries
    if q:
        ql = q.lower()
        shown = [e for e in shown if ql in e.search.lower() or ql in e.title.lower()]
    if cat in by_key:
        shown = [e for e in shown if e.cat == cat]
    else:
        cat = ""
    if kind:
        shown = [e for e in shown if (KIND_GROUP.get(e.kind, e.kind)) == kind]
    flat = bool(q or cat or kind)
    sections = []
    if not flat:
        for c in cats:
            sections.append({**c, "entries": [e for e in shown if e.cat == c["key"]]})
    else:
        shown.sort(key=lambda e: e.title.lower())
    for e in shown:
        e.catinfo = by_key.get(e.cat, {"color": "red", "icon": "file"})
    for s in sections:
        for e in s["entries"]:
            e.catinfo = s
    return render(request, "knowledge/home.html", {
        "cats": cats, "cat": cat, "q": q, "kind": kind, "kinds": KIND_FILTERS, "sections": sections, "entries": shown,
        "flat": flat, "total": len(entries), "found": len(shown)})


def _visible(request, pk):
    obj = get_object_or_404(KBItem.objects.select_related("category", "plant"), pk=pk)
    if not obj.is_active and not request.user.is_shiksha_admin:
        raise Http404
    if obj.plant_id:
        check_plant_access(request.user, obj.plant)
    return obj


@login_required
def item(request, pk):
    obj = _visible(request, pk)
    related = KBItem.objects.filter(category=obj.category, is_active=True).exclude(pk=obj.pk)[:4]
    return render(request, "knowledge/item.html", {"it": obj, "related": related})


@login_required
def item_file(request, pk):
    obj = _visible(request, pk)
    if not obj.file:
        raise Http404
    ctype = mimetypes.guess_type(obj.file.name)[0] or "application/octet-stream"
    name = obj.file.name.rsplit("/", 1)[-1]
    return FileResponse(obj.file.open("rb"), content_type=ctype, as_attachment=bool(request.GET.get("dl")), filename=name)
