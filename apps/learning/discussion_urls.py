from django.urls import path

from . import views

app_name = "discussion"
urlpatterns = [
    path("", views.discussion, name="feed"),
    path("post/", views.discussion_post, name="post"),
    path("<int:pk>/delete/", views.discussion_delete, name="delete"),
    path("<int:pk>/moderate/", views.discussion_moderate, name="moderate"),
]
