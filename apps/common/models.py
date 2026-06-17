import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class PublicUUIDModel(models.Model):
    public_uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    class Meta:
        abstract = True


class SoftDeleteModel(models.Model):
    is_active = models.BooleanField(default=True)
    deleted_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        abstract = True

    def soft_delete(self):
        self.is_active = False
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_active", "deleted_at", "updated_at"])


class AuditFieldsModel(models.Model):
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="+",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="+",
    )

    class Meta:
        abstract = True


class TrackedModel(PublicUUIDModel, SoftDeleteModel, TimeStampedModel, AuditFieldsModel):
    class Meta:
        abstract = True


class Feedback(TrackedModel):
    """Retour d'un utilisateur depuis le tableau de bord (test pilote).

    L'auteur est porte par created_by (renseigne dans la vue). On garde la page
    d'origine pour situer le retour, et un statut de traitement pour le suivi RAF.
    """

    class Category(models.TextChoices):
        BUG = "BUG", "Anomalie / bug"
        IDEA = "IDEA", "Suggestion / amelioration"
        QUESTION = "QUESTION", "Question"
        OTHER = "OTHER", "Autre"

    class Status(models.TextChoices):
        NEW = "NEW", "Nouveau"
        SEEN = "SEEN", "Vu"
        DONE = "DONE", "Traite"

    category = models.CharField(max_length=20, choices=Category.choices, default=Category.IDEA)
    page = models.CharField(max_length=200, blank=True, help_text="Page/ecran concerne.")
    message = models.TextField()
    rating = models.PositiveSmallIntegerField(
        blank=True, null=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Satisfaction 1 a 5 (facultatif).",
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.NEW)

    class Meta:
        db_table = "feedbacks"
        ordering = ["-id"]

    def __str__(self):
        return f"{self.get_category_display()} - {self.message[:40]}"
