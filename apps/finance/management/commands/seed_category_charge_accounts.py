# -*- coding: utf-8 -*-
"""Mappe chaque BudgetCategory engageable vers son compte de charge 6x par defaut.

Prerequis de la comptabilite d'engagement (Phase 0) : a l'engagement d'une
depense, le compte de charge (Dr 6x) est resolu via
category.default_charge_account (surcharge possible par engagement). Cette
commande pose le mapping valide avec le comptable, cf.
docs/MAPPING_CATEGORIES_COMPTES_6X.md.

Idempotent (update du FK par code). Les categories NON engageables (paie,
social/fiscal, apurement de dettes, couts indirects) ne sont volontairement
PAS mappees : elles ont un circuit comptable distinct.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.finance.models import ChartOfAccount
from apps.references.models import BudgetCategory


# code_categorie -> code_compte_6x (cf. docs/MAPPING_CATEGORIES_COMPTES_6X.md)
CATEGORY_CHARGE_MAP = {
    "FORM": "633",
    "PROJ_FORMATION": "633",
    "PROJ_ACTIVITES": "638",
    "PROJ_COMMUNICATION": "6274",
    "PROJ_PRESTATION": "6381",
    "PROJ_SUIVI": "6261",
    "PROJ_INTRANTS": "6011",
    "PROJ_LOGISTIQUE": "6181",
    "ACHATS": "605",
    "PROJ_ADMIN": "6221",
    "SERVICES_EXT": "638",
    "AUTRES_SVC_EXT": "638",
    "APPUIS_SUBV": "652",
    "AUTRES_CHARGES": "658",
    "PROJ_DIVERS": "658",
    "PROJ_EQUIPEMENT": "6056",
}

# Categories volontairement NON mappees (circuit distinct). Listees pour qu'une
# absence de mapping soit un choix explicite, pas un oubli.
NON_ENGAGEABLE = [
    "CHARGES_PERSONNEL", "CHARGES_PERSO_CRT", "PROJ_PERSONNEL",  # paie 661/422
    "IPRES_CSS_2026", "VRS_BRS_CRT",                            # social/fiscal 43/44
    "APUR_HISTORIQUE", "APUR_IPRES_2025", "APUR_VRS_BRS_2025",  # apurement dettes 4xx/5211
    "PROJ_INDIRECTS",                                           # recharge interne 181.x/781
]


class Command(BaseCommand):
    help = (
        "Mappe les categories budgetaires engageables vers leur compte de "
        "charge 6x par defaut (cf. docs/MAPPING_CATEGORIES_COMPTES_6X.md)."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        accounts = {
            a.code: a
            for a in ChartOfAccount.objects.filter(
                code__in=set(CATEGORY_CHARGE_MAP.values()),
                is_active=True,
                deleted_at__isnull=True,
            )
        }

        posed = missing_cat = missing_acc = 0
        for cat_code, acc_code in CATEGORY_CHARGE_MAP.items():
            category = BudgetCategory.objects.filter(code=cat_code).first()
            if category is None:
                self.stderr.write(f"  /!\\ categorie {cat_code} absente, ignoree.")
                missing_cat += 1
                continue
            account = accounts.get(acc_code)
            if account is None:
                self.stderr.write(
                    f"  /!\\ compte {acc_code} absent/inactif ; mapping {cat_code} non pose."
                )
                missing_acc += 1
                continue
            if category.default_charge_account_id != account.id:
                category.default_charge_account = account
                category.save(update_fields=["default_charge_account"])
            posed += 1
            self.stdout.write(f"  {cat_code:20s} -> {acc_code:6s} {account.name[:40]}")

        self.stdout.write(
            f"Mapping pose : {posed} categorie(s) engageable(s) ; "
            f"{missing_cat} categorie(s) absente(s), {missing_acc} compte(s) absent(s)."
        )
        self.stdout.write(
            "Non mappees volontairement (circuit distinct) : "
            + ", ".join(NON_ENGAGEABLE)
        )
