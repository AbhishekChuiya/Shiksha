from django.contrib import admin

from .models import KBCategory, KBItem

admin.site.register(KBCategory)


@admin.register(KBItem)
class KBItemAdmin(admin.ModelAdmin):
    list_display = ["title", "category", "kind", "plant", "is_active"]
    list_filter = ["category", "kind", "plant", "is_active"]
    search_fields = ["title", "title_hi"]
