from django.contrib import admin

from .models import Certificate


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = ["user", "module", "score_percent", "issued_at", "short_code"]
    list_filter = ["module__plant", "module"]
    search_fields = ["user__email", "user__first_name", "code"]
