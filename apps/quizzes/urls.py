from django.urls import path

from . import views

app_name = "quizzes"
urlpatterns = [
    path("", views.quiz_list, name="list"),
    path("<slug:slug>/start/", views.start, name="start"),
    path("attempt/<int:pk>/", views.take, name="take"),
    path("attempt/<int:pk>/result/", views.result, name="result"),
]
