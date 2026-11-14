from django.urls import path

from . import views

app_name = "knowledge"
urlpatterns = [
    path("", views.home, name="home"),
    path("<int:pk>/", views.item, name="item"),
    path("<int:pk>/file/", views.item_file, name="file"),
]
