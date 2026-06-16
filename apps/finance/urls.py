from django.urls import path

from apps.finance.views import (
    balance_sheet,
    bank_account_detail,
    bank_movement_create,
    bank_movement_delete,
    bank_movement_detail,
    bank_movement_voucher,
    bank_movement_voucher_pdf,
    bank_statement_delete,
    cash_flow_statement,
    bank_statement_review,
    bank_statement_upload,
    cash_movement_create,
    cashflow_dashboard,
    chart_of_accounts_view,
    expense_create,
    expense_detail,
    expense_list,
    expense_record_payment,
    finance_dashboard,
    general_ledger,
    income_statement,
    trial_balance,
)


app_name = "finance"

urlpatterns = [
    path("", finance_dashboard, name="dashboard"),
    path("tresorerie/", cashflow_dashboard, name="cashflow"),
    path("plan-comptable/", chart_of_accounts_view, name="chart_of_accounts"),
    path("balance/", trial_balance, name="trial_balance"),
    path("compte-resultat/", income_statement, name="income_statement"),
    path("bilan/", balance_sheet, name="balance_sheet"),
    path("tableau-flux-tresorerie/", cash_flow_statement, name="cash_flow_statement"),
    path("grand-livre/<str:code>/", general_ledger, name="general_ledger"),
    path("comptes/<uuid:public_uuid>/", bank_account_detail, name="bank_account"),
    path("caisse/saisir/", cash_movement_create, name="cash_movement_create"),
    path("banque/saisir/", bank_movement_create, name="bank_movement_create"),
    path("banque/mouvement/<int:pk>/", bank_movement_detail, name="bank_movement_detail"),
    path("banque/mouvement/<int:pk>/piece/", bank_movement_voucher, name="bank_movement_voucher"),
    path("banque/mouvement/<int:pk>/piece.pdf", bank_movement_voucher_pdf, name="bank_movement_voucher_pdf"),
    path("banque/mouvement/<int:pk>/annuler/", bank_movement_delete, name="bank_movement_delete"),
    path("banque/import-releve/", bank_statement_upload, name="bank_statement_upload"),
    path("banque/import-releve/<int:pk>/", bank_statement_review, name="bank_statement_review"),
    path("banque/import-releve/<int:pk>/supprimer/", bank_statement_delete, name="bank_statement_delete"),
    path("demandes/", expense_list, name="expense_list"),
    path("demandes/nouvelle/", expense_create, name="expense_create"),
    path("demandes/<int:pk>/", expense_detail, name="expense_detail"),
    path("demandes/<int:pk>/saisir-paiement/", expense_record_payment, name="expense_record_payment"),
]
