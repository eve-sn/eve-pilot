"""
Seed du plan comptable SYCEBNL OFFICIEL EVE.

Importe l'integralite du plan comptable officiel SYCEBNL (~1100 comptes)
livre par EVE dans le fichier "ETAT FIN SYCBNL EVE 2024.xlsx", feuille
"Plan Comptable". Source de verite stockee dans :
  apps/finance/data/sycebnl_plan_officiel.json

Cette commande remplace l'ancien duo seed_chart_of_accounts_sycebnl +
seed_chart_of_accounts_detailed qui derivait d'une numerotation inventee
non conforme. Apres execution :
  - Les ~1100 comptes officiels SYCEBNL sont presents.
  - Les comptes "compteur EBNL" indispensables qui ne sont PAS dans le
    XLSX d'EVE mais figurent dans le guide d'application (702, 703, ...)
    sont ajoutes comme compteur App.8.
  - Les sous-comptes operationnels EVE (5211.x banques, 181.x liaison
    projet, 571.x caisse) sont generes a partir des objets metier.

Idempotente (update_or_create par code).
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.finance.models import BankAccount, CashRegister, ChartOfAccount
from apps.projects.models import Project


PLAN_JSON_PATH = (
    Path(__file__).resolve().parent.parent.parent / "data" / "sycebnl_plan_officiel.json"
)


# Codes hors XLSX EVE mais explicitement utilises dans le guide d'application
# SYCEBNL App.8 (projets de developpement). Ils sont indispensables pour la
# mecanique 162/462/702/703 cablee dans posting.py.
APPLICATION_GUIDE_COMPLEMENTS = [
    # (code, name, class_number, description)
    ("702", "Quote-part de fonds d'administration transferes au compte de resultat", 7,
        "App.8 du guide SYCEBNL - produit de neutralisation des charges engagees "
        "sur 462. Au fur et a mesure de l'engagement des charges, on debite 462 / "
        "credite 702 pour neutraliser l'impact resultat (matching principle)."),
    ("703", "Quote-part des dotations consomptibles transferees au compte de resultat", 7,
        "App.8 du guide SYCEBNL - couverture des charges engagees sur dotation "
        "consomptible 1041 (cf. compte 1049)."),
    ("181", "Comptes de liaison projets - reseau EVE", 1,
        "Comptes internes EVE de liaison projet <-> Budget General. "
        "Pas dans le plan officiel - convention metier EVE."),
    ("5211", "Banques en monnaie locale - reseau EVE", 5,
        "Sous-comptes 5211.x crees a partir des BankAccount EVE actifs."),
    ("585", "Virements internes - banque vers caisse / inter-comptes", 5,
        "Compte tampon pour les transferts entre comptes EVE (banque -> banque, "
        "banque -> caisse). Confirme present dans le plan officiel."),
]


def _normalize_code(raw) -> str | None:
    """Normalise un code brut du XLSX (peut etre int ou str avec '.')."""
    if raw is None:
        return None
    code = str(raw).strip()
    # Codes "10." (entete classe) -> strip
    code = code.rstrip(".").strip()
    if not code:
        return None
    return code


def _class_number_for(code: str) -> int:
    """Determine la classe SYCEBNL d'apres le 1er chiffre."""
    if not code or not code[0].isdigit():
        return 1
    return int(code[0])


# Mapping nom BankAccount -> code SYCEBNL 5211.x (banques en monnaies locales)
BANK_TO_CODE = {
    "Banque Atlantique": ("5211.10", "Banque Atlantique - EVE"),
    "EVE-OXFAM": ("5211.20", "SUNU BANK - EVE-OXFAM (AXA + ECO)"),
    "EVE service": ("5211.30", "CBAO - EVE service (Saint-Louis)"),
    "EVE-SODIS": ("5211.40", "SUNU BANK - EVE-SODIS (ONAS PDBH)"),
    "EVE": ("5211.50", "BOA - EVE (ChildFund)"),
    "Budget General": ("5211.60", "SUNU BANK - Budget General"),
}

# Mapping nom CashRegister -> code SYCEBNL 571.x
CASH_REGISTER_TO_CODE = {
    "Caisse centrale BG": ("571.00", "Caisse centrale BG"),
}

# Comptes de liaison "speciaux" : projets clos hors-perimetre dont le reliquat
# continue de transiter.
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


def _suffix_for_project(index: int) -> str:
    return f"{(index + 1) * 10:03d}"


class Command(BaseCommand):
    help = (
        "Importe l'integralite du plan comptable SYCEBNL officiel EVE "
        "(source : apps/finance/data/sycebnl_plan_officiel.json), enrichi "
        "des comptes App.8 du guide (702, 703) et des sous-comptes "
        "operationnels EVE (5211.x, 181.x, 571.x)."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        if not PLAN_JSON_PATH.exists():
            self.stderr.write(self.style.ERROR(
                f"Plan JSON introuvable : {PLAN_JSON_PATH}. "
                "Le commit doit inclure ce fichier."
            ))
            return

        with PLAN_JSON_PATH.open(encoding="utf-8") as f:
            entries = json.load(f)

        self.stdout.write(f"Import du plan SYCEBNL officiel ({len(entries)} entrees JSON)...")

        # 1) Import des comptes officiels (sans parent_code resolu sur le 1er passage)
        created, updated, skipped = 0, 0, 0
        for entry in entries:
            code = _normalize_code(entry.get("code"))
            name = (entry.get("name") or "").strip()
            if not code or not name:
                skipped += 1
                continue
            cls = _class_number_for(code)
            obj, was_created = ChartOfAccount.objects.update_or_create(
                code=code,
                defaults={
                    "name": name[:200],
                    "class_number": cls,
                    "is_liaison": False,
                    "is_active": True,
                    "deleted_at": None,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

        # 2) Complements App.8 du guide (702, 703, ...)
        for code, name, cls, description in APPLICATION_GUIDE_COMPLEMENTS:
            obj, was_created = ChartOfAccount.objects.update_or_create(
                code=code,
                defaults={
                    "name": name[:200],
                    "class_number": cls,
                    "description": description,
                    "is_liaison": False,
                    "is_active": True,
                    "deleted_at": None,
                },
            )
            if was_created:
                created += 1
                self.stdout.write(f"  + {code} (complement App.8) : {name[:50]}")

        # 3) Comptes de liaison 181.x par projet actif
        parent_181 = ChartOfAccount.objects.filter(code="181").first()
        projects = list(
            Project.objects.filter(is_active=True, deleted_at__isnull=True).order_by("code")
        )
        for index, project in enumerate(projects):
            suffix = _suffix_for_project(index)
            code = f"181.{suffix}"
            name = f"Liaison {project.short_title or project.title or project.code}"
            ChartOfAccount.objects.update_or_create(
                code=code,
                defaults={
                    "name": name[:200],
                    "class_number": 1,
                    "parent": parent_181,
                    "is_liaison": True,
                    "linked_project": project,
                    "description": f"Compte de liaison interne EVE pour le projet {project.code}.",
                },
            )

        # 3 bis) Liaisons speciales (projets clos)
        for spec in EXTRA_LIAISON_ACCOUNTS:
            ChartOfAccount.objects.update_or_create(
                code=spec["code"],
                defaults={
                    "name": spec["name"],
                    "class_number": 1,
                    "parent": parent_181,
                    "is_liaison": True,
                    "description": spec.get("description", ""),
                },
            )

        # 4) Sous-comptes bancaires 5211.x
        parent_5211 = ChartOfAccount.objects.filter(code="5211").first()
        for bank_name, (code, label) in BANK_TO_CODE.items():
            try:
                bank = BankAccount.objects.get(
                    name=bank_name, is_active=True, deleted_at__isnull=True
                )
            except BankAccount.DoesNotExist:
                self.stderr.write(
                    f"  /!\\ BankAccount '{bank_name}' introuvable, compte {code} non lie."
                )
                continue
            ChartOfAccount.objects.update_or_create(
                code=code,
                defaults={
                    "name": label,
                    "class_number": 5,
                    "parent": parent_5211,
                    "linked_bank_account": bank,
                },
            )

        # 5) Sous-comptes caisses 571.x
        parent_571 = ChartOfAccount.objects.filter(code="571").first()
        for register_name, (code, label) in CASH_REGISTER_TO_CODE.items():
            register = CashRegister.objects.filter(name=register_name).first()
            if register is None:
                register, _ = CashRegister.objects.get_or_create(
                    name=register_name, defaults={"currency": "XOF"},
                )
            ChartOfAccount.objects.update_or_create(
                code=code,
                defaults={
                    "name": label,
                    "class_number": 5,
                    "parent": parent_571,
                    "linked_cash_register": register,
                },
            )

        self.stdout.write(self.style.SUCCESS(
            f"Plan comptable SYCEBNL officiel seede : "
            f"{created} crees, {updated} mis a jour, {skipped} ignores."
        ))
        self.stdout.write(
            "Pour migrer les codes EVE non-officiels (1101, 23, 40, 401, ...) "
            "vers leurs equivalents officiels, lancer migrate (migration 0016)."
        )
