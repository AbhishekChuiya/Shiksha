from django.urls import path

from . import views

app_name = "sops"
urlpatterns = [
    path("", views.sop_list, name="list"),
    path("<int:pk>/", views.sop_detail, name="detail"),
    path("<int:pk>/download/", views.sop_download, name="download"),
]
