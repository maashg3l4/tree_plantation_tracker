from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("reports/", views.reports, name="reports"),
    path("reports/<int:report_id>/", views.report_detail, name="report_detail"),
    path(
        "reports/<int:report_id>/action/",
        views.report_action,
        name="report_action",
    ),
    path("ai-flags/", views.ai_flags, name="ai_flags"),
    path(
        "ai-flags/<int:flag_id>/action/",
        views.ai_flag_action,
        name="ai_flag_action",
    ),
    path("audit/", views.audit_log, name="audit_log"),
]
