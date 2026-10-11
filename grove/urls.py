from django.urls import path

from . import views

app_name = "grove"

urlpatterns = [
    path("", views.workspace, name="workspace"),
    path("start/", views.create_organization, name="create_organization"),
    path("farm/<slug:slug>/", views.public_farm, name="public_farm"),
    path("batch/<str:code>/", views.public_batch, name="public_batch"),
    path("<slug:slug>/", views.dashboard, name="dashboard"),
    path("<slug:slug>/plots/new/", views.create_plot, name="create_plot"),
    path("<slug:slug>/plots/<int:pk>/", views.plot_detail, name="plot_detail"),
    path("<slug:slug>/plots/<int:pk>/import/", views.import_batches, name="import_batches"),
    path("<slug:slug>/plots/<int:pk>/ndvi/", views.add_health_snapshot, name="add_health_snapshot"),
    path("<slug:slug>/plots/<int:pk>/analyze-health/", views.analyze_plot_health, name="analyze_plot_health"),
    path("<slug:slug>/tasks/new/", views.create_task, name="create_task"),
    path("<slug:slug>/tasks/<int:pk>/complete/", views.complete_task, name="complete_task"),
    path("<slug:slug>/members/add/", views.add_member, name="add_member"),
    path("<slug:slug>/batches/<str:code>/qr/", views.batch_qr, name="batch_qr"),
]
