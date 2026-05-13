"""
Import des charges de personnel et cotisations sociales du Budget General EVE 2026.

Sources xlsx Budget_Previsionnel_EVE_2026.xlsx:
- Onglet 1 (Synthese) : ligne "Charges de personnel" (enveloppe globale 2026)
- Onglet 3 (IPRES-CSS) : 3 sections (impayes 2025, courants 2026, dette historique 2022-2024)
- Onglet 4 (VRS-BRS)   : projection 2026 + impayes 2025

Toutes les lignes sont creees dans le Budget General (BudgetLine.project = None)
avec la categorie CHARGES_PERSONNEL. La categorie est creee a la volee si absente.

ATTENTION metier:
- La ligne PAYROLL-SYNTH-2026 (117 232 774 FCFA, onglet 1) est l'enveloppe agregee
  des charges de personnel courantes 2026. Elle inclut probablement les cotisations
  IPRES-CSS et les retenues VRS-BRS qui figurent en lignes detaillees ci-dessous.
  Sommer naivement les 6 lignes provoque un double comptage. La note de chaque
  ligne le signale explicitement, l'interpretation revient a l'utilisateur.

La commande est idempotente : (code, project IS NULL) sert de cle de matchage
via update_or_create.
"""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.finance.models import BudgetLine
from apps.references.models import BudgetCategory


CATEGORY_CODE = "CHARGES_PERSONNEL"
CATEGORY_NAME = "Charges de personnel et cotisations sociales"
CATEGORY_DESCRIPTION = (
    "Lignes Budget General EVE : salaires, IPRES-CSS, VRS-BRS, apurement des "
    "dettes sociales. Le personnel n'est jamais paye sur un compte projet."
)


PAYROLL_LINES = [
    {
        "code": "PAYROLL-SYNTH-2026",
        "description": "Charges de personnel 2026 (enveloppe globale - synthese)",
        "planned_amount": Decimal("117232774"),
        "notes": (
            "Source: onglet 1 Synthese, ligne 'Charges de personnel'. Enveloppe "
            "globale courante 2026 (renvoie aux onglets 3, 4, 5). ATTENTION : "
            "inclut probablement les cotisations IPRES-CSS et retenues VRS-BRS "
            "des lignes detaillees ci-dessous. A traiter comme la reference "
            "agregee, pas comme un montant ajoute aux autres lignes."
        ),
    },
    {
        "code": "PAYROLL-IPRES-2026",
        "description": "IPRES-CSS 2026 - cotisations courantes (4 trimestres)",
        "planned_amount": Decimal("8175120"),
        "notes": (
            "Source: onglet 3 IPRES-CSS section B. 4 echeances trimestrielles "
            "de 2 043 780 FCFA chacune. Provision 2026."
        ),
    },
    {
        "code": "PAYROLL-IPRES-DEBT-2025",
        "description": "IPRES-CSS 2025 - impayes T1-T4 a regulariser",
        "planned_amount": Decimal("7619288"),
        "notes": (
            "Source: onglet 3 IPRES-CSS section A. 4 factures impayees 2025 a "
            "regler en 2026."
        ),
    },
    {
        "code": "PAYROLL-IPRES-DEBT-HIST",
        "description": "IPRES-CSS 2022-2024 - dette historique a apurer",
        "planned_amount": Decimal("18009970"),
        "notes": (
            "Source: onglet 3 IPRES-CSS section C. Dette historique anciennes "
            "annees, a apurer."
        ),
    },
    {
        "code": "PAYROLL-VRS-BRS-2026",
        "description": "VRS-BRS 2026 - projection annuelle (12 mois)",
        "planned_amount": Decimal("14335068"),
        "notes": (
            "Source: onglet 4 VRS-BRS section C. Base mensuelle moy. T1-2026 = "
            "1 194 589 FCFA x 12. Inclut VRS (ISR + TRIMF + CFCE) et BRS "
            "(RAS Tiers + loyers)."
        ),
    },
    {
        "code": "PAYROLL-VRS-BRS-DEBT-2025",
        "description": "VRS-BRS 2025 - impayes Janvier-Aout a regulariser",
        "planned_amount": Decimal("7875201"),
        "notes": (
            "Source: onglet 4 VRS-BRS section B. VRS impaye 6 325 392 + BRS "
            "impaye 1 549 809. A regulariser en 2026."
        ),
    },
]


class Command(BaseCommand):
    help = "Importe les charges de personnel 2026 dans le Budget General (onglets 1, 3, 4)."

    @transaction.atomic
    def handle(self, *args, **options):
        category = self._ensure_category()
        self._import_lines(category)
        self.stdout.write(self.style.SUCCESS("Import payroll Budget General termine."))

    def _ensure_category(self):
        category, created = BudgetCategory.objects.update_or_create(
            code=CATEGORY_CODE,
            defaults={
                "name": CATEGORY_NAME,
                "description": CATEGORY_DESCRIPTION,
            },
        )
        action = "creee" if created else "deja presente"
        self.stdout.write(f"  Categorie '{CATEGORY_CODE}': {action}")
        return category

    def _import_lines(self, category):
        for spec in PAYROLL_LINES:
            defaults = {
                "description": spec["description"],
                "category": category,
                "planned_amount": spec["planned_amount"],
                "currency": "XOF",
                "fiscal_year": 2026,
                "notes": spec["notes"],
            }
            line, created = BudgetLine.objects.update_or_create(
                code=spec["code"],
                project=None,
                defaults=defaults,
            )
            action = "creee" if created else "mise a jour"
            self.stdout.write(
                f"  BudgetLine {spec['code']}: {action} "
                f"({spec['planned_amount']} FCFA)"
            )
