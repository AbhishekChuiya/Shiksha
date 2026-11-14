from django.urls import path

from . import views

app_name = "certificates"
urlpatterns = [
    path("", views.certificate_list, name="list"),
    path("verify/<uuid:code>/", views.certificate_verify, name="verify"),
    path("<uuid:code>/", views.certificate_detail, name="detail"),
    path("<uuid:code>/download/", views.certificate_download, name="download"),
]
