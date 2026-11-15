from django.urls import path

from . import views, views_import as imp, views_kb as kb, views_more as m

app_name = "panel"
urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("help/", m.help_page, name="help"),
    # plants
    path("plants/", views.plant_list, name="plants"),
    path("plants/new/", views.plant_edit, name="plant_new"),
    path("plants/<int:pk>/", views.plant_edit, name="plant_edit"),
    path("plants/<int:pk>/<slug:tab>/", views.plant_edit, name="plant_tab"),
    path("plants/<int:pk>/delete/confirm/", views.plant_delete, name="plant_delete"),
    # modules
    path("modules/", views.module_list, name="modules"),
    path("modules/new/", views.module_edit, name="module_new"),
    path("modules/bulk/", views.module_bulk, name="module_bulk"),
    path("modules/<int:pk>/", views.module_edit, name="module_edit"),
    path("modules/<int:pk>/status/", views.module_status, name="module_status"),
    path("modules/<int:pk>/delete/", views.module_delete, name="module_delete"),
    path("modules/<int:pk>/import/<slug:kind>/", views.module_import, name="module_import"),
    path("modules/<int:pk>/quiz/question/new/", views.question_edit, name="question_new"),
    path("modules/<int:pk>/quiz/question/<int:qid>/", views.question_edit, name="question_edit"),
    path("modules/<int:pk>/quiz/question/<int:qid>/<slug:action>/", views.question_action, name="question_action"),
    path("modules/<int:pk>/<slug:tab>/", views.module_edit, name="module_tab"),
    path("samples/<slug:kind>.csv", views.sample_csv, name="sample_csv"),
    path("quizzes/", views.quiz_list, name="quizzes"),
    # sops
    path("sops/", m.sop_list, name="sops"),
    path("sops/new/", m.sop_edit, name="sop_new"),
    path("sops/<int:pk>/", m.sop_edit, name="sop_edit"),
    path("sops/<int:pk>/delete/", m.sop_delete, name="sop_delete"),
    # imports
    path("import/", imp.import_center, name="import"),
    path("import/sample/<slug:kind>.<slug:ext>", imp.import_sample, name="import_sample"),
    # knowledge base
    path("knowledge/", kb.kb_list, name="kb"),
    path("knowledge/new/", kb.kb_edit, name="kb_new"),
    path("knowledge/categories/", kb.kb_categories, name="kb_categories"),
    path("knowledge/<int:pk>/", kb.kb_edit, name="kb_edit"),
    path("knowledge/<int:pk>/delete/", kb.kb_delete, name="kb_delete"),
    # users
    path("users/", m.user_list, name="users"),
    path("users/new/", m.user_edit, name="user_new"),
    path("users/import/", m.user_import, name="user_import"),
    path("users/import/sample.csv", m.sample_users_csv, name="sample_users"),
    path("users/<int:pk>/", m.user_edit, name="user_edit"),
    path("users/<int:pk>/reset/", m.user_reset, name="user_reset"),
    # moderation & operations
    path("discussion/", m.discussion_list, name="discussion"),
    path("incidents/", m.incident_list, name="incidents"),
    path("incidents/<int:pk>/status/", m.incident_status, name="incident_status"),
    path("certificates/", m.certificate_list, name="certificates"),
    path("certificates/<int:pk>/revoke/", m.certificate_revoke, name="certificate_revoke"),
    path("reports/", m.reports, name="reports"),
    path("reports/export/<slug:kind>.csv", m.report_export, name="report_export"),
]
