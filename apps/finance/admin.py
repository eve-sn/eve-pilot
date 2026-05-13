from django.contrib import admin

from apps.finance.models import (
    BankAccount,
    BankAccountSnapshot,
    BankMovement,
    BudgetLine,
    CashflowEntry,
    Commitment,
    Disbursement,
    SupportingDoc,
)


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ("name", "bank_name", "account_reference", "opening_balance", "opening_date", "currency", "is_active")
    search_fields = ("name", "bank_name", "account_reference")
    list_filter = ("bank_name", "is_active")
    fieldsets = (
        (None, {"fields": ("name", "bank_name", "account_reference", "currency")}),
        ("Solde d'ouverture", {"fields": ("opening_balance", "opening_date")}),
        ("Notes", {"fields": ("notes",)}),
        ("Suivi", {"fields": ("is_active", "deleted_at"), "classes": ("collapse",)}),
    )


@admin.register(BankAccountSnapshot)
class BankAccountSnapshotAdmin(admin.ModelAdmin):
    list_display = ("account", "date", "balance", "is_active")
    search_fields = ("account__name", "source_note")
    list_filter = ("account", "is_active")
    date_hierarchy = "date"


@admin.register(BankMovement)
class BankMovementAdmin(admin.ModelAdmin):
    list_display = ("date_operation", "account", "label", "debit", "credit", "balance_after", "reference")
    search_fields = ("label", "reference", "account__name")
    list_filter = ("account", "is_active")
    date_hierarchy = "date_operation"
    autocomplete_fields = ("project", "cashflow_entry")


@admin.register(CashflowEntry)
class CashflowEntryAdmin(admin.ModelAdmin):
    list_display = ("period_year", "period_month", "direction", "label", "planned_amount", "actual_amount")
    search_fields = ("label", "project__code", "category__code")
    list_filter = ("direction", "period_year", "period_month", "is_active")


@admin.register(BudgetLine)
class BudgetLineAdmin(admin.ModelAdmin):
    list_display = ("project", "category", "description", "planned_amount", "committed_amount", "disbursed_amount", "fiscal_year")
    search_fields = ("project__code", "description", "code")
    list_filter = ("currency", "fiscal_year", "is_active")


@admin.register(Commitment)
class CommitmentAdmin(admin.ModelAdmin):
    list_display = ("commitment_number", "budget_line", "supplier_name", "amount", "commitment_date", "status")
    search_fields = ("commitment_number", "supplier_name")
    list_filter = ("status", "commitment_type")


@admin.register(Disbursement)
class DisbursementAdmin(admin.ModelAdmin):
    list_display = ("payment_number", "budget_line", "amount", "payment_date", "payment_method", "status")
    search_fields = ("payment_number", "beneficiary_name", "bank_reference")
    list_filter = ("status", "payment_method", "currency")


@admin.register(SupportingDoc)
class SupportingDocAdmin(admin.ModelAdmin):
    list_display = ("document_type", "document_number", "amount", "uploaded_by", "uploaded_at")
    search_fields = ("document_number", "file_url")
    list_filter = ("document_type", "is_active")
