from django.db import models

from apps.common.models import TrackedModel


class Commune(TrackedModel):
    code = models.CharField(max_length=10, unique=True, blank=True)
    name = models.CharField(max_length=100)
    department = models.CharField(max_length=80, blank=True)
    region = models.CharField(max_length=50, blank=True)
    is_intervention_zone = models.BooleanField(default=False)

    class Meta:
        db_table = "communes"
        ordering = ["region", "department", "name"]

    def __str__(self):
        return self.name


class BudgetCategory(TrackedModel):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=120)
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="children",
    )
    description = models.TextField(blank=True)

    class Meta:
        db_table = "budget_categories"
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} - {self.name}"


class ContractType(TrackedModel):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    max_duration_months = models.PositiveIntegerField(blank=True, null=True)
    is_permanent = models.BooleanField(default=False)

    class Meta:
        db_table = "contract_types"
        ordering = ["name"]

    def __str__(self):
        return self.name


class DocumentType(TrackedModel):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=120)
    is_required = models.BooleanField(default=False)
    expiry_tracking = models.BooleanField(default=False)

    class Meta:
        db_table = "document_types"
        ordering = ["name"]

    def __str__(self):
        return self.name


class SystemSetting(models.Model):
    key = models.CharField(max_length=60, primary_key=True)
    value = models.TextField(blank=True)
    description = models.CharField(max_length=200, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="system_setting_updates",
    )

    class Meta:
        db_table = "system_settings"
        ordering = ["key"]

    def __str__(self):
        return self.key
