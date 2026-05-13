from django.urls import path

from apps.finance.views import cashflow_dashboard, finance_dashboard


app_name = "finance"

urlpatterns = [
    path("", finance_dashboard, name="dashboard"),
    path("tresorerie/", cashflow_dashboard, name="cashflow"),
]
