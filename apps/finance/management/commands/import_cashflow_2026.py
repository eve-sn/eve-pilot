"""
Importe le plan de tresorerie mensuel 2026 depuis l'onglet 7 du xlsx
Budget_Previsionnel_EVE_2026.xlsx.

L'onglet 7 contient 12 colonnes de mois (Jan-Dec) :
- Encaissements (R5-R14) : 10 lignes, une par projet.
- Decaissements (R18-R28) : 11 lignes, une par categorie de charge.

Chaque ligne x 12 mois produit jusqu'a 12 lignes CashflowEntry (les zeros
sont skip pour ne pas polluer la base).

Mapping encaissements -> Project :
  "AGIR Pikine Phase I (solde)"          -> aucun (projet clos, pas en base)
  "Pikine Phase II T1 (70k EUR)"         -> NOUSCIMS-PIK-MBAO-2026
  "Pikine Phase II T2 (60k EUR)"         -> NOUSCIMS-PIK-MBAO-2026
  "Saint-Louis T1 (60k EUR)"             -> NOUSCIMS-SL-2026
  "Saint-Louis T2 (60k EUR)"             -> NOUSCIMS-SL-2026
  "Espaces communautaires (reliquat)"    -> NOUSCIMS-ECP-2025
  "PDBH IEC ONAS (factures)"             -> ONASAFD-PDBH-IEC-2025
  "Inondations ChildFund/P&G"            -> CHILDFUND-INONDATIONS-2025
  "ISF / AXA Climate (reliquat 2026)"    -> AXA-ISF-2026
  "ECO-AVENIR (11 500 EUR)"              -> OGHOGHO-ECOAVENIR-2026

Mapping decaissements -> BudgetCategory : cree les categories manquantes
a la volee. Liste fixe documentee dans CASHFLOW_OUT_CATEGORIES.

Idempotente : update_or_create sur (period_year, period_month, label, direction).
"""

from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.finance.models import CashflowEntry
from apps.projects.models import Project
from apps.references.models import BudgetCategory


XLSX_REL_PATH = "Budget_Previsionnel_EVE_2026.xlsx"
XLSX_SHEET = "7. Plan trésorerie"
PERIOD_YEAR = 2026


# Mapping label xlsx -> code projet existant. None = encaissement non rattache.
INCOMING_PROJECT_MAP = {
    "AGIR Pikine Phase I (solde)": None,  # projet clos, hors base
    "Pikine Phase II T1 (70k€)": "NOUSCIMS-PIK-MBAO-2026",
    "Pikine Phase II T2 (60k€)": "NOUSCIMS-PIK-MBAO-2026",
    "Saint-Louis T1 (60k€)": "NOUSCIMS-SL-2026",
    "Saint-Louis T2 (60k€)": "NOUSCIMS-SL-2026",
    "Espaces communautaires (reliquat)": "NOUSCIMS-ECP-2025",
    "PDBH IEC ONAS (factures)": "ONASAFD-PDBH-IEC-2025",
    "Inondations ChildFund/P&G": "CHILDFUND-INONDATIONS-2025",
    "ISF / AXA Climate (reliquat 2026)": "AXA-ISF-2026",
    "ECO-AVENIR (11 500 €)": "OGHOGHO-ECOAVENIR-2026",
}


## Categories de decaissement Budget General. Mapping label xlsx -> (code, name).
## Le code est limite a 20 caracteres (modele BudgetCategory).
CASHFLOW_OUT_CATEGORIES = {
    "Achats": ("ACHATS", "Achats (fournitures, carburant, materiel)"),
    "Services extérieurs": ("SERVICES_EXT", "Services exterieurs (location siege, vehicules, entretien, telecoms)"),
    "Autres services extérieurs": ("AUTRES_SVC_EXT", "Autres services exterieurs (personnel exterieur, publicite, deplacements)"),
    "Charges personnel courantes (IPM, Perdiem, Soutien)": ("CHARGES_PERSO_CRT", "Charges personnel courantes (IPM, perdiem, soutien)"),
    "VRS+BRS courant 2026 (mensuel)": ("VRS_BRS_CRT", "VRS + BRS courants 2026 (mensuels)"),
    "IPRES-CSS 2026 trimestriel": ("IPRES_CSS_2026", "IPRES-CSS 2026 (cotisations courantes trimestrielles)"),
    "Apurement dette IPRES-CSS 2025 (étalé)": ("APUR_IPRES_2025", "Apurement dette IPRES-CSS 2025 (etale)"),
    "Apurement dette VRS+BRS 2025 (étalé)": ("APUR_VRS_BRS_2025", "Apurement dette VRS+BRS 2025 (etale)"),
    "Apurement dette historique 2022-2024 (étalé 24 mois)": ("APUR_HISTORIQUE", "Apurement dette historique 2022-2024 (etale 24 mois)"),
    "Appuis et subventions (décaissé)": ("APPUIS_SUBV", "Appuis et subventions decaisses"),
    "Autres charges": ("AUTRES_CHARGES", "Autres charges"),
}


SKIP_ROWS_INCOMING = {"ENCAISSEMENTS", "Total Encaissements"}
SKIP_ROWS_OUTGOING = {"DÉCAISSEMENTS", "Total Décaissements", "SOLDE NET MENSUEL", "SOLDE CUMULÉ"}


class Command(BaseCommand):
    help = "Importe le plan de tresorerie mensuel 2026 (onglet 7 du xlsx)."

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            import openpyxl
        except ImportError:
            self.stderr.write("openpyxl manquant. pip install openpyxl avant relance.")
            return

        xlsx_path = Path(settings.BASE_DIR) / XLSX_REL_PATH
        if not xlsx_path.exists():
            self.stderr.write(f"Fichier xlsx introuvable: {xlsx_path}")
            return

        wb = openpyxl.load_workbook(str(xlsx_path), data_only=True)
        ws = wb[XLSX_SHEET]

        self.stdout.write(f"Lecture {xlsx_path.name} (onglet '{XLSX_SHEET}')...")

        categories = self._seed_categories()
        projects = self._load_projects()

        rows = list(ws.iter_rows(values_only=True))
        # Format attendu: R3 entete, R5-R14 encaissements, R18-R28 decaissements.
        # On parcourt et on detecte la direction par sections.
        direction = None
        incoming_count = 0
        outgoing_count = 0
        skipped_count = 0

        for row_idx, row in enumerate(rows, start=1):
            label = (row[0] or "").strip() if row and row[0] else ""
            # Detection stricte des markers de section. Match exact pour eviter
            # qu'un label projet contenant '(solde)' ne soit confondu avec la
            # ligne SOLDE NET / SOLDE CUMULE.
            if label == "ENCAISSEMENTS":
                direction = CashflowEntry.Direction.INCOMING
                continue
            if label == "DÉCAISSEMENTS":
                direction = CashflowEntry.Direction.OUTGOING
                continue
            if label in ("SOLDE NET MENSUEL", "SOLDE CUMULÉ"):
                direction = None
                continue
            if not label or label in SKIP_ROWS_INCOMING or label in SKIP_ROWS_OUTGOING:
                continue
            if direction is None:
                continue

            # Mensualites en colonnes 1..12 (B..M), Total en colonne 13 (N).
            monthly_amounts = row[1:13]
            for month_idx, amount in enumerate(monthly_amounts, start=1):
                if amount is None or amount == 0:
                    skipped_count += 1
                    continue
                try:
                    decimal_amount = Decimal(str(amount))
                except Exception:
                    self.stderr.write(
                        f"  /!\\ Montant non numerique a R{row_idx} mois {month_idx} ({amount!r}), ignore."
                    )
                    continue
                project = None
                category = None
                if direction == CashflowEntry.Direction.INCOMING:
                    code = INCOMING_PROJECT_MAP.get(label)
                    if code is not None:
                        project = projects.get(code)
                else:
                    cat_info = CASHFLOW_OUT_CATEGORIES.get(label)
                    if cat_info is not None:
                        category = categories.get(cat_info[0])
                CashflowEntry.objects.update_or_create(
                    period_year=PERIOD_YEAR,
                    period_month=month_idx,
                    label=label,
                    direction=direction,
                    defaults={
                        "project": project,
                        "category": category,
                        "planned_amount": decimal_amount,
                    },
                )
                if direction == CashflowEntry.Direction.INCOMING:
                    incoming_count += 1
                else:
                    outgoing_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Plan tresorerie 2026 importe: {incoming_count} encaissements, "
                f"{outgoing_count} decaissements, {skipped_count} cellules vides ignorees."
            )
        )

    def _seed_categories(self):
        result = {}
        for label, (code, name) in CASHFLOW_OUT_CATEGORIES.items():
            category, _ = BudgetCategory.objects.update_or_create(
                code=code,
                defaults={"name": name},
            )
            result[code] = category
        self.stdout.write(f"  {len(result)} categories de decaissement seedees.")
        return result

    def _load_projects(self):
        return {
            p.code: p
            for p in Project.objects.filter(is_active=True, deleted_at__isnull=True)
        }
