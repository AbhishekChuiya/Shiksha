from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

# The Django "Advanced admin" is only for superusers (created with `manage.py createsuperuser`).
admin.site.has_permission = lambda request: bool(request.user.is_active and request.user.is_staff and request.user.is_superuser)
admin.site.site_header = "Project Shiksha — Admin"
admin.site.site_title = "Shiksha Admin"
admin.site.index_title = "Content & platform administration"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("i18n/", include("django.conf.urls.i18n")),
    path("manage/", include("apps.panel.urls")),
    path("accounts/", include("apps.accounts.urls")),
    path("modules/", include("apps.learning.urls")),
    path("discussion/", include("apps.learning.discussion_urls")),
    path("quizzes/", include("apps.quizzes.urls")),
    path("sops/", include("apps.sops.urls")),
    path("knowledge/", include("apps.knowledge.urls")),
    path("certificates/", include("apps.certificates.urls")),
    path("incidents/", include("apps.incidents.urls")),
    path("", include("apps.core.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
