"""
Seed des lignes budgetaires analytiques du projet Saint-Louis Gouvernance.

Source : Budget detaille projet de _saint louis_analytique.pdf
Project : NOUSCIMS-SL-2026

Structure SYCEBNL projet :
- A. Couts directs
    A.1.1 Formations (5 themes, chacun 4 sous-lignes)
    A.1.2 Constructions / Installations
    A.1.3 Equipement / Materiel
    A.1.4 Prestations professionnelles
    A.1.5 AUTRES (11 activites, la plupart avec 4 sous-lignes)
    A.2 Personnel du projet (Staff bureau local + Coordination globale)
    A.3 Suivi, evaluation et apprentissage (3 missions, 3-4 sous-lignes)
    A.4 Depenses administratif (7 lignes location bureau)
    A.5 Divers (3 lignes)
- B. Couts indirects (1 ligne globale)

Categories BudgetCategory creees a la volee si manquantes (PROJ_*).

planned_amount = 0 par defaut (le PDF analytique porte la structure, pas
les montants : ceux-ci sont dans Annexe 2 xlsx detaille au cas par cas).

Idempotente : update_or_create par code BudgetLine.
"""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.finance.models import BudgetLine
from apps.projects.models import Project
from apps.references.models import BudgetCategory


PROJECT_CODE = "NOUSCIMS-SL-2026"


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
}


# --- Helpers pour generer les sous-lignes des sections repetitives ---

FORMATION_SUBLINES = [
    ("Contribution entretien salle",),
    ("Remboursement transport des participants",),
    ("Restauration",),
    ("Outils didactiques",),
]

WORKSHOP_SUBLINES = [
    ("Contribution entretien salle",),
    ("Remboursement transport des participants",),
    ("Restauration",),
    ("Honoraires personnes ressources",),
]

MISSION_SUBLINES = [
    ("Hebergement",),
    ("Remboursement transport",),
    ("Location vehicule",),
    ("Carburant mission",),
]


def make_lines():
    """Construit la liste exhaustive des BudgetLine Saint-Louis."""
    lines = []

    # A.1.1 Formations : 5 themes, chacun 4 sous-lignes "FORMATION"
    formations = [
        "Orientation et formation des elus et membres des equipes des CT sur la nutrition",
        "Renforcement de capacites des acteurs representant secteurs contributifs / societe civile / acteurs communautaires",
        "Renforcement des capacites de planification et de suivi des interventions de nutrition",
        "Formation et renforcement de capacite des prestataires de services (PECMAS) - Fass Ngom",
        "Formation des acteurs communautaires sur la PECMAM et la CIP",
    ]
    for t_idx, theme in enumerate(formations, start=1):
        for s_idx, (sub_label,) in enumerate(FORMATION_SUBLINES, start=1):
            lines.append({
                "code": f"SL-A111-T{t_idx}-S{s_idx}-2026",
                "category": "PROJ_FORMATION",
                "description": f"A.1.1 Theme {t_idx} ({theme[:60]}) - {sub_label}",
            })

    # A.1.2 Constructions / Installations
    # (Aucune sous-ligne explicite dans le PDF, on cree une ligne placeholder)
    lines.append({
        "code": "SL-A112-CONSTR-2026",
        "category": "PROJ_FORMATION",
        "description": "A.1.2 Constructions / Installations (a preciser)",
    })

    # A.1.3 Equipement / Materiel (10 lignes)
    equipements = [
        "Tables de bureau",
        "Chaises visiteurs",
        "Table de reunion",
        "Chaises de reunion",
        "Ordinateurs portables (i5 min.)",
        "Imprimante multifonctions (scan/copy/print)",
        "Photocopieuse de bureau (A3-A4)",
        "Televiseur smart (50-55 pouces) de projection",
        "Climatisation de 3 pieces de bureau et montage",
        "Materiels roulants (motos)",
    ]
    for idx, label in enumerate(equipements, start=1):
        lines.append({
            "code": f"SL-A113-{idx:02d}-2026",
            "category": "PROJ_EQUIPEMENT",
            "description": f"A.1.3 {label}",
        })

    # A.1.4 Prestations professionnelles (3 lignes)
    prestations = [
        "Convention avec acteurs communautaires pour delivrance services nutrition (CIP et PECMA)",
        "Prise en charge des enfants depistes MAM lors des campagnes semestrielles",
        "Prise en charge des enfants depistes MAS lors des campagnes semestrielles",
    ]
    for idx, label in enumerate(prestations, start=1):
        lines.append({
            "code": f"SL-A114-{idx:02d}-2026",
            "category": "PROJ_PRESTATION",
            "description": f"A.1.4 {label}",
        })

    # A.1.5 AUTRES (11 activites de mobilisation et de gouvernance)
    a115_activities = [
        ("1", "Ceremonie de lancement (Prefet, MCD, CD, Communes, ARD, OSC)", WORKSHOP_SUBLINES, [("Cocktail", 3)]),
        ("2", "Appui mise en place / fonctionnement CDDN Saint-Louis", WORKSHOP_SUBLINES, None),
        ("3", "Appui aux 5 cadres communaux de gouvernance territoriale", WORKSHOP_SUBLINES, None),
        ("4", "Atelier elaboration feuilles de routes (departemental + communal)", WORKSHOP_SUBLINES, None),
        ("5", "Rencontres annuelles de suivi feuilles de routes (5 communes)", WORKSHOP_SUBLINES, None),
        ("6", "Appui elaboration et mise en oeuvre des PAN communaux", WORKSHOP_SUBLINES, None),
        ("8", "Rencontres planification campagnes semestrielles depistage", WORKSHOP_SUBLINES, None),
        ("10", "Rencontres evaluation campagnes semestrielles depistage", [
            ("Contribution entretien salle",),
            ("Remboursement transport des participants",),
            ("Restauration",),
            ("Rembousement personnes ressources",),
        ], None),
    ]
    for code_num, title, subs, overrides in a115_activities:
        sub_list = list(subs)
        if overrides:
            for new_label, replace_idx in overrides:
                sub_list[replace_idx - 1] = (new_label,)
        for s_idx, (sub_label,) in enumerate(sub_list, start=1):
            lines.append({
                "code": f"SL-A115-{code_num}-S{s_idx}-2026",
                "category": "PROJ_ACTIVITES",
                "description": f"A.1.5/{code_num} {title} - {sub_label}",
            })

    # A.1.5/7 Plaidoyer - Fora communautaires (sous-structure differente)
    fora_sublines = [
        "Location de sonorisation + micros",
        "Rafraichissements et collation",
        "Chaises",
        "Bache",
        "Honoraires personnes ressources",
    ]
    for s_idx, sub_label in enumerate(fora_sublines, start=1):
        lines.append({
            "code": f"SL-A115-7-S{s_idx}-2026",
            "category": "PROJ_ACTIVITES",
            "description": f"A.1.5/7 Plaidoyer - Fora communautaires - {sub_label}",
        })

    # A.1.5/9 Campagnes semestrielles dépistage (2 sous-lignes specifiques)
    lines.append({
        "code": "SL-A115-9-S1-2026",
        "category": "PROJ_ACTIVITES",
        "description": "A.1.5/9 Campagnes depistage - Prise en charge ICP, Point focal, equipe cadre district / niveau central",
    })
    lines.append({
        "code": "SL-A115-9-S2-2026",
        "category": "PROJ_ACTIVITES",
        "description": "A.1.5/9 Campagnes depistage - Appui prise en charge des relais",
    })

    # A.1.5/11 Rehabilitation CREN et UREN (1 ligne)
    lines.append({
        "code": "SL-A115-11-2026",
        "category": "PROJ_ACTIVITES",
        "description": "A.1.5/11 Rehabilitation des locaux abritant CREN et UREN dans les postes de sante",
    })

    # A.2 Personnel du projet
    # Sous-section 1 - Staff bureau local Saint-Louis
    staff_local = [
        "Chef de projet, charge du suivi evaluation (1 poste a 100%)",
        "Animateurs charges des concertations (2 postes a 100%)",
        "Secretaire comptable (1 poste a 100%)",
        "Superviseurs (2 postes a 100%)",
    ]
    for idx, label in enumerate(staff_local, start=1):
        lines.append({
            "code": f"SL-A2-STAFF-{idx:02d}-2026",
            "category": "PROJ_PERSONNEL",
            "description": f"A.2/1 Staff bureau local - {label}",
        })
    # Sous-section 2 - Coordination globale
    coordination = [
        "Coordonnateur politique (1 poste a 15%)",
        "Assistant administratif et financier (1 poste a 50%)",
        "Chauffeur (1 poste a 100%)",
    ]
    for idx, label in enumerate(coordination, start=1):
        lines.append({
            "code": f"SL-A2-COORD-{idx:02d}-2026",
            "category": "PROJ_PERSONNEL",
            "description": f"A.2/2 Coordination globale - {label}",
        })

    # A.3 Suivi, evaluation et apprentissage (3 missions x 3-4 sous-lignes)
    missions = [
        ("1", "Mission conjointe suivi-supervision (CNDN, Plateforme SUN, EVE)", MISSION_SUBLINES),
        ("2", "Mission d'appui, de suivi et de supervision du siege", MISSION_SUBLINES),
        ("3", "Mission de supervision du bureau local", [
            ("Remboursement transport",),
            ("Location vehicule",),
            ("Carburant mission",),
        ]),
    ]
    for m_num, m_title, sublines in missions:
        for s_idx, (sub_label,) in enumerate(sublines, start=1):
            lines.append({
                "code": f"SL-A3-{m_num}-S{s_idx}-2026",
                "category": "PROJ_SUIVI",
                "description": f"A.3/{m_num} {m_title} - {sub_label}",
            })

    # A.4 Depenses administratif (7 lignes)
    admin_lines = [
        "Location bureau",
        "Frais Electricite",
        "Internet/telephone fixe",
        "Consommables de bureau",
        "Produits d'entretien",
        "Eau",
        "Entretien carburant moto",
    ]
    for idx, label in enumerate(admin_lines, start=1):
        lines.append({
            "code": f"SL-A4-{idx:02d}-2026",
            "category": "PROJ_ADMIN",
            "description": f"A.4 {label}",
        })

    # A.5 Divers (3 lignes)
    divers_lines = [
        "Personnel de soutien : Femme de charge",
        "Elaboration outils de gestion (fiches croissance, registres depistage, prise en charge enfants depistes)",
        "Communication et visibilite (supports de communication, communication digitale et tele/radio, etc.)",
    ]
    for idx, label in enumerate(divers_lines, start=1):
        lines.append({
            "code": f"SL-A5-{idx:02d}-2026",
            "category": "PROJ_DIVERS",
            "description": f"A.5 {label}",
        })

    # B. Couts indirects (1 ligne globale = 10% des couts directs)
    lines.append({
        "code": "SL-B-INDIRECT-2026",
        "category": "PROJ_INDIRECTS",
        "description": "B. Couts indirects (10% des couts directs totaux)",
    })

    return lines


class Command(BaseCommand):
    help = "Cree / met a jour les lignes budgetaires analytiques du projet Saint-Louis Gouvernance."

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            project = Project.objects.get(
                code=PROJECT_CODE, is_active=True, deleted_at__isnull=True
            )
        except Project.DoesNotExist:
            self.stderr.write(f"Project '{PROJECT_CODE}' introuvable.")
            return

        self.stdout.write(f"Seed lignes budgetaires {PROJECT_CODE} (analytique)...")

        # Garantir les BudgetCategory projet
        categories = {}
        for code, name in PROJECT_CATEGORIES.items():
            cat, _ = BudgetCategory.objects.update_or_create(
                code=code,
                defaults={"name": name},
            )
            categories[code] = cat

        specs = make_lines()
        created_count = 0
        updated_count = 0
        for spec in specs:
            cat = categories.get(spec["category"])
            if cat is None:
                self.stderr.write(f"  /!\\ Categorie '{spec['category']}' introuvable, ligne {spec['code']} ignoree.")
                continue
            line, was_created = BudgetLine.objects.update_or_create(
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
                created_count += 1
            else:
                updated_count += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"{PROJECT_CODE} : {created_count} lignes creees, {updated_count} mises a jour "
                f"({len(specs)} attendues)."
            )
        )
