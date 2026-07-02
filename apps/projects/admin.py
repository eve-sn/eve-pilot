from django.contrib import admin

from apps.projects.models import Donor, Indicator, IndicatorValue, Project, ProjectDonor, ProjectLocation, ProjectTeam


@admin.register(Donor)
class DonorAdmin(admin.ModelAdmin):
    list_display = ("name", "short_name", "donor_type", "country", "is_active")
    search_fields = ("name", "short_name", "country")
    list_filter = ("donor_type", "is_active")


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("code", "title", "primary_donor", "project_manager", "status", "start_date", "end_date")
    search_fields = ("code", "title", "short_title")
    list_filter = ("status", "sector", "is_active")
    # Valideurs specifiques au projet (vide = trio par defaut RAF/DP/SE).
    filter_horizontal = ("validator_roles",)


@admin.register(ProjectDonor)
class ProjectDonorAdmin(admin.ModelAdmin):
    list_display = ("project", "donor", "contribution_amount", "contribution_percentage")
    search_fields = ("project__code", "donor__name")


@admin.register(ProjectTeam)
class ProjectTeamAdmin(admin.ModelAdmin):
    list_display = ("project", "employee", "role", "allocation_percentage", "start_date", "end_date")
    search_fields = ("project__code", "employee__first_name", "employee__last_name", "role")


@admin.register(ProjectLocation)
class ProjectLocationAdmin(admin.ModelAdmin):
    list_display = ("project", "commune")
    search_fields = ("project__code", "commune__name")


@admin.register(Indicator)
class IndicatorAdmin(admin.ModelAdmin):
    list_display = ("project", "code", "name", "indicator_type", "target_value", "current_value", "achievement_rate")
    search_fields = ("project__code", "code", "name")
    list_filter = ("indicator_type", "frequency", "is_active")


@admin.register(IndicatorValue)
class IndicatorValueAdmin(admin.ModelAdmin):
    list_display = ("indicator", "value", "period_start", "period_end", "recorded_by", "recorded_at")
    search_fields = ("indicator__code", "indicator__name")
