"""
Seed de la ligne budgetaire analytique unique du projet AXA-ISF-2026.

Une seule ligne (arbitrage utilisateur) : "Activites mises en oeuvre par EVE"
Categorie PROJ_PRESTATION (contrat de prestation expertise + frais de gestion).

Idempotent.
"""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.finance.models import BudgetLine
from apps.projects.models import Project
from apps.references.models import BudgetCategory


PROJECT_CODE = "AXA-ISF-2026"


class Command(BaseCommand):
    help = "Cree la ligne budgetaire unique du projet AXA Climate ISF 2026."

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            project = Project.objects.get(
                code=PROJECT_CODE, is_active=True, deleted_at__isnull=True
            )
        except Project.DoesNotExist:
            self.stderr.write(f"Project {PROJECT_CODE} introuvable.")
            return

        category, _ = BudgetCategory.objects.update_or_create(
            code="PROJ_PRESTATION",
            defaults={"name": "Prestations professionnelles (projet)"},
        )

        line, was_created = BudgetLine.objects.update_or_create(
            code="AXA-ISF-ACTIVITES-2026",
            project=project,
            defaults={
                "category": category,
                "description": "Activites mises en oeuvre par EVE",
                "currency": "XOF",
                "fiscal_year": 2026,
                "planned_amount": Decimal("0"),
            },
        )
        action = "creee" if was_created else "mise a jour"
        self.stdout.write(
            self.style.SUCCESS(
                f"BudgetLine AXA-ISF-ACTIVITES-2026 ({project.code}) : {action}."
            )
        )
