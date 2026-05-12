from django.contrib import admin

from apps.references.models import BudgetCategory, Commune, ContractType, DocumentType, SystemSetting


@admin.register(Commune)
class CommuneAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "department", "region", "is_intervention_zone", "is_active")
    search_fields = ("code", "name", "department", "region")
    list_filter = ("region", "is_intervention_zone", "is_active")


@admin.register(BudgetCategory)
class BudgetCategoryAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "parent", "is_active")
    search_fields = ("code", "name")
    list_filter = ("is_active",)


@admin.register(ContractType)
class ContractTypeAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "max_duration_months", "is_permanent", "is_active")
    search_fields = ("code", "name")
    list_filter = ("is_permanent", "is_active")


@admin.register(DocumentType)
class DocumentTypeAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_required", "expiry_tracking", "is_active")
    search_fields = ("code", "name")
    list_filter = ("is_required", "expiry_tracking", "is_active")


@admin.register(SystemSetting)
class SystemSettingAdmin(admin.ModelAdmin):
    list_display = ("key", "value", "updated_at", "updated_by")
    search_fields = ("key", "value")
