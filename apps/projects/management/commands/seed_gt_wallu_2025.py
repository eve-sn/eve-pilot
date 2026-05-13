"""
Cree le projet GT Wallu Dome (Groupe Thematique Nous-Cims).

Source de verite :
- Convention : EVE Conveni entitats para GT_signe-eve-15072025_FR.pdf (signature 15/07/2025)
- Budget detaille : budget Campagne Wallu_GT.xlsx (TOTAL BUDGET ACTIVITES = 3 279 785 FCFA)
- Encaissement deja documente dans le Budget Previsionnel onglet 6 : 12/08/2025
  "Groupe Thematique Wallu Dome" = 3 279 785 FCFA depuis Fondation Nous-Cims.

Le projet n'est PAS dans le portefeuille du Budget Previsionnel 2026 (onglet 6)
car il est ponctuel (campagne courte) et lance / clos en 2025. Cette commande
est donc dediee, hors de import_budget_2026.

Idempotente : update_or_create par code projet.
"""

from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.projects.models import Donor, Project


PROJECT_CODE = "NOUSCIMS-GT-WALLU-DOOM-2025"
DONOR_NAME = "Fondation Nous-Cims"


class Command(BaseCommand):
    help = "Cree le projet Wallu Dome (GT Nous-Cims) avec son budget et son rattachement bailleur."

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            donor = Donor.objects.get(
                name=DONOR_NAME, is_active=True, deleted_at__isnull=True
            )
        except Donor.DoesNotExist:
            self.stderr.write(
                f"Donor '{DONOR_NAME}' introuvable. Lancer import_rh_reference_2026 "
                "ou import_budget_2026 au prealable."
            )
            return

        defaults = {
            "title": "Campagne Wallu Dome - Groupe Thematique Nutrition (Nous-Cims)",
            "short_title": "Wallu Dome GT",
            "description": (
                "Campagne de communication et de mobilisation autour de la nutrition "
                "infantile, portee par le Groupe Thematique. Budget detaille dans "
                "'budget Campagne Wallu_GT.xlsx' (TOTAL BUDGET = 3 279 785 FCFA). "
                "Encaissement Nous-Cims documente le 12/08/2025 (Budget Previsionnel "
                "2026 onglet 6, section Encaissements). Convention signee le 15/07/2025."
            ),
            "primary_donor": donor,
            "total_budget": Decimal("3279785.00"),
            "currency": "XOF",
            "start_date": date(2025, 7, 15),
            "end_date": date(2025, 12, 31),
            "status": Project.Status.ACTIVE,
            "sector": "NUTRITION",
            "progress_percentage": Decimal("0.00"),
        }
        project, created = Project.objects.update_or_create(
            code=PROJECT_CODE, defaults=defaults
        )
        action = "cree" if created else "mis a jour"
        self.stdout.write(
            self.style.SUCCESS(
                f"Project {PROJECT_CODE}: {action} "
                f"(budget {defaults['total_budget']} XOF, bailleur {donor.name})"
            )
        )
