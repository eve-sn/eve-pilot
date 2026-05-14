"""
Seed du plan de comptes SYCEBNL EVE.

Cree :
  - Les comptes de regroupement (181, 512, 571, 6x, 7x).
  - Un sous-compte 181.x par projet actif EVE (lie via linked_project).
  - Un sous-compte 512.x par BankAccount EVE (lie via linked_bank_account).
  - Un sous-compte 571.x pour la caisse centrale (lie via linked_cash_register).
  - Les comptes principaux 6x (charges) et 7x (produits) utilises a date.

Idempotente : update_or_create par code SYCEBNL.

Cette commande complete le plan a chaque execution ; les sous-comptes
projets sont generes a partir de la liste des Project actifs en base
(et non d'un mapping en dur), donc l'ajout d'un nouveau projet declenche
automatiquement la creation de son compte 181.x.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.finance.models import BankAccount, CashRegister, ChartOfAccount
from apps.projects.models import Project


ROOT_ACCOUNTS = [
    # Classe 1 - Fonds propres et fonds dedies
    {"code": "18", "name": "Comptes de liaison et fonds dedies", "class_number": 1},
    {"code": "181", "name": "Comptes de liaison projets EVE", "class_number": 1, "parent_code": "18"},

    # Classe 5 - Tresorerie
    {"code": "51", "name": "Tresorerie - Banques", "class_number": 5},
    {"code": "512", "name": "Comptes bancaires en devises locales", "class_number": 5, "parent_code": "51"},
    {"code": "57", "name": "Caisse", "class_number": 5},
    {"code": "571", "name": "Caisse principale", "class_number": 5, "parent_code": "57"},

    # Classe 6 - Charges
    {"code": "60", "name": "Achats et variations de stocks", "class_number": 6},
    {"code": "61", "name": "Services exterieurs", "class_number": 6},
    {"code": "62", "name": "Autres services exterieurs", "class_number": 6},
    {"code": "63", "name": "Impots et taxes", "class_number": 6, "description": "Inclut VRS, BRS, ISR, TRIMF, CFCE."},
    {"code": "64", "name": "Charges de personnel", "class_number": 6, "description": "Salaires, IPRES, CSS, perdiem, IPM."},
    {"code": "65", "name": "Autres charges", "class_number": 6, "description": "Charges diverses non rattachees."},
    {"code": "66", "name": "Charges financieres", "class_number": 6, "description": "Frais bancaires, commissions, agios."},
    {"code": "67", "name": "Subventions et appuis verses", "class_number": 6, "description": "Appuis et subventions decaisses aux beneficiaires."},

    # Classe 7 - Produits
    {"code": "75", "name": "Subventions et dons recus", "class_number": 7, "description": "Subventions bailleurs (Nous-Cims, ONAS, AXA, ChildFund, Oghogho, etc.)."},
    {"code": "77", "name": "Produits financiers", "class_number": 7},
]


# Mapping nom interne BankAccount -> code SYCEBNL 512.x souhaite
BANK_TO_CODE = {
    "Banque Atlantique": ("512.10", "Banque Atlantique - EVE"),
    "EVE-OXFAM": ("512.20", "SUNU BANK - EVE-OXFAM (AXA + ECO)"),
    "EVE service": ("512.30", "CBAO - EVE service (Saint-Louis)"),
    "EVE-SODIS": ("512.40", "SUNU BANK - EVE-SODIS (ONAS PDBH)"),
    "EVE": ("512.50", "BOA - EVE (ChildFund)"),
    "Budget General": ("512.60", "SUNU BANK - Budget General"),
}


# Mapping nom CashRegister -> code SYCEBNL 571.x souhaite
CASH_REGISTER_TO_CODE = {
    "Caisse centrale BG": ("571.00", "Caisse centrale BG"),
}


# Comptes de liaison "speciaux" : projets clos ou hors-perimetre base dont
# le reliquat continue de circuler. Pas de linked_project (le Project
# n'existe pas en base).
EXTRA_LIAISON_ACCOUNTS = [
    {
        "code": "181.110",
        "name": "Liaison Pikine Phase I (cloture - reliquat)",
        "description": (
            "Compte de liaison du projet AGIR Pikine Phase I, cloture en "
            "fevrier 2026 et donc hors base Project. Son reliquat continue de "
            "transiter par le Budget General en 2026."
        ),
    },
]


def _suffix_for_project(index):
    """Genere un suffixe sur 3 chiffres (010, 020, ..., 100) pour assurer un
    tri lexicographique stable jusqu'a 9 projets (au-dela passer en 4 chiffres)."""
    return f"{(index + 1) * 10:03d}"


class Command(BaseCommand):
    help = "Cree / met a jour le plan de comptes SYCEBNL EVE."

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write("Seed plan comptable SYCEBNL EVE...")

        # 1) Comptes de regroupement (sans parent_code resolu sur le 1er passage)
        accounts = {}
        for spec in ROOT_ACCOUNTS:
            acc, created = ChartOfAccount.objects.update_or_create(
                code=spec["code"],
                defaults={
                    "name": spec["name"],
                    "class_number": spec["class_number"],
                    "description": spec.get("description", ""),
                },
            )
            accounts[spec["code"]] = acc
            self.stdout.write(f"  {acc.code}: {'cree' if created else 'mis a jour'}")

        # 2) Resolution des parent_code
        for spec in ROOT_ACCOUNTS:
            parent_code = spec.get("parent_code")
            if parent_code:
                acc = accounts[spec["code"]]
                acc.parent = accounts[parent_code]
                acc.save(update_fields=["parent", "updated_at"])

        # 3) Comptes de liaison 181.x par projet actif
        projects = list(Project.objects.filter(is_active=True, deleted_at__isnull=True).order_by("code"))
        for index, project in enumerate(projects):
            suffix = _suffix_for_project(index)
            code = f"181.{suffix}"
            name = f"Liaison {project.short_title or project.title or project.code}"
            acc, created = ChartOfAccount.objects.update_or_create(
                code=code,
                defaults={
                    "name": name[:200],
                    "class_number": 1,
                    "parent": accounts["181"],
                    "is_liaison": True,
                    "linked_project": project,
                    "description": f"Compte de liaison interne EVE pour le projet {project.code}.",
                },
            )
            self.stdout.write(
                f"  {code} ({project.code}): {'cree' if created else 'mis a jour'}"
            )

        # 3 bis) Comptes de liaison speciaux (projets clos / hors base)
        for spec in EXTRA_LIAISON_ACCOUNTS:
            acc, created = ChartOfAccount.objects.update_or_create(
                code=spec["code"],
                defaults={
                    "name": spec["name"],
                    "class_number": 1,
                    "parent": accounts["181"],
                    "is_liaison": True,
                    "description": spec.get("description", ""),
                },
            )
            self.stdout.write(f"  {spec['code']} (liaison speciale): {'cree' if created else 'mis a jour'}")

        # 4) Comptes bancaires 512.x
        for bank_name, (code, label) in BANK_TO_CODE.items():
            try:
                bank = BankAccount.objects.get(
                    name=bank_name, is_active=True, deleted_at__isnull=True
                )
            except BankAccount.DoesNotExist:
                self.stderr.write(f"  /!\\ BankAccount '{bank_name}' introuvable, compte {code} non lie.")
                continue
            acc, created = ChartOfAccount.objects.update_or_create(
                code=code,
                defaults={
                    "name": label,
                    "class_number": 5,
                    "parent": accounts["512"],
                    "linked_bank_account": bank,
                },
            )
            self.stdout.write(f"  {code} ({bank_name}): {'cree' if created else 'mis a jour'}")

        # 5) Caisse 571.x
        for register_name, (code, label) in CASH_REGISTER_TO_CODE.items():
            register = CashRegister.objects.filter(name=register_name).first()
            if register is None:
                # Cree la caisse a la volee avec le defaut SYCEBNL
                register, _ = CashRegister.objects.get_or_create(
                    name=register_name,
                    defaults={"currency": "XOF"},
                )
                self.stdout.write(f"  Caisse '{register_name}' cree a la volee.")
            acc, created = ChartOfAccount.objects.update_or_create(
                code=code,
                defaults={
                    "name": label,
                    "class_number": 5,
                    "parent": accounts["571"],
                    "linked_cash_register": register,
                },
            )
            self.stdout.write(f"  {code} ({register_name}): {'cree' if created else 'mis a jour'}")

        self.stdout.write(self.style.SUCCESS("Plan comptable SYCEBNL seedé."))
