from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse

from apps.knowledge.models import COLORS, ICONS, KBCategory, KBItem
from apps.plants.models import Plant

from .decorators import admin_required
from .editor import Editor, F
from .forms import KBItemForm
from .views import _editor_page, audit, crumbs, paginate, render_panel


@admin_required
def kb_list(request):
    q = (request.GET.get("q") or "").strip()
    cat, kind = request.GET.get("cat") or "", request.GET.get("kind") or ""
    qs = KBItem.objects.select_related("category", "plant")
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(title_hi__icontains=q) | Q(description__icontains=q))
    if cat.isdigit():
        qs = qs.filter(category_id=cat)
    if kind:
        qs = qs.filter(kind=kind)
    page = paginate(request, qs)
    return render_panel(request, "panel/kb_list.html", page_title="Knowledge base", page=page, q=q, cat=cat, kind=kind, total=page.paginator.count,
                        cats=KBCategory.objects.annotate(n=Count("items")), kinds=KBItem.Kind.choices)


@admin_required
def kb_edit(request, pk=None):
    obj = get_object_or_404(KBItem, pk=pk) if pk else None
    if not KBCategory.objects.exists():
        messages.info(request, "Create at least one category first.")
        return redirect("panel:kb_categories")
    form = KBItemForm(request.POST or None, request.FILES or None, instance=obj, initial={"category": request.GET.get("cat")} if not obj else None)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        if not item.uploaded_by_id:
            item.uploaded_by = request.user
        if request.FILES.get("file") or form.cleaned_data.get("file__clear"):
            item.kind = ""            # re-detect from the new file
        item.save()
        audit(request, "kb.save", item)
        messages.success(request, "Saved.")
        return redirect("panel:kb_edit", pk=item.pk)
    title = obj.title if obj else "Add to knowledge base"
    return render_panel(request, "panel/kb_edit.html", page_title=title, obj=obj, form=form,
                        crumbs=crumbs(("Knowledge base", reverse("panel:kb")), (title, None)),
                        groups=[("What is it?", ["title", "category", "plant", "is_active"]), ("The file", ["file", "url"]),
                                ("Short description (optional)", ["description"]), ("Hindi (optional)", ["title_hi", "description_hi"]), ("Gujarati (optional)", ["title_gu", "description_gu"]), ("Order", ["order"])])


@admin_required
def kb_delete(request, pk):
    obj = get_object_or_404(KBItem, pk=pk)
    if request.method == "POST":
        audit(request, "kb.delete", obj, title=obj.title)
        if obj.file:
            obj.file.delete(save=False)
        obj.delete()
        messages.success(request, "Deleted.")
        return redirect("panel:kb")
    return render_panel(request, "panel/confirm.html", page_title="Delete", obj_name=obj.title, back=reverse("panel:kb_edit", args=[pk]),
                        warning="This permanently deletes the item and its uploaded file.")


@admin_required
def kb_categories(request):
    ed = Editor("cats", KBCategory,
                [F("name", "Category name", required=True, width="half"), F("name_hi", "Name (Hindi)", hindi=True),
                 F("icon", "Icon", "select", required=True, choices=ICONS, width="half"), F("color", "Colour", "select", required=True, choices=COLORS, width="half")],
                {}, filter={}, title="Categories", noun="category", add_label="Add category",
                info="SOP documents and module videos appear automatically in the Knowledge Base. Add categories for everything else — e.g. Machine manuals, Forms & formats, Quality standards.",
                empty_hint="No categories yet — add the first one.")
    ctx = {"page_title": "Knowledge categories", "crumbs": crumbs(("Knowledge base", reverse("panel:kb")), ("Categories", None))}
    return _editor_page(request, "panel/kb_categories.html", [ed], ctx, redirect_name="panel:kb_categories", redirect_kwargs={}, saved="Categories saved.", log=("kb.categories", None))
