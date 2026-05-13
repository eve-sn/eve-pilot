"""
Seed des lignes budgetaires analytiques des projets restants (hors BG et
Saint-Louis qui ont leurs commandes dediees).

Couvre 5 projets :
  - CHILDFUND-INONDATIONS-2025 (P&G_EVE_Budget distribution_analytique.pdf)
  - OGHOGHO-ECOAVENIR-2026 (Budget previsionnel ECO-AVENIR_analytique.pdf)
  - NOUSCIMS-ECP-2025 (Projet Espaces communautaires ... _analytique.pdf)
  - NOUSCIMS-PIK-MBAO-2026 (Budget detaille Phase Extension Pikine_EVE_Analytique.pdf)
  - NOUSCIMS-GT-WALLU-DOOM-2025 (budget Campagne Wallu_GT_analytique.pdf)

planned_amount = 0 par defaut. Idempotent via update_or_create par (code, project).
"""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.finance.models import BudgetLine
from apps.projects.models import Project
from apps.references.models import BudgetCategory


# Categories projet partagees avec Saint-Louis (deja seedees) + nouvelles.
PROJECT_CATEGORIES = {
    "PROJ_FORMATION": "Formations (projet)",
    "PROJ_EQUIPEMENT": "Equipement et materiel (projet)",
    "PROJ_PRESTATION": "Prestations professionnelles (projet)",
    "PROJ_ACTIVITES": "Activites et evenements (projet)",
    "PROJ_PERSONNEL": "Personnel projet",
    "PROJ_SUIVI": "Suivi, evaluation et apprentissage",
    "PROJ_ADMIN": "Depenses administratives projet",
    "PROJ_DIVERS": "Divers projet",
    "PROJ_INDIRECTS": "Couts indirects projet",
    "PROJ_LOGISTIQUE": "Logistique projet (transport, entrepot, distribution)",
    "PROJ_COMMUNICATION": "Communication projet (CCC, supports, medias)",
    "PROJ_INTRANTS": "Intrants et acquisitions projet",
}


# Helpers de generation des sous-lignes ----------------------------------

FORMATION_PIKINE_SUB = [
    ("a", "Location salle"),
    ("b", "Remboursement transport des participants"),
    ("c", "Restauration participant"),
    ("d", "Outils didactiques"),
    ("e", "Honoraires facilitateurs"),
]

WORKSHOP_4 = [
    ("a", "Contribution entretien salle"),
    ("b", "Remboursement transport des participants"),
    ("c", "Restauration"),
    ("e", "Honoraires facilitateurs"),
]


def _add(lines, code, category, description):
    lines.append({"code": code, "category": category, "description": description})


# CHILDFUND - INONDATIONS ------------------------------------------------

def childfund_lines():
    lines = []
    # Objectif 1 : Accès à l'eau potable
    _add(lines, "CF-O1-START-2026", "PROJ_ACTIVITES", "O1/Atelier demarrage (personnel interne projet)")
    # 1.1 Couts d'expedition
    _add(lines, "CF-O1-1-1-2026", "PROJ_LOGISTIQUE", "O1/1.1 Couts d'expedition des conteneurs")
    _add(lines, "CF-O1-1-2-2026", "PROJ_INTRANTS", "O1/1.1 Sachets de traitement de l'eau")
    # 1.2 Distribution
    _add(lines, "CF-O1-1-2-A-2026", "PROJ_LOGISTIQUE", "O1/1.2 Main-d'oeuvre temporaire pour dechargement")
    _add(lines, "CF-O1-1-2-B-2026", "PROJ_LOGISTIQUE", "O1/1.2 Frais d'entrepot")
    _add(lines, "CF-O1-1-2-C-2026", "PROJ_LOGISTIQUE", "O1/1.2 Frais de securite a l'entrepot")
    _add(lines, "CF-O1-1-2-D-2026", "PROJ_LOGISTIQUE", "O1/1.2 Transport vers zones de distribution")
    _add(lines, "CF-O1-1-2-E-2026", "PROJ_LOGISTIQUE", "O1/1.2 Carburant pour tous modes de transport")
    _add(lines, "CF-O1-1-2-F-2026", "PROJ_LOGISTIQUE", "O1/1.2 Nourriture et boissons pour les benevoles")
    # 1.3 Voyage / supervision
    _add(lines, "CF-O1-1-3-A-2026", "PROJ_SUIVI", "O1/1.3 Voyage - Soutien du personnel du partenaire")
    _add(lines, "CF-O1-1-3-B-2026", "PROJ_SUIVI", "O1/1.3 Voyage - Vehicule de location")
    _add(lines, "CF-O1-1-3-C-2026", "PROJ_SUIVI", "O1/1.3 Voyage - Hebergement")
    _add(lines, "CF-O1-1-3-D-2026", "PROJ_SUIVI", "O1/1.3 Voyage - Reunion de coordination")
    # Objectif 2 : Hygiene et assainissement
    _add(lines, "CF-O2-MOB-2026", "PROJ_ACTIVITES", "O2/Mobilisation - Sensibiliser a la resilience face aux inondations")
    # Formation promoteurs hygiene
    _add(lines, "CF-O2-FP-A-2026", "PROJ_FORMATION", "O2/Formation promoteurs - Acteurs communautaires soutien")
    _add(lines, "CF-O2-FP-B-2026", "PROJ_FORMATION", "O2/Formation promoteurs - Facilitateurs soutien")
    _add(lines, "CF-O2-FP-C-2026", "PROJ_FORMATION", "O2/Formation promoteurs - Transport participants")
    _add(lines, "CF-O2-FP-D-2026", "PROJ_FORMATION", "O2/Formation promoteurs - Materiel didactique")
    # Formation comite direction
    _add(lines, "CF-O2-FD-A-2026", "PROJ_FORMATION", "O2/Formation comite direction - Formation formateurs")
    _add(lines, "CF-O2-FD-B-2026", "PROJ_FORMATION", "O2/Formation comite direction - Paiement facilitateurs")
    _add(lines, "CF-O2-FD-C-2026", "PROJ_FORMATION", "O2/Formation comite direction - Transport participants")
    _add(lines, "CF-O2-FD-D-2026", "PROJ_FORMATION", "O2/Formation comite direction - Materiel didactique")
    # CDD + post-formation
    _add(lines, "CF-O2-CDD-2026", "PROJ_ACTIVITES", "O2/Reunion comite developpement departemental (CDD)")
    _add(lines, "CF-O2-POST-2026", "PROJ_SUIVI", "O2/Suivi post-formation")
    # Equipement + supports
    _add(lines, "CF-O2-KIT-2026", "PROJ_EQUIPEMENT", "O2/Equipement - Kit d'hygiene")
    _add(lines, "CF-O2-DISTR-2026", "PROJ_LOGISTIQUE", "O2/Soutien acteurs locaux pour distribution materiel")
    _add(lines, "CF-O2-CCC-2026", "PROJ_COMMUNICATION", "O2/Production supports et messages CCC sur hygiene et assainissement")
    return lines


# OGHOGHO - ECO-AVENIR ---------------------------------------------------

def ecoavenir_lines():
    lines = []
    # A.1 Formation formateurs
    _add(lines, "ECO-A1-1-2026", "PROJ_FORMATION", "A.1 Mobiliser un formateur")
    _add(lines, "ECO-A1-2-2026", "PROJ_FORMATION", "A.1 Prise en charge restauration enseignants")
    _add(lines, "ECO-A1-3-2026", "PROJ_FORMATION", "A.1 Reprographier outils et supports didactiques")
    _add(lines, "ECO-A1-4-2026", "PROJ_EQUIPEMENT", "A.1 Acheter materiel didactique")
    # A.2 Modules formations
    _add(lines, "ECO-A2-1-2026", "PROJ_FORMATION", "A.2 Prise en charge seances de travail (dej / pause-cafe)")
    _add(lines, "ECO-A2-2-2026", "PROJ_FORMATION", "A.2 Remboursement transport personnes ressources / inspections")
    # A.3 Espaces apprentissage
    _add(lines, "ECO-A3-1-2026", "PROJ_EQUIPEMENT", "A.3 Confection 6 panneaux 3m x 2,5m")
    # A.4 Sorties pedagogiques
    _add(lines, "ECO-A4-1-2026", "PROJ_ACTIVITES", "A.4 Frais de transport sorties pedagogiques")
    _add(lines, "ECO-A4-2-2026", "PROJ_ACTIVITES", "A.4 Frais de collation sorties pedagogiques")
    # A.5 Supports communication
    _add(lines, "ECO-A5-1-2026", "PROJ_COMMUNICATION", "A.5 Production de videos courtes sur activites projet")
    # A.6 Coordination
    _add(lines, "ECO-A6-2026", "PROJ_PERSONNEL", "A.6 Coordination et suivi du projet (personnel EVE)")
    return lines


# NOUSCIMS - ECP --------------------------------------------------------

def ecp_lines():
    lines = []
    _add(lines, "ECP-1-1-1-2026", "PROJ_FORMATION", "1.1.1 Appui organisationnel - Formation 12 groupements (3 thematiques, 4 jours, 8000 FCFA/participant)")
    _add(lines, "ECP-1-1-2-2026", "PROJ_FORMATION", "1.1.2 Honoraires de 6 facilitateurs (15000 FCFA/jour, 4 jours)")
    _add(lines, "ECP-1-2-1-2026", "PROJ_EQUIPEMENT", "1.2.1 Amenagement de 12 espaces de commercialisation (500000 FCFA/espace)")
    _add(lines, "ECP-1-2-2-2026", "PROJ_EQUIPEMENT", "1.2.2 Achat petits equipements (ustensiles, materiels - 100000 FCFA/groupement)")
    _add(lines, "ECP-1-2-3-2026", "PROJ_INTRANTS", "1.2.3 Intrants de base produits alimentaires (100000 FCFA/groupement)")
    _add(lines, "ECP-2-1-2026", "PROJ_PERSONNEL", "2.1 Gestionnaire du projet 100% (350000 FCFA x 13 mois)")
    _add(lines, "ECP-2-2-2026", "PROJ_PERSONNEL", "2.2 Animateurs (2 postes, 150000 FCFA x 12 mois)")
    _add(lines, "ECP-5-1-2026", "PROJ_DIVERS", "5.1 Fond de roulement (50000 FCFA/groupement, 1 mois)")
    _add(lines, "ECP-5-2-2026", "PROJ_COMMUNICATION", "5.2 Communication et brandings (100000 FCFA/mois, 12 mois)")
    _add(lines, "ECP-5-3-2026", "PROJ_SUIVI", "5.3 Suivi des activites (5620 FCFA/groupement supervise)")
    _add(lines, "ECP-INDIRECT-2026", "PROJ_INDIRECTS", "Frais indirect 7% du total direct")
    return lines


# NOUSCIMS - PIKINE PHASE II --------------------------------------------

def pikine_lines():
    lines = []
    # 1.1.1 Sessions CIP (5 sublignes a-e)
    for letter, sub in FORMATION_PIKINE_SUB:
        _add(lines, f"PIK-1-1-1-{letter.upper()}-2026", "PROJ_FORMATION",
             f"1.1.1 Sessions formation/recyclage CIP - {sub}")
    # 1.1.2 Renforcement femmes pole emploi
    for letter, sub in FORMATION_PIKINE_SUB:
        _add(lines, f"PIK-1-1-2-{letter.upper()}-2026", "PROJ_FORMATION",
             f"1.1.2 Renforcement capacites femmes pole emploi - {sub}")
    # 1.2 Constructions
    _add(lines, "PIK-1-2-CONSTR-2026", "PROJ_EQUIPEMENT", "1.2 Constructions / Installations")
    # 1.3 Equipement
    _add(lines, "PIK-1-3-1-2026", "PROJ_EQUIPEMENT", "1.3.1 Equipement sites communautaires (Muacs, fiches, registres, outils)")
    # 1.4 Prestations professionnelles
    _add(lines, "PIK-1-4-DEP-A-2026", "PROJ_PRESTATION", "1.4 Depistage semestriel - Prise en charge relais communautaires")
    _add(lines, "PIK-1-4-DEP-B-2026", "PROJ_PRESTATION", "1.4 Depistage semestriel - Prise en charge ICP")
    _add(lines, "PIK-1-4-DEP-C-2026", "PROJ_PRESTATION", "1.4 Depistage semestriel - Prise en charge points focaux communes")
    _add(lines, "PIK-1-4-CIP-A-2026", "PROJ_ACTIVITES", "1.4 Activites CIP - Frais d'organisation discussions de groupe")
    _add(lines, "PIK-1-4-CIP-B-2026", "PROJ_ACTIVITES", "1.4 Activites CIP - Prise en charge relais (causeries educatives)")
    _add(lines, "PIK-1-4-CIP-C-2026", "PROJ_ACTIVITES", "1.4 Activites CIP - Prise en charge relais (VAD)")
    # 1.5 AUTRES
    # FARNE
    _add(lines, "PIK-1-5-FAR-A-2026", "PROJ_ACTIVITES", "1.5 FARNE - Appui animation foyers MAM")
    _add(lines, "PIK-1-5-FAR-B-2026", "PROJ_ACTIVITES", "1.5 FARNE - Prise en charge cas MAM depistes")
    # Debat public nutrition
    for letter, sub in WORKSHOP_4:
        _add(lines, f"PIK-1-5-DEB-{letter.upper()}-2026", "PROJ_ACTIVITES",
             f"1.5 Debat public nutrition CCDN - {sub}")
    # Fora plaidoyer
    _add(lines, "PIK-1-5-FOR-A-2026", "PROJ_ACTIVITES", "1.5 Fora plaidoyer DOB - Contribution entretien salle")
    _add(lines, "PIK-1-5-FOR-B-2026", "PROJ_ACTIVITES", "1.5 Fora plaidoyer DOB - Rafraichissements et collation")
    _add(lines, "PIK-1-5-FOR-C-2026", "PROJ_ACTIVITES", "1.5 Fora plaidoyer DOB - Facilitateurs")
    # Appui CDDN Pikine
    cddn_subs = [("a", "Contribution entretien salle"), ("b", "Remboursement transport"),
                 ("c", "Restauration"), ("d", "Facilitateurs/Experts"),
                 ("e", "Honoraires autorites locales et administratives")]
    for letter, sub in cddn_subs:
        _add(lines, f"PIK-1-5-CDDN-{letter.upper()}-2026", "PROJ_ACTIVITES",
             f"1.5 Appui CDDN Pikine - {sub}")
    # Rencontres planification campagnes
    rcp_subs = [("a", "Contribution entretien salle"), ("b", "Remboursement transport"),
                ("c", "Restauration"), ("d", "Honoraires personnes ressources")]
    for letter, sub in rcp_subs:
        _add(lines, f"PIK-1-5-CMP-{letter.upper()}-2026", "PROJ_ACTIVITES",
             f"1.5 Rencontres planif campagnes - {sub}")
    # Appui mise en oeuvre initiatives femmes
    _add(lines, "PIK-1-5-INIT-2026", "PROJ_ACTIVITES", "1.5 Appui initiatives femmes Pikine (aliments diversifies)")
    # Appui CCDN 12 communes
    ccdn_subs = [("a", "Contribution entretien salle"), ("b", "Remboursement transport"),
                 ("c", "Restauration"), ("e", "Honoraires personnes ressources")]
    for letter, sub in ccdn_subs:
        _add(lines, f"PIK-1-5-CCD-{letter.upper()}-2026", "PROJ_ACTIVITES",
             f"1.5 Appui CCDN 12 communes - {sub}")
    # Evenements innovations culinaires
    _add(lines, "PIK-1-5-EVT-2026", "PROJ_ACTIVITES", "1.5 Evenements innovations culinaires produits locaux")
    # 2 Personnel (6 postes - 40% perimetre projet)
    personnel = [
        ("a", "Coordonnateur Politique (10%)"),
        ("b", "Charge de projet (1 poste 100%)"),
        ("c", "Charge suivi-evaluation (70%)"),
        ("d", "Specialiste concertations / engagement communautaire (30%)"),
        ("e", "Assistant administratif et financier (50%)"),
        ("f", "Facilitateurs de district (4 postes 100%)"),
    ]
    for letter, sub in personnel:
        _add(lines, f"PIK-2-{letter.upper()}-2026", "PROJ_PERSONNEL",
             f"2 Personnel projet (40%) - {sub}")
    # 3 Suivi
    suivi = [
        "Mission supervision campagnes par ICP",
        "Mission supervision membres equipes cadre district / niveau central",
        "Mission supervision points focaux collectivites territoriales",
        "Mission supervision staff projet",
        "Carburant vehicules supervision + prise en charge chauffeurs",
        "Mission supervision initiatives communautaires (autorites administratives)",
        "Participation ateliers d'apprentissage FNC",
    ]
    for idx, sub in enumerate(suivi, start=1):
        _add(lines, f"PIK-3-{idx:02d}-2026", "PROJ_SUIVI", f"3 Suivi - {sub}")
    # 4 Admin
    _add(lines, "PIK-4-1-2026", "PROJ_ADMIN", "4 Contribution charges fixes (telephone, ADSL, eau, electricite)")
    _add(lines, "PIK-4-2-2026", "PROJ_ADMIN", "4 Contribution location siege")
    # 5 Divers
    _add(lines, "PIK-5-1-2026", "PROJ_COMMUNICATION", "5 Communication et visibilite (supports, digital, protocoles medias)")
    # Indirect
    _add(lines, "PIK-INDIRECT-2026", "PROJ_INDIRECTS", "Frais indirect 10% du total direct")
    return lines


# NOUSCIMS - GT WALLU DOOM ----------------------------------------------

def gt_wallu_lines():
    lines = []
    # A.2 Communication / strategie media
    _add(lines, "GT-A2-BAND-2026", "PROJ_COMMUNICATION", "A.2 Communication - Banderoles")
    _add(lines, "GT-A2-VID-2026", "PROJ_COMMUNICATION", "A.2 Communication - Production capsules videos promotion")
    _add(lines, "GT-A2-PRX-A-2026", "PROJ_COMMUNICATION", "A.2 Communication proximite - Portes a portes")
    _add(lines, "GT-A2-PRX-B-2026", "PROJ_COMMUNICATION", "A.2 Communication proximite - Crieurs publics")
    _add(lines, "GT-A2-PRX-C-2026", "PROJ_COMMUNICATION", "A.2 Communication proximite - Radios communautaires")
    # Mobilisation
    _add(lines, "GT-MOB-PREF-2026", "PROJ_ACTIVITES", "Mobilisation - Remboursement transport prefet")
    _add(lines, "GT-MOB-SPREF-2026", "PROJ_ACTIVITES", "Mobilisation - Remboursement transport sous-prefet")
    _add(lines, "GT-MOB-SECT-2026", "PROJ_ACTIVITES", "Mobilisation - Remboursement sectoriels")
    _add(lines, "GT-MOB-PERS-2026", "PROJ_ACTIVITES", "Mobilisation - Remboursement personnes ressources")
    _add(lines, "GT-MOB-COM-2026", "PROJ_ACTIVITES", "Mobilisation des acteurs communautaires")
    _add(lines, "GT-MOB-GT-2026", "PROJ_ACTIVITES", "Mobilisation des membres du GT")
    _add(lines, "GT-MOB-MED-2026", "PROJ_COMMUNICATION", "Mobilisation - Couverture mediatique")
    _add(lines, "GT-MOB-REST-2026", "PROJ_ACTIVITES", "Mobilisation - Restauration des participants")
    # B. Campagne (seances demonstration culinaires)
    _add(lines, "GT-B-INT-2026", "PROJ_INTRANTS", "B.Campagne - Achat d'intrants culinaires")
    _add(lines, "GT-B-ACC-2026", "PROJ_INTRANTS", "B.Campagne - Achat accessoires (gobelets, plats, ustensiles)")
    _add(lines, "GT-B-GAZ-2026", "PROJ_INTRANTS", "B.Campagne - Recharge gaz butane")
    # D. Divers et imprevus
    _add(lines, "GT-D-DIV-2026", "PROJ_DIVERS", "D. Divers et imprevus")
    # Frais gestion
    _add(lines, "GT-FRAIS-2026", "PROJ_INDIRECTS", "Frais de gestion (couts indirects)")
    return lines


PROJECT_SPECS = {
    "CHILDFUND-INONDATIONS-2025": childfund_lines,
    "OGHOGHO-ECOAVENIR-2026": ecoavenir_lines,
    "NOUSCIMS-ECP-2025": ecp_lines,
    "NOUSCIMS-PIK-MBAO-2026": pikine_lines,
    "NOUSCIMS-GT-WALLU-DOOM-2025": gt_wallu_lines,
}


class Command(BaseCommand):
    help = "Seed les BudgetLine analytiques des 5 projets restants (ECP, Pikine PhII, GT, ECO-AVENIR, ChildFund)."

    @transaction.atomic
    def handle(self, *args, **options):
        # Garantir les BudgetCategory
        categories = {}
        for code, name in PROJECT_CATEGORIES.items():
            cat, _ = BudgetCategory.objects.update_or_create(
                code=code, defaults={"name": name}
            )
            categories[code] = cat

        total_created = 0
        total_updated = 0
        for project_code, lines_fn in PROJECT_SPECS.items():
            try:
                project = Project.objects.get(
                    code=project_code, is_active=True, deleted_at__isnull=True
                )
            except Project.DoesNotExist:
                self.stderr.write(f"  /!\\ Project {project_code} introuvable, skip.")
                continue

            specs = lines_fn()
            created = 0
            updated = 0
            for spec in specs:
                cat = categories.get(spec["category"])
                if cat is None:
                    self.stderr.write(f"  /!\\ Categorie {spec['category']} introuvable pour {spec['code']}.")
                    continue
                _, was_created = BudgetLine.objects.update_or_create(
                    code=spec["code"],
                    project=project,
                    defaults={
                        "category": cat,
                        "description": spec["description"][:1000],
                        "currency": "XOF",
                        "fiscal_year": 2026,
                        "planned_amount": Decimal("0"),
                    },
                )
                if was_created:
                    created += 1
                else:
                    updated += 1
            self.stdout.write(
                f"  {project_code}: {created} creees, {updated} mises a jour "
                f"({len(specs)} attendues)."
            )
            total_created += created
            total_updated += updated

        self.stdout.write(
            self.style.SUCCESS(
                f"Total : {total_created} BudgetLine creees, {total_updated} mises a jour sur 5 projets."
            )
        )
