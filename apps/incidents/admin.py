from django.contrib import admin

from .models import Incident


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = ["id", "title", "plant", "category", "status", "reported_by", "created_at"]
    list_filter = ["status", "category", "plant"]
    search_fields = ["title", "description", "reported_by__email"]
    date_hierarchy = "created_at"
