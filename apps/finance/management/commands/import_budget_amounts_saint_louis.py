# -*- coding: utf-8 -*-
"""
Importe les vrais montants du budget detaille Saint-Louis (xls -> BudgetLine).

Source : "Annexe 2- Budget detaille projet de _saint louis_15-06-2025.xls"
Project : NOUSCIMS-SL-2026

Le xls fournit le budget en 3 colonnes annuelles (ANNEE 1, ANNEE 2, ANNEE 3 -
toujours 0) et un COUT TOTAL. La commande importe le COUT TOTAL FCFA sur
chaque BudgetLine seedee, plus quantity et unit_cost lorsque disponibles.

Le mapping (xls_row -> code BudgetLine) est explicite et stable. Si la
structure du xls change (ajout/retrait de lignes), il faudra mettre a jour
la table de mapping ci-dessous.

Idempotente : ecrase les montants existants sur chaque ligne mappee.

Conventions de colonne xls :
  col 1 : libelle rubrique
  col 2 : cout unitaire
  col 3 : quantite
  col 10: cout total FCFA
"""

from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.finance.models import BudgetLine
from apps.projects.models import Project

try:
    import xlrd
except ImportError:  # pragma: no cover
    xlrd = None

PROJECT_CODE = "NOUSCIMS-SL-2026"
XLS_FILENAME = "Annexe 2- Budget detaille projet de _saint louis_15-06-2025.xls"

COL_UNIT_COST = 2
COL_QUANTITY = 3
COL_ANNEE_1_FCFA = 4
COL_ANNEE_2_FCFA = 6
COL_ANNEE_3_FCFA = 8
COL_TOTAL_FCFA = 10

# Mapping explicite : (xls_row, BudgetLine.code).
# Les sections "header" du xls (sans montant directement chiffrable, le
# montant en col 10 est l'agregat des sous-lignes) ne sont pas mappees ici.
ROW_TO_CODE = [
    # A.1.1 Formations - 5 themes x 4 sous-lignes
    *[(11 + i, f"SL-A111-T1-S{i + 1}-2026") for i in range(4)],   # rows 11-14
    *[(16 + i, f"SL-A111-T2-S{i + 1}-2026") for i in range(4)],   # rows 16-19
    *[(21 + i, f"SL-A111-T3-S{i + 1}-2026") for i in range(4)],   # rows 21-24
    *[(26 + i, f"SL-A111-T4-S{i + 1}-2026") for i in range(4)],   # rows 26-29
    *[(31 + i, f"SL-A111-T5-S{i + 1}-2026") for i in range(4)],   # rows 31-34
    # A.1.3 Equipement / Materiel - 10 lignes
    *[(39 + i, f"SL-A113-{i + 1:02d}-2026") for i in range(10)],  # rows 39-48
    # A.1.4 Prestations professionnelles - 3 lignes
    *[(50 + i, f"SL-A114-{i + 1:02d}-2026") for i in range(3)],   # rows 50-52
    # A.1.5/1 Ceremonie lancement - 4 sous-lignes
    *[(55 + i, f"SL-A115-1-S{i + 1}-2026") for i in range(4)],    # rows 55-58
    # A.1.5/2 CDDN - 4 sous-lignes
    *[(60 + i, f"SL-A115-2-S{i + 1}-2026") for i in range(4)],    # rows 60-63
    # A.1.5/3 5 cadres communaux - 4 sous-lignes
    *[(65 + i, f"SL-A115-3-S{i + 1}-2026") for i in range(4)],    # rows 65-68
    # A.1.5/4 Atelier feuilles de routes - 4 sous-lignes
    *[(70 + i, f"SL-A115-4-S{i + 1}-2026") for i in range(4)],    # rows 70-73
    # A.1.5/5 Rencontres annuelles suivi - 4 sous-lignes
    *[(75 + i, f"SL-A115-5-S{i + 1}-2026") for i in range(4)],    # rows 75-78
    # A.1.5/6 PAN communaux - 4 sous-lignes
    *[(80 + i, f"SL-A115-6-S{i + 1}-2026") for i in range(4)],    # rows 80-83
    # A.1.5/7 Plaidoyer Fora - 5 sous-lignes (7.1.1 - 7.1.5)
    *[(86 + i, f"SL-A115-7-S{i + 1}-2026") for i in range(5)],    # rows 86-90
    # A.1.5/8 Planification campagnes - 4 sous-lignes
    *[(92 + i, f"SL-A115-8-S{i + 1}-2026") for i in range(4)],    # rows 92-95
    # A.1.5/9 Organisation campagnes - 2 sous-lignes (ICP / Relais)
    (97, "SL-A115-9-S1-2026"),
    (98, "SL-A115-9-S2-2026"),
    # A.1.5/10 Evaluation campagnes - 4 sous-lignes
    *[(100 + i, f"SL-A115-10-S{i + 1}-2026") for i in range(4)],  # rows 100-103
    # A.1.5/11 Rehabilitation - ligne unique
    (104, "SL-A115-11-2026"),
    # A.2/1 Staff bureau local - 4 sous-lignes
    *[(107 + i, f"SL-A2-STAFF-{i + 1:02d}-2026") for i in range(4)],  # rows 107-110
    # A.2/2 Coordination globale - 3 sous-lignes
    *[(112 + i, f"SL-A2-COORD-{i + 1:02d}-2026") for i in range(3)],  # rows 112-114
    # A.3/1 Mission conjointe - 4 sous-lignes
    *[(117 + i, f"SL-A3-1-S{i + 1}-2026") for i in range(4)],     # rows 117-120
    # A.3/2 Mission siege - 4 sous-lignes
    *[(122 + i, f"SL-A3-2-S{i + 1}-2026") for i in range(4)],     # rows 122-125
    # A.3/3 Mission supervision bureau local - 3 sous-lignes
    *[(127 + i, f"SL-A3-3-S{i + 1}-2026") for i in range(3)],     # rows 127-129
    # A.4 Depenses administratives - 7 lignes
    *[(131 + i, f"SL-A4-{i + 1:02d}-2026") for i in range(7)],    # rows 131-137
    # A.5 Divers - 3 lignes (Femme de charge, Outils gestion, Communication)
    (139, "SL-A5-01-2026"),
    (140, "SL-A5-02-2026"),
    (141, "SL-A5-03-2026"),
    # B. Couts indirects (1 ligne, lue sur la ligne TOTAL COUTS INDIRECTS = row 145)
    (145, "SL-B-INDIRECT-2026"),
]


def _to_decimal(value):
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _row_total(sheet, row):
    """Renvoie le COUT TOTAL FCFA d'une ligne.

    Sur certaines sous-lignes (cf. A.1.5/1) la col TOTAL est laissee vide
    alors que les colonnes ANNEE 1/2/3 sont renseignees ; on rebascule alors
    sur la somme des annees.
    """
    total = _to_decimal(sheet.cell_value(row, COL_TOTAL_FCFA))
    if total is not None:
        return total
    parts = [
        _to_decimal(sheet.cell_value(row, COL_ANNEE_1_FCFA)) or Decimal("0"),
        _to_decimal(sheet.cell_value(row, COL_ANNEE_2_FCFA)) or Decimal("0"),
        _to_decimal(sheet.cell_value(row, COL_ANNEE_3_FCFA)) or Decimal("0"),
    ]
    summed = sum(parts, Decimal("0"))
    return summed if summed != Decimal("0") else None


class Command(BaseCommand):
    help = (
        "Importe les montants COUT TOTAL FCFA du budget detaille Saint-Louis "
        "(Annexe 2 xls) dans les BudgetLine du projet NOUSCIMS-SL-2026."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            default=str(settings.BASE_DIR / XLS_FILENAME),
            help="Chemin du fichier xls (defaut: a la racine du depot).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if xlrd is None:
            raise CommandError("xlrd n'est pas installe (requis pour lire .xls)")
        path = Path(options["file"])
        if not path.exists():
            raise CommandError(f"Fichier introuvable : {path}")

        try:
            project = Project.objects.get(
                code=PROJECT_CODE, is_active=True, deleted_at__isnull=True
            )
        except Project.DoesNotExist:
            raise CommandError(f"Projet {PROJECT_CODE} introuvable.")

        wb = xlrd.open_workbook(str(path))
        sheet = wb.sheet_by_index(0)

        existing = {
            bl.code: bl
            for bl in BudgetLine.objects.filter(
                project=project, is_active=True, deleted_at__isnull=True
            )
        }

        updated = 0
        skipped_missing = 0
        skipped_zero = 0
        total_amount = Decimal("0")
        missing_codes = []

        for row, code in ROW_TO_CODE:
            bl = existing.get(code)
            if bl is None:
                missing_codes.append(code)
                skipped_missing += 1
                continue
            total = _row_total(sheet, row)
            if total is None:
                skipped_zero += 1
                continue
            unit_cost = _to_decimal(sheet.cell_value(row, COL_UNIT_COST))
            quantity = _to_decimal(sheet.cell_value(row, COL_QUANTITY))

            bl.planned_amount = total
            if unit_cost is not None:
                bl.unit_cost = unit_cost
            if quantity is not None:
                bl.quantity = quantity
            bl.save(
                update_fields=["planned_amount", "unit_cost", "quantity", "updated_at"]
            )
            updated += 1
            total_amount += total

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Budget Saint-Louis importe : {updated} lignes mises a jour, "
                f"total {total_amount:,.0f} XOF."
            )
        )
        if missing_codes:
            self.stdout.write(self.style.WARNING(
                f"Codes BudgetLine manquants (lancer d'abord le seed) : {missing_codes}"
            ))
        if skipped_zero:
            self.stdout.write(f"  {skipped_zero} cellules vides ignorees.")
