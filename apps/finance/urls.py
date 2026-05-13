from django.urls import path

from apps.finance.views import (
    bank_account_detail,
    cashflow_dashboard,
    chart_of_accounts_view,
    expense_create,
    expense_detail,
    expense_list,
    finance_dashboard,
)


app_name = "finance"

urlpatterns = [
    path("", finance_dashboard, name="dashboard"),
    path("tresorerie/", cashflow_dashboard, name="cashflow"),
    path("plan-comptable/", chart_of_accounts_view, name="chart_of_accounts"),
    path("comptes/<uuid:public_uuid>/", bank_account_detail, name="bank_account"),
    path("demandes/", expense_list, name="expense_list"),
    path("demandes/nouvelle/", expense_create, name="expense_create"),
    path("demandes/<int:pk>/", expense_detail, name="expense_detail"),
]
