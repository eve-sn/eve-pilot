"""
Seed du compte bancaire 'TEST-SIMULATION' dedie aux tests de procedure
EVE Pilot (formation climat, achat equipement, supervision terrain,
fonctionnement, petite caisse).

Cree :
  - Un BankAccount fictif 'TEST-SIMULATION' avec opening_balance = 10M FCFA
  - Un ChartOfAccount 5211.99 lie a ce BankAccount

Permet de tester le circuit complet d'une depense (demande -> validation ->
engagement -> decaissement -> ecritures SYCEBNL Dr 6xxx / Cr 5211.99 +
neutralisation Dr 462 / Cr 702) sans polluer la balance des comptes
operationnels reels (5211.10 ... 5211.60).

Idempotente : update_or_create.

Apres chaque simulation, les mouvements peuvent etre annules via le bouton
'Annuler' du detail du compte (cf. bank_movement_delete).
"""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.finance.models import BankAccount, ChartOfAccount


class Command(BaseCommand):
    help = (
        "Cree le compte bancaire TEST-SIMULATION et son ChartOfAccount 5211.99 "
        "dedies aux tests de procedure SYCEBNL dans EVE Pilot."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        # 1. BankAccount fictif
        bank, created = BankAccount.objects.update_or_create(
            name="TEST-SIMULATION",
            defaults={
                "bank_name": "Banque fictive pour simulations UAT",
                "opening_balance": Decimal("10000000"),
                "currency": "XOF",
                "notes": (
                    "Compte EVE Pilot dedie EXCLUSIVEMENT aux tests de "
                    "procedure SYCEBNL (formation climat, achat equipement, "
                    "supervision terrain, fonctionnement, petite caisse). "
                    "Aucun decaissement reel - les ecritures generees sur ce "
                    "compte n'apparaissent pas dans la balance des comptes "
                    "operationnels."
                ),
            },
        )
        self.stdout.write(
            f"BankAccount : {'cree' if created else 'mis a jour'} "
            f"id={bank.id} name='{bank.name}'"
        )

        # 2. ChartOfAccount 5211.99 lie a ce BankAccount
        parent_5211 = ChartOfAccount.objects.filter(code="5211").first()
        if parent_5211 is None:
            self.stderr.write(self.style.WARNING(
                "Compte parent 5211 introuvable. Lancer d'abord "
                "seed_chart_of_accounts_official."
            ))
            return

        acc, created = ChartOfAccount.objects.update_or_create(
            code="5211.99",
            defaults={
                "name": "Compte de tresorerie TEST-SIMULATION (UAT)",
                "class_number": 5,
                "parent": parent_5211,
                "linked_bank_account": bank,
                "description": (
                    "Sous-compte SYCEBNL dedie aux ecritures de test. Permet "
                    "de tester le posting.py et les rapports sans polluer la "
                    "balance reelle des 5211.10..5211.60."
                ),
            },
        )
        self.stdout.write(
            f"ChartOfAccount : {'cree' if created else 'mis a jour'} "
            f"code={acc.code}"
        )

        self.stdout.write(self.style.SUCCESS(
            "\nOK. La banque 'TEST-SIMULATION' est disponible dans /finance/banque/saisir/ "
            "et dans /finance/banque/import-releve/.\n"
            "Solde d'ouverture fictif : 10 000 000 FCFA."
        ))
