from django.contrib import admin

from apps.reporting.models import Report, ReportExport, ReportTemplate


@admin.register(ReportTemplate)
class ReportTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "report_type", "donor", "is_active")
    search_fields = ("name", "report_type")
    list_filter = ("report_type", "is_active")


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("title", "template", "project", "status", "generated_by", "generated_at")
    search_fields = ("title", "project__code", "project__title")
    list_filter = ("status",)


@admin.register(ReportExport)
class ReportExportAdmin(admin.ModelAdmin):
    list_display = ("report", "export_format", "exported_by", "exported_at")
    search_fields = ("report__title", "file_url")
    list_filter = ("export_format",)
