from django.urls import path

from . import views

app_name = "grove_compliance"

urlpatterns = [
    path("<slug:slug>/compliance/", views.overview, name="overview"),
    path("<slug:slug>/compliance/upload/", views.upload_document, name="upload_document"),
    path("<slug:slug>/compliance/documents/<int:pk>/download/", views.download_document, name="download_document"),
]
