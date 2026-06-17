# -*- coding: utf-8 -*-
"""Prepare le projet ECO-AVENIR pour le test du workflow de depense.

Choix valide : on teste la depense sur un PROJET (et non le Budget General),
pour qu'un CHARGE_SUIVI puisse etre le demandeur (le BG est reserve aux roles a
acces global / ARAF). ECO-AVENIR est le projet climat, cible naturelle de la
formation climat.

La commande, idempotente et a empreinte minimale (elle ne deverse pas les 8
projets-bailleurs), garantit sur la base courante :
  1. le bailleur Donor 'Oghogho Meye / La Locomotiva' ;
  2. le projet OGHOGHO-ECOAVENIR-2026 (ACTIF, vraie description, primary_donor) ;
  3. le rattachement a la banque EVE-OXFAM (SUNU BANK) pour le decaissement ;
  4. une ligne budgetaire eligible (FORM-CLIMAT-TEST) ;
  5. le rattachement du demandeur (CHARGE_SUIVI) via ProjectTeam, sinon il ne
     verrait pas le projet et ne pourrait pas creer la demande.

Usage :
  manage.py setup_test_ecoavenir
  manage.py setup_test_ecoavenir --requester maguevedrame --amount 1500000
"""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import User
from apps.finance.models import BankAccount, BudgetLine
from apps.projects.models import Donor, Project, ProjectTeam
from apps.references.models import BudgetCategory

PROJECT_CODE = "OGHOGHO-ECOAVENIR-2026"
PROJECT_TITLE = (
    "Enfants et jeunes, acteurs des processus de resilience au changement "
    "climatique a Pikine et ses environs (Dakar, Senegal)"
)
DONOR_NAME = "Oghogho Meye / La Locomotiva"
BANK_NAME = "EVE-OXFAM"
LINE_CODE = "FORM-CLIMAT-TEST"


class Command(BaseCommand):
    help = "Prepare le projet ECO-AVENIR (climat) pour le test de depense."

    def add_arguments(self, parser):
        parser.add_argument("--requester", default="maguevedrame",
                            help="Username du CHARGE_SUIVI demandeur a rattacher au projet.")
        parser.add_argument("--amount", default="1500000",
                            help="Montant prevu de la ligne budgetaire de test (XOF).")

    @transaction.atomic
    def handle(self, *args, **opts):
        # 1) Bailleur
        donor, _ = Donor.objects.get_or_create(
            name=DONOR_NAME,
            defaults={"short_name": "La Locomotiva", "donor_type": Donor.DonorType.FOUNDATION},
        )

        # 2) Projet
        project, created = Project.objects.update_or_create(
            code=PROJECT_CODE,
            defaults={
                "title": PROJECT_TITLE[:200],
                "short_title": "ECO-AVENIR",
                "status": Project.Status.ACTIVE,
                "start_date": "2026-01-01",
                "end_date": "2026-12-31",
                "primary_donor": donor,
                "currency": "XOF",
                "is_active": True,
                "deleted_at": None,
            },
        )
        self.stdout.write(self.style.SUCCESS(
            f"Projet {PROJECT_CODE} {'cree' if created else 'mis a jour'} (ACTIF)."
        ))

        # 3) Banque SUNU BANK (EVE-OXFAM)
        bank = BankAccount.objects.filter(
            name=BANK_NAME, is_active=True, deleted_at__isnull=True
        ).first()
        if bank:
            project.bank_accounts.add(bank)
            self.stdout.write(f"  Banque rattachee : {BANK_NAME} (SUNU BANK).")
        else:
            self.stderr.write(
                f"  /!\\ Banque '{BANK_NAME}' introuvable : lancer seed_bank_accounts_2026 "
                "pour le decaissement SUNU BANK."
            )

        # 4) Ligne budgetaire eligible
        category, _ = BudgetCategory.objects.get_or_create(
            code="FORM", defaults={"name": "Formation et renforcement de capacites"},
        )
        line, line_created = BudgetLine.objects.update_or_create(
            project=project, code=LINE_CODE,
            defaults={
                "category": category,
                "description": "Formation thematique climat - test pilote",
                "planned_amount": Decimal(opts["amount"]),
                "currency": "XOF",
                "fiscal_year": 2026,
                "is_active": True,
                "deleted_at": None,
            },
        )
        self.stdout.write(
            f"  Ligne budgetaire [{line.code}] {'creee' if line_created else 'a jour'} "
            f"- {line.planned_amount:.0f} XOF."
        )

        # 5) Rattachement du demandeur (CHARGE_SUIVI) via ProjectTeam
        username = opts["requester"]
        user = User.objects.filter(username=username).first()
        if user is None:
            self.stderr.write(self.style.WARNING(
                f"  /!\\ Utilisateur '{username}' introuvable : aucun demandeur rattache."
            ))
        elif not user.employee_id:
            self.stderr.write(self.style.WARNING(
                f"  /!\\ '{username}' n'est pas lie a une fiche Employee : lancer "
                "link_users_employees, puis relancer cette commande."
            ))
        else:
            team, team_created = ProjectTeam.objects.get_or_create(
                project=project, employee=user.employee, start_date=None,
                defaults={"role": "Charge de suivi (demandeur test)", "is_active": True},
            )
            self.stdout.write(self.style.SUCCESS(
                f"  Demandeur rattache : {username} -> {user.employee} "
                f"({'nouveau' if team_created else 'deja en equipe'})."
            ))

        self.stdout.write(self.style.SUCCESS(
            "\nProjet ECO-AVENIR pret. Le demandeur peut creer la demande sur ce projet "
            "et la payer via SUNU BANK (EVE-OXFAM)."
        ))
