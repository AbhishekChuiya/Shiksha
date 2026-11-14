from django.urls import path

from . import views

app_name = "learning"
urlpatterns = [
    path("", views.module_list, name="module_list"),
    path("<slug:slug>/", views.module_detail, name="module_detail"),
    path("<slug:slug>/safety/", views.acknowledge_safety, name="ack_safety"),
    path("<slug:slug>/steps/<int:number>/", views.toggle_step, name="toggle_step"),
    path("<slug:slug>/heartbeat/", views.heartbeat, name="heartbeat"),
]
