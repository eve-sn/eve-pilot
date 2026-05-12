from django.contrib import admin

from apps.hr.models import (
    Contract,
    Employee,
    EmployeeDocument,
    Evaluation,
    Leave,
    Payslip,
    WorkforceGeography,
    WorkforceSnapshot,
)


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = (
        "matricule",
        "first_name",
        "last_name",
        "workforce_category",
        "position",
        "organizational_unit",
        "assignment_label",
        "status",
        "is_active",
    )
    search_fields = (
        "matricule",
        "first_name",
        "last_name",
        "position",
        "department",
        "organizational_unit",
        "assignment_label",
        "reference_source",
    )
    list_filter = ("workforce_category", "status", "department", "organizational_unit", "is_active")


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = ("contract_number", "employee", "contract_type", "project", "start_date", "end_date", "status")
    search_fields = ("contract_number", "employee__first_name", "employee__last_name")
    list_filter = ("status", "contract_type")


@admin.register(Leave)
class LeaveAdmin(admin.ModelAdmin):
    list_display = ("employee", "leave_type", "start_date", "end_date", "days_count", "status")
    search_fields = ("employee__first_name", "employee__last_name", "leave_type")
    list_filter = ("leave_type", "status")


@admin.register(Payslip)
class PayslipAdmin(admin.ModelAdmin):
    list_display = ("employee", "period_month", "period_year", "net_salary", "status", "payment_date")
    search_fields = ("employee__first_name", "employee__last_name")
    list_filter = ("period_year", "period_month", "status")


@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = ("employee", "evaluator", "evaluation_year", "overall_score", "status")
    search_fields = ("employee__first_name", "employee__last_name", "evaluation_year")
    list_filter = ("evaluation_year", "status")


@admin.register(EmployeeDocument)
class EmployeeDocumentAdmin(admin.ModelAdmin):
    list_display = ("employee", "document_type", "title", "expiry_date", "is_active")
    search_fields = ("employee__first_name", "employee__last_name", "title")
    list_filter = ("document_type", "is_active")


class WorkforceGeographyInline(admin.TabularInline):
    model = WorkforceGeography
    extra = 0


@admin.register(WorkforceSnapshot)
class WorkforceSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        "reference_code",
        "title",
        "source_date",
        "reported_total_staff",
        "detailed_total_staff",
        "relay_worker_count",
    )
    search_fields = ("reference_code", "title", "scope")
    inlines = [WorkforceGeographyInline]
