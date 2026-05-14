from django.contrib import admin

from apps.activities.models import Activity, ActivityEvidence, ActivityLocation, ActivityReport, Beneficiary


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ("project", "code", "title", "activity_type", "planned_start_date", "status", "completion_rate")
    search_fields = ("project__code", "code", "title")
    list_filter = ("status", "activity_type", "is_active")


@admin.register(ActivityLocation)
class ActivityLocationAdmin(admin.ModelAdmin):
    list_display = ("activity", "commune")
    search_fields = ("activity__title", "commune__name")


@admin.register(ActivityReport)
class ActivityReportAdmin(admin.ModelAdmin):
    list_display = ("activity", "report_date", "participants_count", "validation_status", "reported_by", "validated_by")
    search_fields = ("activity__title", "actual_location")
    list_filter = ("validation_status",)


@admin.register(ActivityEvidence)
class ActivityEvidenceAdmin(admin.ModelAdmin):
    list_display = ("activity_report", "evidence_type", "uploaded_at", "is_active")
    search_fields = ("caption",)
    list_filter = ("evidence_type", "is_active")


@admin.register(Beneficiary)
class BeneficiaryAdmin(admin.ModelAdmin):
    list_display = ("first_name", "last_name", "activity_report", "gender", "age", "commune")
    search_fields = ("first_name", "last_name", "id_card_number")
    list_filter = ("gender", "commune")
