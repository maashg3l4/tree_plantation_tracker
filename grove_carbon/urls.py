from django.urls import path

from . import views

app_name = "grove_carbon"

urlpatterns = [path("<slug:slug>/carbon/", views.overview, name="overview")]
