from django.urls import path

from . import views

app_name = "core"
urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("plant/", views.plant_overview, name="plant_overview"),
    path("plant/switch/", views.set_plant, name="set_plant"),
    path("view-mode/", views.set_view_mode, name="view_mode"),
    path("search/", views.search, name="search"),
    path("search/suggest/", views.suggest, name="suggest"),
    path("progress/", views.progress, name="progress"),
    path("notifications/", views.notifications, name="notifications"),
    path("notifications/read-all/", views.notifications_read_all, name="notifications_read_all"),
    path("notifications/<int:pk>/open/", views.notification_open, name="notification_open"),
    path("soon/<slug:feature>/", views.coming_soon, name="coming_soon"),
]
