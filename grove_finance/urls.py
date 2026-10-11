from django.urls import path

from . import views

app_name = "grove_finance"

urlpatterns = [
    path("<slug:slug>/finance/", views.overview, name="overview"),
    path("<slug:slug>/finance/transactions/new/", views.create_transaction, name="create_transaction"),
    path("<slug:slug>/finance/report.pdf", views.pdf_report, name="pdf_report"),
]
