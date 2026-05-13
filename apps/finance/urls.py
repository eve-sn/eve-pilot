from django.urls import path

from apps.finance.views import (
    bank_account_detail,
    cashflow_dashboard,
    chart_of_accounts_view,
    finance_dashboard,
)


app_name = "finance"

urlpatterns = [
    path("", finance_dashboard, name="dashboard"),
    path("tresorerie/", cashflow_dashboard, name="cashflow"),
    path("plan-comptable/", chart_of_accounts_view, name="chart_of_accounts"),
    path("comptes/<uuid:public_uuid>/", bank_account_detail, name="bank_account"),
]
