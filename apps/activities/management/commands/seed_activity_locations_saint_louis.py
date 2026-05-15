# -*- coding: utf-8 -*-
"""
Cree les ActivityLocation des activites du projet Saint-Louis.

Ciblage geographique (cadre logique) :
  - A1.1 (Ceremonie de lancement) et A1.4 (CDDN) sont departementales :
    Saint-Louis (chef-lieu).
  - A1.2, A1.3, A1.5, A1.6, A2.1, A2.2, A2.3 ciblent les 5 communes du
    departement (Saint-Louis, Mpal, Fass Ngom, Gandon, Ndiebene Gandiol).
  - A3.1 a A3.8 ciblent uniquement les 2 communes de Fass Ngom et Mpal.

Prerequis : seed_communes_saint_louis et import_activities_saint_louis.

Idempotente (get_or_create par (activity, commune)).
"""

from django.core.management.base import BaseCommand, CommandError

from apps.activities.models import Activity, ActivityLocation
from apps.projects.models import Project
from apps.references.models import Commune

PROJECT_CODE = "NOUSCIMS-SL-2026"

# Listes de noms de communes (matchent Commune.name).
DEPARTEMENT = ["Saint-Louis"]
FIVE_COMMUNES = ["Saint-Louis", "Mpal", "Fass Ngom", "Gandon", "Ndiebene Gandiol"]
TWO_COMMUNES = ["Fass Ngom", "Mpal"]

# Code Activity (cadre logique) -> liste de noms de Commune.
ACTIVITY_TO_COMMUNES = {
    "SL-R1-A1": DEPARTEMENT,
    "SL-R1-A2": FIVE_COMMUNES,
    "SL-R1-A3": FIVE_COMMUNES,
    "SL-R1-A4": DEPARTEMENT,
    "SL-R1-A5": FIVE_COMMUNES,
    "SL-R1-A6": FIVE_COMMUNES,
    "SL-R2-A1": FIVE_COMMUNES,
    "SL-R2-A2": FIVE_COMMUNES,
    "SL-R2-A3": FIVE_COMMUNES,
    "SL-R3-A1": TWO_COMMUNES,
    "SL-R3-A2": TWO_COMMUNES,
    "SL-R3-A3": TWO_COMMUNES,
    "SL-R3-A4": TWO_COMMUNES,
    "SL-R3-A5": TWO_COMMUNES,
    "SL-R3-A6": TWO_COMMUNES,
    "SL-R3-A7": TWO_COMMUNES,
    "SL-R3-A8": TWO_COMMUNES,
}


class Command(BaseCommand):
    help = "Cree les ActivityLocation des 17 activites du projet Saint-Louis."

    def handle(self, *args, **options):
        try:
            project = Project.objects.get(
                code=PROJECT_CODE, is_active=True, deleted_at__isnull=True
            )
        except Project.DoesNotExist:
            raise CommandError(f"Projet {PROJECT_CODE} introuvable.")

        activities = {
            a.code: a
            for a in Activity.objects.filter(
                project=project, is_active=True, deleted_at__isnull=True
            )
        }
        if not activities:
            raise CommandError(
                "Aucune activite trouvee. Lancer d'abord import_activities_saint_louis."
            )

        commune_names = set()
        for names in ACTIVITY_TO_COMMUNES.values():
            commune_names.update(names)
        communes = {
            c.name: c
            for c in Commune.objects.filter(
                name__in=commune_names, is_active=True, deleted_at__isnull=True
            )
        }
        missing = commune_names - set(communes.keys())
        if missing:
            raise CommandError(
                f"Communes manquantes au referentiel : {sorted(missing)}. "
                "Lancer d'abord seed_communes_saint_louis."
            )

        created = 0
        already = 0
        skipped = 0
        for act_code, names in ACTIVITY_TO_COMMUNES.items():
            activity = activities.get(act_code)
            if activity is None:
                self.stderr.write(f"  /!\\ Activite {act_code} introuvable, ignoree.")
                skipped += len(names)
                continue
            for name in names:
                _, was_created = ActivityLocation.objects.get_or_create(
                    activity=activity, commune=communes[name]
                )
                if was_created:
                    created += 1
                else:
                    already += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"ActivityLocation Saint-Louis : {created} creees, "
                f"{already} deja presentes, {skipped} ignorees."
            )
        )
