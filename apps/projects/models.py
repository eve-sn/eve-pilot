from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.common.models import TimeStampedModel, TrackedModel


class Donor(TrackedModel):
    class DonorType(models.TextChoices):
        MULTILATERAL = "MULTILATERAL", "Multilateral"
        BILATERAL = "BILATERAL", "Bilateral"
        FOUNDATION = "FOUNDATION", "Foundation"
        COMPANY = "COMPANY", "Company"
        INDIVIDUAL = "INDIVIDUAL", "Individual"
        GOVERNMENT = "GOVERNMENT", "Government"
        OTHER = "OTHER", "Other"

    name = models.CharField(max_length=150, unique=True)
    short_name = models.CharField(max_length=30, blank=True)
    donor_type = models.CharField(max_length=30, choices=DonorType.choices, blank=True)
    country = models.CharField(max_length=50, blank=True)
    contact_person = models.CharField(max_length=150, blank=True)
    email = models.EmailField(max_length=120, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    website = models.URLField(max_length=200, blank=True)
    logo_url = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "donors"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Project(TrackedModel):
    class Status(models.TextChoices):
        PREPARATION = "PREPARATION", "Preparation"
        ACTIVE = "ACTIF", "Actif"
        SUSPENDED = "SUSPENDU", "Suspendu"
        CLOSED = "CLOTURE", "Cloture"
        ARCHIVED = "ARCHIVE", "Archive"

    code = models.CharField(max_length=30, unique=True)
    title = models.CharField(max_length=200)
    short_title = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True)
    primary_donor = models.ForeignKey(
        Donor,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="primary_projects",
    )
    total_budget = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)
    currency = models.CharField(max_length=3, default="XOF")
    start_date = models.DateField()
    end_date = models.DateField()
    project_manager = models.ForeignKey(
        "hr.Employee",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="managed_projects",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PREPARATION)
    sector = models.CharField(max_length=50, blank=True)
    objectives = models.TextField(blank=True)
    target_beneficiaries = models.PositiveIntegerField(blank=True, null=True)
    logo_url = models.CharField(max_length=255, blank=True)
    progress_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    class Meta:
        db_table = "projects"
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} - {self.title}"


class ProjectDonor(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="co_funders")
    donor = models.ForeignKey(Donor, on_delete=models.RESTRICT, related_name="co_funded_projects")
    contribution_amount = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)
    contribution_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    class Meta:
        db_table = "project_donors"
        unique_together = ("project", "donor")

    def __str__(self):
        return f"{self.project.code} / {self.donor.name}"


class ProjectTeam(TrackedModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="team_assignments")
    employee = models.ForeignKey("hr.Employee", on_delete=models.RESTRICT, related_name="project_assignments")
    role = models.CharField(max_length=60, blank=True)
    allocation_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)

    class Meta:
        db_table = "project_teams"
        ordering = ["project__code", "employee__last_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "employee", "start_date"],
                name="uq_project_teams_assignment",
            )
        ]

    def __str__(self):
        return f"{self.project.code} / {self.employee}"


class ProjectLocation(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="locations")
    commune = models.ForeignKey("references.Commune", on_delete=models.RESTRICT, related_name="project_locations")

    class Meta:
        db_table = "project_locations"
        unique_together = ("project", "commune")

    def __str__(self):
        return f"{self.project.code} / {self.commune.name}"


class Indicator(TrackedModel):
    class IndicatorType(models.TextChoices):
        OUTPUT = "OUTPUT", "Output"
        OUTCOME = "OUTCOME", "Outcome"
        IMPACT = "IMPACT", "Impact"

    class Frequency(models.TextChoices):
        WEEKLY = "HEBDOMADAIRE", "Hebdomadaire"
        MONTHLY = "MENSUEL", "Mensuel"
        QUARTERLY = "TRIMESTRIEL", "Trimestriel"
        SEMIANNUAL = "SEMESTRIEL", "Semestriel"
        YEARLY = "ANNUEL", "Annuel"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="indicators")
    code = models.CharField(max_length=20, blank=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    unit = models.CharField(max_length=30, blank=True)
    indicator_type = models.CharField(max_length=20, choices=IndicatorType.choices, blank=True)
    baseline_value = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)
    target_value = models.DecimalField(max_digits=14, decimal_places=2)
    current_value = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    achievement_rate = models.DecimalField(max_digits=7, decimal_places=2, blank=True, null=True, editable=False)
    frequency = models.CharField(max_length=20, choices=Frequency.choices, blank=True)
    disaggregation = models.CharField(max_length=100, blank=True)
    data_source = models.CharField(max_length=150, blank=True)

    class Meta:
        db_table = "indicators"
        ordering = ["project__code", "code", "name"]

    def save(self, *args, **kwargs):
        if self.target_value and self.target_value != 0:
            self.achievement_rate = (self.current_value / self.target_value) * 100
        else:
            self.achievement_rate = None
        super().save(*args, **kwargs)

    def __str__(self):
        return self.code or self.name


class IndicatorValue(TrackedModel):
    indicator = models.ForeignKey(Indicator, on_delete=models.CASCADE, related_name="values")
    period_start = models.DateField(blank=True, null=True)
    period_end = models.DateField(blank=True, null=True)
    value = models.DecimalField(max_digits=14, decimal_places=2)
    notes = models.TextField(blank=True)
    evidence_url = models.CharField(max_length=255, blank=True)
    recorded_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="recorded_indicator_values",
    )
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "indicator_values"
        ordering = ["-recorded_at"]

    def __str__(self):
        return f"{self.indicator} / {self.value}"
