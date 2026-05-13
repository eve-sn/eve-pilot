from django.urls import path

from apps.finance.views import bank_account_detail, cashflow_dashboard, finance_dashboard


app_name = "finance"

urlpatterns = [
    path("", finance_dashboard, name="dashboard"),
    path("tresorerie/", cashflow_dashboard, name="cashflow"),
    path("comptes/<uuid:public_uuid>/", bank_account_detail, name="bank_account"),
]
