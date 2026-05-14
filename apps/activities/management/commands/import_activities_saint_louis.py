# -*- coding: utf-8 -*-
"""
Import des activites du projet Saint-Louis Gouvernance depuis le cadre logique.

Source : "Annexe 1- Matrice du cadre logique du projet de Saint-Louis-revu.docx"
Projet  : NOUSCIMS-SL-2026

Le cadre logique decrit 2 objectifs specifiques, 3 resultats attendus et
17 activites prevues. Cette commande cree une Activity par activite prevue.

Limites assumees (le cadre logique ne les porte pas) :
  - planned_start_date : laisse vide (le cadre logique n'est pas calendarise).
  - planned_budget     : laisse vide (les montants sont dans le budget detaille,
                         importe separement comme BudgetLine).
  - responsible        : laisse vide.
  - activity_type      : laisse vide.
Ces champs sont a completer ensuite via l'UI d'edition.

Idempotente : update_or_create par (project, code).
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.activities.models import Activity
from apps.projects.models import Project

PROJECT_CODE = "NOUSCIMS-SL-2026"

# Objectifs specifiques du cadre logique.
OS1 = (
    "Appuyer la mise en place et le fonctionnement de cadres multisectoriels "
    "de gouvernance et d'institutionnalisation de la nutrition aux niveaux "
    "departemental et communal a Saint-Louis"
)
OS2 = (
    "Renforcer les dispositifs de prevention et de prise en charge de la "
    "nutrition dans les communes de Fass Ngom et Mpal"
)

# Resultats attendus -> (code resultat, objectif specifique, libelle resultat, [activites]).
LOGFRAME = [
    (
        "R1",
        1,
        OS1,
        "Un cadre departemental et 5 cadres communaux de gouvernance "
        "territoriale sensible a la nutrition sont mis en place et "
        "fonctionnels dans le departement de Saint-Louis",
        [
            "Rencontre de partage et de lancement du projet (Prefet, MCD, "
            "Conseil departemental, Communes, ARD, services techniques "
            "contributifs)",
            "Orientation et formation des elus et membres des equipes "
            "municipales sur la nutrition (elus, points focaux nutrition, "
            "secretaires municipaux)",
            "Renforcement de capacites des acteurs des secteurs contributifs, "
            "de la societe civile et des acteurs communautaires sur la nutrition",
            "Appui a la mise en place du Comite Departemental de Developpement "
            "de la Nutrition (CDDN) de Saint-Louis",
            "Appui a la mise en place et au fonctionnement des 5 cadres "
            "territoriaux de concertation (Saint-Louis, Mpal, Fass Ngom, "
            "Gandon et Ndiebene Gandiol)",
            "Appui a l'animation et au fonctionnement du CDDN et des 5 CLDN",
        ],
    ),
    (
        "R2",
        1,
        OS1,
        "La nutrition est inscrite comme priorite des collectivites "
        "territoriales avec des ressources dediees",
        [
            "Renforcement des capacites de planification et de suivi des "
            "interventions de nutrition (elus, equipes techniques des CT, "
            "secteurs cles, societe civile)",
            "Appui a l'elaboration et a la mise en oeuvre de plans d'action "
            "communaux de nutrition",
            "Sessions de plaidoyer en faveur de la nutrition aupres des "
            "collectivites territoriales (fora communautaires, mobilisations "
            "sociales) lors des Debats d'Orientation Budgetaire",
        ],
    ),
    (
        "R3",
        2,
        OS2,
        "Les dispositifs de prevention et de prise en charge communautaire et "
        "clinique de la malnutrition sont renforces dans les communes de Fass "
        "Ngom et Mpal",
        [
            "Signature de conventions tripartites (communes de Fass Ngom et "
            "Mpal, acteurs communautaires, EVE) pour la delivrance des "
            "services de prevention et de prise en charge de la malnutrition "
            "aigue",
            "Formation et renforcement des prestataires de services dans la "
            "zone de polarisation des communes de Fass Ngom et Mpal sur la PECMAS",
            "Formation des acteurs communautaires sur la CIP",
            "Formation des acteurs communautaires sur la PECMAM",
            "Rencontres de planification des campagnes semestrielles de "
            "depistage de la malnutrition aigue chez les enfants 6-59 mois",
            "Organisation de campagnes de depistage semestriel de la "
            "malnutrition chez les enfants 6-59 mois dans les communes de "
            "Fass Ngom et Mpal",
            "Rencontres d'evaluation des campagnes semestrielles de depistage "
            "de la malnutrition aigue chez les enfants 6-59 mois",
            "Prise en charge des enfants depistes malnutris lors des campagnes "
            "semestrielles",
        ],
    ),
]


class Command(BaseCommand):
    help = "Importe les activites du cadre logique du projet Saint-Louis (NOUSCIMS-SL-2026)."

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            project = Project.objects.get(
                code=PROJECT_CODE, is_active=True, deleted_at__isnull=True
            )
        except Project.DoesNotExist:
            raise CommandError(
                f"Projet {PROJECT_CODE} introuvable. Importer d'abord le portefeuille projets."
            )

        created = 0
        updated = 0
        for result_code, os_num, os_label, result_label, activities in LOGFRAME:
            for idx, title in enumerate(activities, start=1):
                code = f"SL-{result_code}-A{idx}"
                if len(title) > 200:
                    raise CommandError(
                        f"Titre trop long ({len(title)} > 200) pour {code} : {title}"
                    )
                description = (
                    f"Objectif specifique {os_num} : {os_label}\n"
                    f"Resultat attendu {result_code} : {result_label}"
                )
                obj, was_created = Activity.objects.update_or_create(
                    project=project,
                    code=code,
                    defaults={
                        "title": title,
                        "description": description,
                        "status": Activity.Status.PLANNED,
                        "completion_rate": 0,
                        "is_active": True,
                        "deleted_at": None,
                    },
                )
                if was_created:
                    created += 1
                    self.stdout.write(f"  + {code} : {title[:70]}")
                else:
                    updated += 1
                    self.stdout.write(f"  ~ {code} : {title[:70]}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Cadre logique Saint-Louis importe : {created} creees, "
                f"{updated} mises a jour ({created + updated} activites au total)."
            )
        )
