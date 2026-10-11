from django.urls import path

from . import views

app_name = "grove_market"

urlpatterns = [
    path("", views.listings, name="listings"),
    path("new/", views.create_listing, name="create_listing"),
]
