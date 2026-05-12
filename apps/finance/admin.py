from django.contrib import admin

from apps.finance.models import BudgetLine, Commitment, Disbursement, SupportingDoc


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
