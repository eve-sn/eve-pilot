"""
Cree les comptes bancaires EVE et les rattache aux projets.

Source : inventaire confirme par EVE le 13/05/2026.
- Banque Atlantique : NOUSCIMS-ECP-2025, NOUSCIMS-PIK-MBAO-2026, NOUSCIMS-GT-WALLU-DOOM-2025
- EVE-OXFAM (SUNU BANK SENEGAL, ex-BICIS) : AXA-ISF-2026, OGHOGHO-ECOAVENIR-2026
- EVE service (CBAO) : NOUSCIMS-SL-2026
- EVE-SODIS (SUNU BANK SENEGAL, ex-BICIS) : ONASAFD-PDBH-IEC-2025
- EVE (BOA) : CHILDFUND-INONDATIONS-2025

Les projets PNBSF-DAK-2026 et PNBSF-KED-2026 n'ont pas encore de compte
ouvert (status PREPARATION, contrats non signes) - aucun rattachement.

Solde d'ouverture : laisse a None pour l'instant. A renseigner via un edit
de ce fichier ou via /admin/ une fois les soldes au 01/01/2026 fournis.

Idempotente : update_or_create par nom de compte.
"""

from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.finance.models import BankAccount
from apps.projects.models import Project


OPENING_DATE = date(2026, 1, 1)


# (account name, bank name, opening_balance, notes, project_codes)
BANK_ACCOUNTS = [
    {
        "name": "Banque Atlantique",
        "bank_name": "Banque Atlantique",
        "opening_balance": None,
        "notes": (
            "Compte partage entre les projets Nous-Cims geres en commun. "
            "Solde au 01/01/2026 a renseigner."
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
        "opening_balance": None,
        "notes": (
            "Anciennement BICIS, devenue SUNU BANK SENEGAL. Compte partage "
            "entre les projets ISF AXA Climate et ECO-AVENIR. Solde au "
            "01/01/2026 a renseigner."
        ),
        "project_codes": [
            "AXA-ISF-2026",
            "OGHOGHO-ECOAVENIR-2026",
        ],
    },
    {
        "name": "EVE service",
        "bank_name": "CBAO",
        "opening_balance": None,
        "notes": (
            "Compte dedie au projet Saint-Louis Gouvernance Multisectorielle "
            "(Nous-Cims). Solde au 01/01/2026 a renseigner."
        ),
        "project_codes": [
            "NOUSCIMS-SL-2026",
        ],
    },
    {
        "name": "EVE-SODIS",
        "bank_name": "SUNU BANK SENEGAL",
        "opening_balance": None,
        "notes": (
            "Compte dedie au projet PDBH IEC ONAS-AFD. ONAS precompte la TVA "
            "18% : encaissements en HT. Solde au 01/01/2026 a renseigner."
        ),
        "project_codes": [
            "ONASAFD-PDBH-IEC-2025",
        ],
    },
    {
        "name": "EVE",
        "bank_name": "BOA",
        "opening_balance": None,
        "notes": (
            "Compte dedie au projet Reponse urgence inondations ChildFund/P&G. "
            "Solde au 01/01/2026 a renseigner."
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
