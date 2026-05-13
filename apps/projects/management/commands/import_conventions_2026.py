"""
Renseigne pour chaque projet la contribution au Budget General EVE.

Definition metier arbitree par EVE (13/05/2026):
La contribution d'un projet au Budget General correspond aux LIGNES du
budget projet qui financent en realite le fonctionnement central EVE
(salaires personnel, coordination, frais indirects). Ces lignes ne sont
PAS un overhead unique en %. Selon les bailleurs, elles couvrent un
perimetre plus ou moins large.

Mapping par projet (sources xlsx du dossier eve_pilot_backend) :

- NOUSCIMS-PIK-MBAO-2026 (Pikine Phase II Nutrition)
    Annexe 2_Budget detaille Phase Extension Pikine_EVE.xlsx
    -> rubrique "2. PERSONNEL DU PROJET (40%)" R69 = 57 970 542 FCFA

- NOUSCIMS-SL-2026 (Saint-Louis Gouvernance)
    Annexe 2 Budget detaille Saint-Louis 15-06-2025.xlsx
    -> A.6 TOTAL R116, somme de :
        "1- Staff pour le bureau local de Saint-Louis" R107 = 48 000 000
        "2- Coordination globale du projet"           R112 = 13 279 416
    -> Total = 61 279 416 FCFA

- NOUSCIMS-ECP-2025 (Espaces communautaires Pikine)
    Projet Espaces communautaires (3).xlsx
    -> "2. PERSONNEL DU PROJET" R21 = 8 150 000
    -> "Frais indirect (7%)"     R32 = 1 716 540
    -> Total = 9 866 540 FCFA

- AXA-ISF-2026 (ISF / AXA Climate)
    Budget projet ISF pour Pikine (1).xlsx
    -> Experts (R7-R11)         = 26 850 000 (sous-total HT)
    -> Frais de gestion 10% HT  =  2 685 000
    -> Total = 29 535 000 FCFA (= TOTAL PRESTATION HT)

- OGHOGHO-ECOAVENIR-2026
    Budget previsionnel ECO-AVENIR.xlsx
    -> Ligne A.6 "Assurer la coordination et le suivi du projet"
       = 5 000 EUR convertis ~ 3 279 350 FCFA

- CHILDFUND-INONDATIONS-2025
    P&G_EVE_Budget distribution_Nov.25.xlsx
    -> Ligne "Supervision Project by Partner Local / Support by partner staff"
       = 1 799 289 FCFA

- ONASAFD-PDBH-IEC-2025 (PDBH IEC ONAS-AFD)
    Definition EVE: "reliquat de l'Avenant 2 + toutes les lignes de l'Avenant 2".
    Le fichier de detail de l'Avenant 2 n'est pas present dans le dossier
    actuellement. Marque "a documenter" jusqu'a fourniture des chiffres.

Idempotente: update_or_create par code projet.
"""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.projects.models import Project


# Contributions au Budget General : montants exacts pris dans les conventions.
# pct = ratio amount / total_budget x 100, calcule manuellement et stocke a titre
# indicatif (pas un taux conventionnel uniforme). Laisse a None si non pertinent.
KNOWN_CONTRIBUTIONS = {
    "NOUSCIMS-PIK-MBAO-2026": {
        "amount": Decimal("57970542.40"),
        "pct": Decimal("33.99"),  # 57970542 / 170548815
        "note": (
            "Source: Annexe 2_Budget detaille Phase Extension Pikine_EVE.xlsx, "
            "rubrique '2. PERSONNEL DU PROJET (40%)' (R69). Couvre integralement "
            "le personnel mobilise sur le projet, paye via le Budget General "
            "EVE et non sur le compte projet."
        ),
    },
    "NOUSCIMS-SL-2026": {
        "amount": Decimal("61279416.00"),
        "pct": Decimal("35.93"),  # 61279416 / 170548656
        "note": (
            "Source: Annexe 2 Budget detaille Saint-Louis 15-06-2025.xlsx, "
            "TOTAL A.6 (R116). Decomposition : "
            "'1- Staff bureau local Saint-Louis' = 48 000 000 + "
            "'2- Coordination globale du projet' = 13 279 416. "
            "Sur 3 annees du projet."
        ),
    },
    "NOUSCIMS-ECP-2025": {
        "amount": Decimal("9866540.00"),
        "pct": Decimal("37.60"),  # 9866540 / 26238540
        "note": (
            "Source: Projet Espaces communautaires (3).xlsx. Deux lignes "
            "consolidees : '2. PERSONNEL DU PROJET' R21 = 8 150 000 + "
            "'Frais indirect (7%)' R32 = 1 716 540 FCFA."
        ),
    },
    "AXA-ISF-2026": {
        "amount": Decimal("29535000.00"),
        "pct": Decimal("84.74"),  # 29535000 / 34851300
        "note": (
            "Source: Budget projet ISF pour Pikine (1).xlsx. Couts experts "
            "(R7-R11) = 26 850 000 + Frais de gestion (R13) = 2 685 000 FCFA. "
            "Equivalent au TOTAL PRESTATION HT (R14). Le reliquat (TVA 5,3M "
            "FCFA) est reverse a l'Etat et ne transite pas par le BG."
        ),
    },
    "OGHOGHO-ECOAVENIR-2026": {
        "amount": Decimal("3279350.00"),
        "pct": Decimal("43.47"),  # 3279350 / 7543506
        "note": (
            "Source: Budget previsionnel ECO-AVENIR.xlsx, ligne A.6 'Assurer "
            "la coordination et le suivi du projet' = 5 000 EUR. Description "
            "xlsx : 'Indemnite et frais de deplacement du personnel mobilise "
            "par EVE pour la coordination et le suivi technique et financier'. "
            "Conversion approximative 5 000 EUR -> 3 279 350 FCFA via le ratio "
            "budget total."
        ),
    },
    "CHILDFUND-INONDATIONS-2025": {
        "amount": Decimal("1799289.00"),
        "pct": Decimal("6.77"),  # 1799289 / 26582392
        "note": (
            "Source: P&G_EVE_Budget distribution_Nov.25.xlsx, ligne "
            "'Supervision Project by Partner Local / Support by partner staff' "
            "= 1 799 289 FCFA. Seule ligne du projet ChildFund consideree "
            "comme recette du Budget General EVE."
        ),
    },
    "NOUSCIMS-GT-WALLU-DOOM-2025": {
        "amount": Decimal("103535.00"),
        "pct": Decimal("3.16"),  # 103535 / 3279785
        "note": (
            "Source: budget Campagne Wallu_GT.xlsx, ligne R58 'Frais de gestion' "
            "(orthographiee 'Frais e gestion' dans le xlsx). Seule ligne du "
            "budget consideree comme recette du Budget General EVE pour ce "
            "projet ponctuel (campagne Wallu Dome). Le reste finance "
            "directement les activites de la campagne (preparation, "
            "communication, mobilisation, divers et imprevus)."
        ),
    },
    "ONASAFD-PDBH-IEC-2025": {
        "amount": Decimal("243025423.73"),
        "pct": Decimal("84.75"),  # 243025424 / 286770000 (HT / TTC)
        "note": (
            "Source: extraits comptables SOLDE CLIENT ONAS 2024 et 2025 + "
            "definition contractuelle confirmee par EVE (13/05/2026). "
            "Marche initial 240 990 000 + Avenant 3 PAR 45 780 000 = "
            "286 770 000 FCFA TTC. ONAS precompte la TVA 18% : les encaissements "
            "reels arrivent sur les comptes EVE en HT. La recette du Budget "
            "General correspond donc au montant HT du marche total : "
            "  286 770 000 / 1,18 = 243 025 423,73 FCFA HT. "
            "Decompose : 197 812 797 HT encaisses au 31/12/2025 (cumul 2024+2025) "
            "+ 45 212 626 HT a executer en 2026 (= reliquat 53 350 882 TTC du "
            "xlsx onglet 6). La TVA cumulee 35 606 321 FCFA n'a jamais transite "
            "par EVE, ONAS l'a reversee directement a la DGID."
        ),
    },
}


# Projets dont la contribution reste a documenter (vide aujourd'hui).
PENDING_CONTRIBUTIONS = {}


class Command(BaseCommand):
    help = (
        "Renseigne pour chaque projet la contribution au Budget General "
        "(operating_contribution_amount/pct/note) a partir des conventions "
        "detaillees. Idempotente."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write("Mise a jour des contributions Budget General par projet...")

        for code, data in KNOWN_CONTRIBUTIONS.items():
            self._update(code, data["amount"], data["pct"], data["note"])

        for code, note in PENDING_CONTRIBUTIONS.items():
            self._update(code, None, None, note)

        self.stdout.write(self.style.SUCCESS("Conventions traitees."))

    def _update(self, code, amount, pct, note):
        try:
            project = Project.objects.get(
                code=code, is_active=True, deleted_at__isnull=True
            )
        except Project.DoesNotExist:
            self.stderr.write(f"  /!\\ Project {code} introuvable, ignore.")
            return

        project.operating_contribution_amount = amount
        project.operating_contribution_pct = pct
        project.operating_contribution_note = note
        project.save(
            update_fields=[
                "operating_contribution_amount",
                "operating_contribution_pct",
                "operating_contribution_note",
                "updated_at",
            ]
        )
        if amount is not None:
            pct_str = f"{pct}%" if pct is not None else "n/a"
            self.stdout.write(
                f"  {code}: contribution {amount} FCFA ({pct_str} du budget)"
            )
        else:
            self.stdout.write(f"  {code}: marque 'a documenter'")
