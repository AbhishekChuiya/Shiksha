from django.contrib import admin

from apps.core.models import AuditLog

from .models import SOPAccess, SOPDocument, SOPVersion


class VersionInline(admin.StackedInline):
    model = SOPVersion
    extra = 0
    fields = [("version", "status", "effective_date"), "file", "change_summary",
              "approved_by", "content"]


@admin.register(SOPDocument)
class SOPDocumentAdmin(admin.ModelAdmin):
    list_display = ["code", "title", "plant", "department", "active_version_label", "owner"]
    list_filter = ["plant", "department", "category", "language"]
    search_fields = ["code", "title", "tags"]
    inlines = [VersionInline]

    @admin.display(description="Active version")
    def active_version_label(self, obj):
        v = obj.active_version
        return f"v{v.version} ({v.effective_date:%d %b %Y})" if v else "— none approved —"

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for obj in formset.deleted_objects:
            obj.delete()
        for inst in instances:
            if isinstance(inst, SOPVersion):
                if not inst.uploaded_by_id:
                    inst.uploaded_by = request.user
                is_new = inst.pk is None
                old = None if is_new else SOPVersion.objects.get(pk=inst.pk).status
                inst.save()
                if is_new or old != inst.status:
                    AuditLog.record(request.user, "sop.version_status", inst,
                                    sop=inst.sop.code, version=inst.version,
                                    old=old, new=inst.status)
            else:
                inst.save()
        formset.save_m2m()


@admin.register(SOPAccess)
class SOPAccessAdmin(admin.ModelAdmin):
    list_display = ["sop", "user", "action", "at"]
    list_filter = ["action", "sop__plant"]
    date_hierarchy = "at"
