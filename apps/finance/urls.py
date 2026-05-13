from django.urls import path

from apps.finance.views import finance_dashboard


app_name = "finance"

urlpatterns = [
    path("", finance_dashboard, name="dashboard"),
]
