"""
Seed des lignes budgetaires analytiques 2026 du Budget General EVE.

Source : Budget_Previsionnel_EVE_2026_Analytique_BG.pdf
6 rubriques : Achats, Services exterieurs, Autres services exterieurs,
Charges de personnel, Appuis et subventions, Autres charges.

Lignes creees avec :
- project = None (Budget General)
- category = BudgetCategory adequat (cree par import_cashflow_2026 ou ici)
- planned_amount = 0 (montants laisses a la saisie ulterieure ; le PDF
  analytique ne porte que la structure des lignes, pas les montants)
- fiscal_year = 2026
- currency = XOF

Idempotente : update_or_create par code BudgetLine.
"""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.finance.models import BudgetLine
from apps.references.models import BudgetCategory


CATEGORY_DEFAULTS = {
    "ACHATS": "Achats (fournitures, carburant, materiel)",
    "SERVICES_EXT": "Services exterieurs",
    "AUTRES_SVC_EXT": "Autres services exterieurs",
    "CHARGES_PERSO_CRT": "Charges personnel courantes",
    "IPRES_CSS_2026": "IPRES-CSS 2026 courantes",
    "VRS_BRS_CRT": "VRS+BRS courants 2026",
    "APUR_IPRES_2025": "Apurement IPRES-CSS 2025",
    "APUR_VRS_BRS_2025": "Apurement VRS+BRS 2025",
    "APUR_HISTORIQUE": "Apurement dette historique 2022-2024",
    "APPUIS_SUBV": "Appuis et subventions",
    "AUTRES_CHARGES": "Autres charges",
}


BUDGET_LINES = [
    # ACHATS (4)
    {"code": "BG-ACH-FOURN-2026", "category": "ACHATS", "description": "Fournitures et consommables de bureau"},
    {"code": "BG-ACH-CARB-VEH-2026", "category": "ACHATS", "description": "Carburant vehicule"},
    {"code": "BG-ACH-CARB-MOTO-2026", "category": "ACHATS", "description": "Carburant moto Saint-Louis et Kedougou"},
    {"code": "BG-ACH-ORD-2026", "category": "ACHATS", "description": "Ordinateurs, imprimantes, photocopieuse"},

    # SERVICES EXTERIEURS (13)
    {"code": "BG-SVE-LOC-DK-2026", "category": "SERVICES_EXT", "description": "Location siege Dakar (Pikine 1,5M + Mbao 500k/mois)"},
    {"code": "BG-SVE-LOC-SL-2026", "category": "SERVICES_EXT", "description": "Location siege Saint-Louis"},
    {"code": "BG-SVE-LOC-KED-2026", "category": "SERVICES_EXT", "description": "Location siege Kedougou"},
    {"code": "BG-SVE-LOC-SALLE-2026", "category": "SERVICES_EXT", "description": "Location de salle de reunion"},
    {"code": "BG-SVE-LOC-VEH-2026", "category": "SERVICES_EXT", "description": "Location vehicules"},
    {"code": "BG-SVE-HON-CONS-2026", "category": "SERVICES_EXT", "description": "Honoraires consultants"},
    {"code": "BG-SVE-HON-FACIL-2026", "category": "SERVICES_EXT", "description": "Honoraires facilitateurs externes"},
    {"code": "BG-SVE-ENT-LOC-2026", "category": "SERVICES_EXT", "description": "Entretien locaux"},
    {"code": "BG-SVE-ENT-VEH-2026", "category": "SERVICES_EXT", "description": "Entretien et reparation vehicules et motos"},
    {"code": "BG-SVE-TEL-INT-2026", "category": "SERVICES_EXT", "description": "Telephone et internet"},
    {"code": "BG-SVE-EAU-ELEC-2026", "category": "SERVICES_EXT", "description": "Eau et electricite"},
    {"code": "BG-SVE-ASS-VEH-2026", "category": "SERVICES_EXT", "description": "Assurances vehicules"},
    {"code": "BG-SVE-VIS-TECH-2026", "category": "SERVICES_EXT", "description": "Visite technique vehicules"},

    # AUTRES SERVICES EXTERIEURS (7)
    {"code": "BG-ASE-PERSO-EXT-2026", "category": "AUTRES_SVC_EXT", "description": "Personnel exterieur"},
    {"code": "BG-ASE-PUB-2026", "category": "AUTRES_SVC_EXT", "description": "Publicite et relations publiques"},
    {"code": "BG-ASE-DEP-REC-2026", "category": "AUTRES_SVC_EXT", "description": "Deplacements et receptions"},
    {"code": "BG-ASE-POST-TEL-2026", "category": "AUTRES_SVC_EXT", "description": "Frais postaux et de telecoms"},
    {"code": "BG-ASE-DIV-IMP-2026", "category": "AUTRES_SVC_EXT", "description": "Divers et imprevus"},
    {"code": "BG-ASE-SITE-2026", "category": "AUTRES_SVC_EXT", "description": "Site internet et supports numeriques"},
    {"code": "BG-ASE-OUTILS-COM-2026", "category": "AUTRES_SVC_EXT", "description": "Outils et supports de communication"},

    # CHARGES DE PERSONNEL (11)
    {"code": "BG-CHP-PERSO-DK-2026", "category": "CHARGES_PERSO_CRT", "description": "Personnel de soutien Dakar"},
    {"code": "BG-CHP-PERSO-SL-2026", "category": "CHARGES_PERSO_CRT", "description": "Personnel de soutien Saint-Louis"},
    {"code": "BG-CHP-PERSO-KED-2026", "category": "CHARGES_PERSO_CRT", "description": "Personnel de soutien Kedougou"},
    {"code": "BG-CHP-IPRES-2026", "category": "IPRES_CSS_2026", "description": "Cotisation annuelle IPRES-CSS 2026"},
    {"code": "BG-CHP-IPRES-DEBT-HIST", "category": "APUR_HISTORIQUE", "description": "Impayes IPRES-CSS 2022-2024 (dette ancienne)"},
    {"code": "BG-CHP-IPRES-DEBT-2025", "category": "APUR_IPRES_2025", "description": "Impayes IPRES-CSS 2025 (4 trimestres non payes)"},
    {"code": "BG-CHP-VRS-2026", "category": "VRS_BRS_CRT", "description": "Impots sur le revenu personnel 2026 (VRS+BRS)"},
    {"code": "BG-CHP-VRS-DEBT-HIST", "category": "APUR_HISTORIQUE", "description": "Impayes IR personnel 2022-2024 (dette ancienne)"},
    {"code": "BG-CHP-VRS-DEBT-2025", "category": "APUR_VRS_BRS_2025", "description": "Impayes IR personnel 2025 (VRS+BRS Jan-Aout)"},
    {"code": "BG-CHP-PERDIEM-2026", "category": "CHARGES_PERSO_CRT", "description": "Perdiem et frais de mission"},
    {"code": "BG-CHP-IPM-2026", "category": "CHARGES_PERSO_CRT", "description": "Assurances sante & IPM"},

    # APPUIS ET SUBVENTIONS (5)
    {"code": "BG-APS-LIGNE1-2026", "category": "APPUIS_SUBV", "description": "Ligne 1 - Subvention (a preciser)"},
    {"code": "BG-APS-LIGNE2-2026", "category": "APPUIS_SUBV", "description": "Ligne 2 - Subvention (a preciser)"},
    {"code": "BG-APS-LIGNE3-2026", "category": "APPUIS_SUBV", "description": "Ligne 3 - Subvention (a preciser)"},
    {"code": "BG-APS-LIGNE4-2026", "category": "APPUIS_SUBV", "description": "Ligne 4 - Subvention (a preciser)"},
    {"code": "BG-APS-LIGNE5-2026", "category": "APPUIS_SUBV", "description": "Ligne 5 - Subvention (a preciser)"},

    # AUTRES CHARGES (6)
    {"code": "BG-AUC-IMP-TAX-2026", "category": "AUTRES_CHARGES", "description": "Impots et taxes"},
    {"code": "BG-AUC-AMORT-2026", "category": "AUTRES_CHARGES", "description": "Dotations aux amortissements"},
    {"code": "BG-AUC-FRAIS-BANC-2026", "category": "AUTRES_CHARGES", "description": "Frais bancaires"},
    {"code": "BG-AUC-FRAIS-TRANS-2026", "category": "AUTRES_CHARGES", "description": "Frais de transfert d'argent"},
    {"code": "BG-AUC-AMENDES-2026", "category": "AUTRES_CHARGES", "description": "Amendes et penalites"},
    {"code": "BG-AUC-AUDIT-2026", "category": "AUTRES_CHARGES", "description": "Audit externe"},
]


class Command(BaseCommand):
    help = "Cree / met a jour les lignes budgetaires analytiques 2026 du Budget General EVE."

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write("Seed lignes budgetaires BG 2026 (analytique)...")

        # 1. Garantir la presence des BudgetCategory utilisees
        categories = {}
        for code, name in CATEGORY_DEFAULTS.items():
            cat, _ = BudgetCategory.objects.update_or_create(
                code=code,
                defaults={"name": name},
            )
            categories[code] = cat

        # 2. Creer les BudgetLine BG (project = None)
        created_count = 0
        updated_count = 0
        for spec in BUDGET_LINES:
            cat = categories.get(spec["category"])
            if cat is None:
                self.stderr.write(f"  /!\\ Categorie '{spec['category']}' introuvable, ligne {spec['code']} ignoree.")
                continue
            line, was_created = BudgetLine.objects.update_or_create(
                code=spec["code"],
                project=None,
                defaults={
                    "category": cat,
                    "description": spec["description"],
                    "currency": "XOF",
                    "fiscal_year": 2026,
                    "planned_amount": Decimal("0"),
                },
            )
            if was_created:
                created_count += 1
            else:
                updated_count += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"BG 2026 : {created_count} lignes creees, {updated_count} mises a jour "
                f"({len(BUDGET_LINES)} attendues)."
            )
        )
