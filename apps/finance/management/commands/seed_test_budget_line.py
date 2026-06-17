# -*- coding: utf-8 -*-
"""Garantit qu'un projet possede au moins UNE ligne budgetaire eligible.

Filet de securite pour le test du workflow de depense : `expense_create` impose
de choisir une `BudgetLine` active, or il n'existe pas (encore) d'ecran de
creation manuelle de ligne. Cette commande cree, si besoin, une ligne
« Formation et renforcement de capacites » sur le projet choisi.

Idempotent : reperee par (projet, code FORM-CLIMAT-TEST), un re-run ne duplique
pas. Par defaut le projet climat OGHOGHO-ECOAVENIR-2026.

Usage :
  manage.py seed_test_budget_line
  manage.py seed_test_budget_line --project AXA-ISF-2026 --amount 2000000
  manage.py seed_test_budget_line --project BG          # ligne Budget General
"""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.finance.models import BudgetLine
from apps.projects.models import Project
from apps.references.models import BudgetCategory

LINE_CODE = "FORM-CLIMAT-TEST"


class Command(BaseCommand):
    help = "Cree une ligne budgetaire de test (formation) si le projet n'en a pas."

    def add_arguments(self, parser):
        parser.add_argument("--project", default="OGHOGHO-ECOAVENIR-2026",
                            help="Code projet (ou 'BG' pour le Budget General).")
        parser.add_argument("--amount", type=str, default="1500000",
                            help="Montant prevu de la ligne (XOF).")
        parser.add_argument("--description",
                            default="Formation thematique climat - test pilote")

    @transaction.atomic
    def handle(self, *args, **opts):
        code = opts["project"].strip()
        if code.upper() == "BG":
            project = None
            label = "Budget General (BG)"
        else:
            project = Project.objects.filter(
                code=code, is_active=True, deleted_at__isnull=True
            ).first()
            if project is None:
                avail = ", ".join(
                    Project.objects.filter(is_active=True, deleted_at__isnull=True)
                    .order_by("code").values_list("code", flat=True)
                )
                self.stderr.write(self.style.ERROR(
                    f"Projet '{code}' introuvable. Projets disponibles : {avail}"
                ))
                return
            label = project.code

        existing = BudgetLine.objects.filter(
            project=project, is_active=True, deleted_at__isnull=True
        )
        if existing.exists() and not BudgetLine.objects.filter(
            project=project, code=LINE_CODE
        ).exists():
            self.stdout.write(self.style.SUCCESS(
                f"{label} a deja {existing.count()} ligne(s) budgetaire(s) active(s) : "
                f"rien a creer, le test peut utiliser l'une d'elles."
            ))
            return

        category, _ = BudgetCategory.objects.get_or_create(
            code="FORM",
            defaults={"name": "Formation et renforcement de capacites"},
        )

        line, created = BudgetLine.objects.update_or_create(
            project=project, code=LINE_CODE,
            defaults={
                "category": category,
                "description": opts["description"][:200],
                "planned_amount": Decimal(opts["amount"]),
                "currency": "XOF",
                "fiscal_year": 2026,
                "is_active": True,
                "deleted_at": None,
            },
        )
        verb = "creee" if created else "mise a jour"
        self.stdout.write(self.style.SUCCESS(
            f"Ligne budgetaire {verb} sur {label} : "
            f"[{line.code}] {line.description} - {line.planned_amount:.0f} XOF."
        ))
