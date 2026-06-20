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


class SoftDeleteQuerySet(models.QuerySet):
    """QuerySet des modeles soft-deletables, avec accesseurs explicites."""

    def active(self):
        """Seulement les enregistrements vivants (actifs et non supprimes).

        Equivalent canonique du `.filter(is_active=True, deleted_at__isnull=True)`
        (alias ACTIVE_DOMAIN) dissemine dans les vues et commandes.
        """
        return self.filter(is_active=True, deleted_at__isnull=True)

    def deleted(self):
        """Seulement les enregistrements soft-deletes."""
        return self.filter(deleted_at__isnull=False)


class SoftDeleteManager(models.Manager.from_queryset(SoftDeleteQuerySet)):
    """Manager par defaut des TrackedModel.

    IMPORTANT - choix volontaire : get_queryset() renvoie TOUS les
    enregistrements, y compris les soft-deletes, EXACTEMENT comme le manager
    Django par defaut. On ne change donc PAS le comportement existant (admin,
    get_or_create / update_or_create des commandes de seed, acces via cles
    etrangeres, migrations restent intacts). On ajoute seulement les accesseurs
    .active() / .deleted() pour remplacer progressivement les filtres manuels
    `is_active=True, deleted_at__isnull=True` epars dans le code.

    Filtrer par defaut casserait notamment le re-seed : update_or_create ne
    retrouverait plus un enregistrement soft-delete et tenterait un INSERT en
    doublon (IntegrityError sur les champs unique).
    """


class SoftDeleteModel(models.Model):
    is_active = models.BooleanField(default=True)
    deleted_at = models.DateTimeField(blank=True, null=True)

    # Manager unique nomme `objects` : conserve le comportement par defaut
    # (tous les enregistrements) et expose .active()/.deleted(). Les modeles
    # avec un manager custom (ex. User/UserManager) le surchargent sans conflit.
    objects = SoftDeleteManager()

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
