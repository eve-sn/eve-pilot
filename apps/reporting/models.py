from django.db import models

from apps.common.models import TrackedModel


class ReportTemplate(TrackedModel):
    class ReportType(models.TextChoices):
        INTERNAL_MONTHLY = "INTERNE_MENSUEL", "Interne mensuel"
        INTERNAL_QUARTERLY = "INTERNE_TRIMESTRIEL", "Interne trimestriel"
        DONOR = "BAILLEUR", "Bailleur"
        AUDIT = "AUDIT", "Audit"
        HR = "RH", "RH"
        FINANCE = "FINANCE", "Finance"

    name = models.CharField(max_length=150)
    report_type = models.CharField(max_length=30, choices=ReportType.choices, blank=True)
    donor = models.ForeignKey(
        "projects.Donor",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="report_templates",
    )
    template_file_url = models.CharField(max_length=255, blank=True)
    configuration = models.JSONField(blank=True, null=True)

    class Meta:
        db_table = "report_templates"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Report(TrackedModel):
    class Status(models.TextChoices):
        DRAFT = "BROUILLON", "Brouillon"
        VALIDATED = "VALIDE", "Valide"
        PUBLISHED = "PUBLIE", "Publie"

    template = models.ForeignKey(
        ReportTemplate,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="reports",
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="reports",
    )
    title = models.CharField(max_length=200)
    period_start = models.DateField(blank=True, null=True)
    period_end = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    content = models.JSONField(blank=True, null=True)
    generated_file_url = models.CharField(max_length=255, blank=True)
    generated_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="generated_reports",
    )
    generated_at = models.DateTimeField(blank=True, null=True)
    validated_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="validated_reports",
    )
    validated_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "reports"
        ordering = ["-created_at", "title"]

    def __str__(self):
        return self.title


class ReportExport(TrackedModel):
    class ExportFormat(models.TextChoices):
        PDF = "PDF", "PDF"
        DOCX = "DOCX", "DOCX"
        XLSX = "XLSX", "XLSX"
        CSV = "CSV", "CSV"

    report = models.ForeignKey(Report, on_delete=models.CASCADE, related_name="exports")
    export_format = models.CharField(max_length=10, choices=ExportFormat.choices)
    file_url = models.CharField(max_length=255)
    exported_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="report_exports",
    )
    exported_at = models.DateTimeField(auto_now_add=True)
    checksum_sha256 = models.CharField(max_length=64, blank=True)

    class Meta:
        db_table = "report_exports"
        ordering = ["-exported_at"]

    def __str__(self):
        return f"{self.report} / {self.export_format}"
