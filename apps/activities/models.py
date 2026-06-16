from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.common.models import TrackedModel


class Activity(TrackedModel):
    class Status(models.TextChoices):
        PLANNED = "PLANIFIE", "Planifie"
        IN_PROGRESS = "EN_COURS", "En cours"
        COMPLETED = "REALISE", "Realise"
        CANCELED = "ANNULE", "Annule"

    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="activities")
    code = models.CharField(max_length=30, blank=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    activity_type = models.CharField(max_length=40, blank=True)
    planned_start_date = models.DateField(
        blank=True,
        null=True,
        help_text=(
            "Date de debut prevue. Peut etre vide pour une activite issue d'un "
            "cadre logique non encore calendarise ; la saisie manuelle l'exige."
        ),
    )
    planned_end_date = models.DateField(blank=True, null=True)
    planned_budget = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    responsible = models.ForeignKey(
        "hr.Employee",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="responsible_activities",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PLANNED)
    completion_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "activities"
        ordering = ["project__code", "planned_start_date", "title"]

    def __str__(self):
        return self.title


class ActivityLocation(models.Model):
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name="locations")
    commune = models.ForeignKey("references.Commune", on_delete=models.RESTRICT, related_name="activity_locations")

    class Meta:
        db_table = "activity_locations"
        unique_together = ("activity", "commune")

    def __str__(self):
        return f"{self.activity.title} / {self.commune.name}"


class ActivityReport(TrackedModel):
    class ValidationStatus(models.TextChoices):
        SUBMITTED = "SOUMIS", "Soumis"
        VALIDATED = "VALIDE", "Valide"
        REJECTED = "REJETE", "Rejete"

    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name="reports")
    report_date = models.DateField()
    actual_location = models.CharField(max_length=200, blank=True)
    commune = models.ForeignKey(
        "references.Commune",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="activity_reports",
    )
    gps_latitude = models.DecimalField(max_digits=10, decimal_places=6, blank=True, null=True)
    gps_longitude = models.DecimalField(max_digits=10, decimal_places=6, blank=True, null=True)
    participants_count = models.PositiveIntegerField(blank=True, null=True)
    male_count = models.PositiveIntegerField(blank=True, null=True)
    female_count = models.PositiveIntegerField(blank=True, null=True)
    children_count = models.PositiveIntegerField(blank=True, null=True)
    narrative = models.TextField(blank=True)
    outcomes = models.TextField(blank=True)
    challenges = models.TextField(blank=True)
    recommendations = models.TextField(blank=True)
    reported_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="submitted_activity_reports",
    )
    validated_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="validated_activity_reports",
    )
    validation_status = models.CharField(
        max_length=20,
        choices=ValidationStatus.choices,
        default=ValidationStatus.SUBMITTED,
    )
    validation_comment = models.TextField(
        blank=True,
        help_text="Commentaire du valideur (Secretaire Executif), notamment en cas de rejet.",
    )
    validated_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "activity_reports"
        ordering = ["-report_date", "-created_at"]

    def __str__(self):
        return f"{self.activity.title} / {self.report_date}"


def _activity_evidence_upload_to(instance, filename):
    """Range les preuves sous media/activity_evidences/<report_id>/."""
    rid = instance.activity_report_id or "draft"
    return f"activity_evidences/{rid}/{filename}"


class ActivityEvidence(TrackedModel):
    class EvidenceType(models.TextChoices):
        PHOTO = "PHOTO", "Photo"
        PRESENCE_LIST = "PRESENCE_LIST", "Presence list"
        DOCUMENT = "DOCUMENT", "Document"
        VIDEO = "VIDEO", "Video"
        AUDIO = "AUDIO", "Audio"
        GPS = "GPS", "GPS"

    activity_report = models.ForeignKey(
        ActivityReport,
        on_delete=models.CASCADE,
        related_name="evidences",
    )
    evidence_type = models.CharField(max_length=20, choices=EvidenceType.choices, blank=True)
    file = models.FileField(upload_to=_activity_evidence_upload_to)
    caption = models.CharField(max_length=200, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "activity_evidences"
        ordering = ["-uploaded_at"]

    def __str__(self):
        return self.caption or self.file_url


class Beneficiary(TrackedModel):
    class Gender(models.TextChoices):
        MALE = "M", "Male"
        FEMALE = "F", "Female"

    activity_report = models.ForeignKey(
        ActivityReport,
        on_delete=models.CASCADE,
        related_name="beneficiaries",
    )
    last_name = models.CharField(max_length=80)
    first_name = models.CharField(max_length=80)
    gender = models.CharField(max_length=1, choices=Gender.choices, blank=True)
    age = models.PositiveIntegerField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True)
    commune = models.ForeignKey(
        "references.Commune",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="beneficiaries",
    )
    id_card_number = models.CharField(max_length=30, blank=True)
    signature_url = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "beneficiaries"
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"
