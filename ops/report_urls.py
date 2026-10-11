from django.urls import path

from .views import submit_report

urlpatterns = [path("", submit_report, name="submit")]
