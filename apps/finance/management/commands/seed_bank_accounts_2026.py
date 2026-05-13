"""
Cree les comptes bancaires EVE et les rattache aux projets. Renseigne
egalement les soldes d'ouverture au 01/01/2026 (= solde de cloture au
31/12/2025) lorsque le releve a ete fourni.

Source : inventaire confirme par EVE le 13/05/2026 + releves bancaires
au 31/12/2025 partages le meme jour.

Idempotente : update_or_create par nom de compte.
"""

from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.finance.models import BankAccount, BankAccountSnapshot
from apps.projects.models import Project


OPENING_DATE = date(2026, 1, 1)
CLOSING_DATE = date(2025, 12, 31)
RELEASE_SOURCE = "Releve bancaire au 31/12/2025"


# (account name, bank name, account_reference, opening_balance, notes, project_codes)
BANK_ACCOUNTS = [
    {
        "name": "Banque Atlantique",
        "bank_name": "Banque Atlantique",
        "account_reference": "84284780007",
        "opening_balance": Decimal("39870516.00"),
        "notes": (
            "Compte partage entre les projets Nous-Cims geres en commun "
            "(ECP, Pikine Phase II, GT Wallu Dome). Releve 12 au 31/12/2025 "
            "ancien solde 30/11/2025 = 48 671 944, mouvements debit 9 451 428, "
            "credit 650 000, nouveau solde 39 870 516."
        ),
        "project_codes": [
            "NOUSCIMS-ECP-2025",
            "NOUSCIMS-PIK-MBAO-2026",
            "NOUSCIMS-GT-WALLU-DOOM-2025",
        ],
    },
    {
        "name": "EVE-OXFAM",
        "bank_name": "SUNU BANK SENEGAL",
        "account_reference": "11667910006",  # IBAN SN08SN0100152001166791000622
        "opening_balance": Decimal("838196.00"),
        "notes": (
            "Compte SUNU Bank libelle 'EAU VIE ENVIRONNEMENT OXFAM', SICAP "
            "MBAO Villa 367. Anciennement BICIS, devenue SUNU BANK SENEGAL. "
            "Compte partage entre les projets ISF AXA Climate et ECO-AVENIR. "
            "Releve 31/12/2025 : dernier solde avant 01/12/2025 = 3 818 454, "
            "mouvements debit 6 119 810 / credit 3 139 552, nouveau solde au "
            "31/12/2025 = 838 196. IBAN : SN08SN0100152001166791000622. "
            "Gestionnaire SUNU : DIAKHATE Rose Marie."
        ),
        "project_codes": [
            "AXA-ISF-2026",
            "OGHOGHO-ECOAVENIR-2026",
        ],
    },
    {
        "name": "Budget General",
        "bank_name": "SUNU BANK SENEGAL",
        "account_reference": "11411670009",
        "opening_balance": Decimal("1253122.00"),
        "notes": (
            "Compte central EVE alimentant le Budget General : recoit les "
            "contributions des projets (virements 'CONTRIBUTION SUR SALAIRES "
            "STAFF...' et 'CONTRIBUTION SUR LA LOCATION 2 LES CHARGES FIXES') "
            "et regle les salaires personnel + charges fixes. SUNU Bank "
            "(ex-BICIS), client 141167. Releve 31/12/2025 : solde de depart "
            "01/12/2025 = 1 057 589, solde final 31/12/2025 = 1 253 122. "
            "Aucun projet rattache : ce compte est central et non dedie a un "
            "projet bailleur."
        ),
        "project_codes": [],  # Compte central, pas de rattachement projet
    },
    {
        "name": "EVE service",
        "bank_name": "CBAO",
        "account_reference": "36171795503-55",
        "opening_balance": Decimal("5888104.00"),
        "notes": (
            "Compte dedie au projet Saint-Louis Gouvernance Multisectorielle "
            "(Nous-Cims). Releve extrait a la demande 06/01/2026 pour la "
            "periode 01/01-31/12/2025, solde au 31/12/2025 = 5 888 104. "
            "Total general 2025 : debit 20 425 176 / credit 26 313 280."
        ),
        "project_codes": [
            "NOUSCIMS-SL-2026",
        ],
    },
    {
        "name": "EVE-SODIS",
        "bank_name": "SUNU BANK SENEGAL",
        "account_reference": "11172890011",  # IBAN SN08SN0100152001117289001195
        "opening_balance": Decimal("105476433.00"),
        "notes": (
            "Compte dedie au projet PDBH IEC ONAS-AFD. ONAS precompte la TVA "
            "18% : encaissements en HT. Releve SUNU Bank au 31/12/2025 : "
            "dernier solde avant 01/12/2025 = 126 838 932, mouvements decembre "
            "debit 21 362 932 / credit 433, nouveau solde au 31/12/2025 = "
            "105 476 433. IBAN : SN08SN0100152001117289001195."
        ),
        "project_codes": [
            "ONASAFD-PDBH-IEC-2025",
        ],
    },
    {
        "name": "EVE",
        "bank_name": "BOA",
        "account_reference": "06335290004",
        "opening_balance": Decimal("4988629.00"),
        "notes": (
            "Compte dedie au projet Reponse urgence inondations ChildFund/P&G. "
            "Releve BOA au 31/12/2025 : ancien solde 30/11/2025 = 87 678, "
            "mouvements debit 99 949 / credit 5 000 000, nouveau solde 4 988 629."
        ),
        "project_codes": [
            "CHILDFUND-INONDATIONS-2025",
        ],
    },
]


class Command(BaseCommand):
    help = (
        "Cree les comptes bancaires EVE et leurs rattachements aux projets. "
        "Idempotent."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write("Creation/mise a jour des comptes bancaires EVE...")
        for spec in BANK_ACCOUNTS:
            account, created = BankAccount.objects.update_or_create(
                name=spec["name"],
                defaults={
                    "bank_name": spec["bank_name"],
                    "opening_balance": spec["opening_balance"],
                    "opening_date": OPENING_DATE if spec["opening_balance"] is not None else None,
                    "currency": "XOF",
                    "notes": spec["notes"],
                },
            )
            action = "cree" if created else "mis a jour"

            projects = list(
                Project.objects.filter(
                    code__in=spec["project_codes"],
                    is_active=True,
                    deleted_at__isnull=True,
                )
            )
            found_codes = {p.code for p in projects}
            missing = set(spec["project_codes"]) - found_codes
            if missing:
                self.stderr.write(
                    f"  /!\\ Projects manquants pour '{spec['name']}': {sorted(missing)}"
                )

            account.projects.set(projects)
            balance_str = (
                f"{spec['opening_balance']} XOF"
                if spec["opening_balance"] is not None
                else "solde a renseigner"
            )
            self.stdout.write(
                f"  {account.name} ({account.bank_name}): {action}, "
                f"{len(projects)} projet(s) rattache(s), {balance_str}"
            )
        self.stdout.write(self.style.SUCCESS("Comptes bancaires traites."))
