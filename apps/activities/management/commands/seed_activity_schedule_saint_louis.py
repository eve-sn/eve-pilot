# -*- coding: utf-8 -*-
"""
Cale les dates et le responsable des 17 activites du projet Saint-Louis.

Sources :
  - Chronogramme : "Chronogramme projet Saint Louis_EVE_VF.pdf"
    (visuel : grille An1 par mois 1-12, An2 et An3 par trimestre)
  - Organigramme : "Annexe 3_Organigramme du projet de Saint-Louis.docx"
    (positions : Coordonnateur Politique, Referent technique, Charge de la
     gouvernance, Chef de projet S&E, Animateurs concertations, Assistant AF,
     Secretaire comptable, Superviseurs)

Hypotheses :
  - Projet demarre le 01/08/2025, donc An1 M1 = aout 2025.
  - Le chronogramme etant un visuel, l'interpretation des cellules orange est
    approximative ; les dates sont a affiner via l'UI d'edition.
  - Le seul employe affecte au bureau local de Saint-Louis aujourd'hui dans
    la base est Moustapha FALL (Chef de projet S&E). Il porte la
    responsabilite operationnelle des 17 activites tant que le reste de
    l'equipe (animateurs, superviseurs, charge gouvernance, etc.) n'est pas
    enregistre.

Idempotente : ecrase planned_start_date, planned_end_date et responsible
sur les 17 activites.
"""

from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.activities.models import Activity
from apps.hr.models import Employee
from apps.projects.models import Project

PROJECT_CODE = "NOUSCIMS-SL-2026"

# Bureau local Saint-Louis - matricules par poste fonctionnel.
CHEF_PROJET = "REF-2026-011"        # Moustapha FALL
POINT_FOCAL = "REF-2026-005"        # Cheikh Pathe FALL
ANIMATEUR_1 = "REF-2026-015"        # Papa Iba Mar FALL
ANIMATEUR_2 = "REF-2026-016"        # Farma DIEYE
SUPERVISEUR_1 = "REF-2026-020"      # Alassane BA
SUPERVISEUR_2 = "REF-2026-021"      # Youssoupha SY
# Rokhaya BA (secretaire comptable) ne pilote pas d'activite terrain.

# Repartition par activite, etablie a partir de la nature du travail :
#   - cadres institutionnels / signature / suivi-eval -> Chef de projet
#   - concertation communale / formations elus / plaidoyer -> Animateurs
#   - formations terrain PECMA(S|M) / campagnes / PEC -> Superviseurs
#   - formation CIP / supervision nutrition -> Point focal nutrition
RESPONSIBLE_BY_ACTIVITY = {
    "SL-R1-A1": CHEF_PROJET,     # Ceremonie de lancement
    "SL-R1-A2": ANIMATEUR_1,     # Orientation des elus
    "SL-R1-A3": ANIMATEUR_2,     # Renforcement acteurs contributifs
    "SL-R1-A4": CHEF_PROJET,     # CDDN (departemental)
    "SL-R1-A5": ANIMATEUR_1,     # 5 cadres communaux
    "SL-R1-A6": ANIMATEUR_1,     # Animation CDDN + CLDN
    "SL-R2-A1": ANIMATEUR_2,     # Capacites de planification
    "SL-R2-A2": ANIMATEUR_1,     # PAN communaux
    "SL-R2-A3": CHEF_PROJET,     # Plaidoyer DOB
    "SL-R3-A1": CHEF_PROJET,     # Conventions tripartites (signature)
    "SL-R3-A2": SUPERVISEUR_1,   # Formation prestataires PECMAS
    "SL-R3-A3": POINT_FOCAL,     # Formation acteurs communautaires CIP
    "SL-R3-A4": SUPERVISEUR_2,   # Formation acteurs communautaires PECMAM
    "SL-R3-A5": CHEF_PROJET,     # Planification campagnes (coordination)
    "SL-R3-A6": SUPERVISEUR_1,   # Organisation campagnes depistage
    "SL-R3-A7": CHEF_PROJET,     # Evaluation campagnes (S&E)
    "SL-R3-A8": SUPERVISEUR_2,   # Prise en charge enfants malnutris
}

# Calendrier des activites issu du chronogramme.
# Format : code -> (start_date, end_date or None)
# None pour end_date = activite recurrente / continue jusqu'a la fin du projet.
SCHEDULE = {
    # R1 - cadres de gouvernance territoriale
    "SL-R1-A1": (date(2025, 12, 1), date(2025, 12, 31)),   # Ceremonie lancement (M5)
    "SL-R1-A2": (date(2026, 1, 1),  date(2026, 1, 31)),    # Orientation elus (M6)
    "SL-R1-A3": (date(2026, 2, 1),  date(2026, 2, 28)),    # Renforcement acteurs (M7)
    "SL-R1-A4": (date(2026, 3, 1),  date(2026, 4, 30)),    # CDDN (M8-M9)
    "SL-R1-A5": (date(2026, 3, 1),  date(2026, 4, 30)),    # 5 cadres communaux (M8-M9)
    "SL-R1-A6": (date(2026, 5, 1),  None),                 # Animation CDDN+CLDN (continu)
    # R2 - nutrition priorite des CT
    "SL-R2-A1": (date(2026, 3, 1),  date(2026, 4, 30)),    # Capacites planification
    "SL-R2-A2": (date(2026, 4, 1),  date(2026, 6, 30)),    # PAN communaux
    "SL-R2-A3": (date(2026, 5, 1),  date(2027, 1, 31)),    # Plaidoyer DOB (M10 + An2 T2)
    # R3 - prevention et prise en charge (Fass Ngom, Mpal)
    "SL-R3-A1": (date(2025, 12, 1), date(2025, 12, 31)),   # Conventions tripartites (M5)
    "SL-R3-A2": (date(2026, 1, 1),  date(2026, 1, 31)),    # Formation PECMAS (M6)
    "SL-R3-A3": (date(2026, 2, 1),  date(2026, 2, 28)),    # Formation CIP (M7)
    "SL-R3-A4": (date(2026, 2, 1),  date(2026, 2, 28)),    # Formation PECMAM (M7)
    "SL-R3-A5": (date(2026, 3, 1),  None),                 # Planif campagnes (semestriel)
    "SL-R3-A6": (date(2026, 4, 1),  None),                 # Campagnes depistage (recurrent)
    "SL-R3-A7": (date(2026, 6, 1),  None),                 # Evaluation campagnes (recurrent)
    "SL-R3-A8": (date(2026, 5, 1),  None),                 # PEC malnutris (continu)
}


class Command(BaseCommand):
    help = (
        "Cale les dates (chronogramme) et le responsable (organigramme) des "
        "17 activites du projet Saint-Louis."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            project = Project.objects.get(
                code=PROJECT_CODE, is_active=True, deleted_at__isnull=True
            )
        except Project.DoesNotExist:
            raise CommandError(f"Projet {PROJECT_CODE} introuvable.")

        # Charge en un coup les 6 employes pilotes.
        matricules = set(RESPONSIBLE_BY_ACTIVITY.values())
        employees = {
            e.matricule: e
            for e in Employee.objects.filter(
                matricule__in=matricules, is_active=True, deleted_at__isnull=True
            )
        }
        missing_employees = matricules - set(employees.keys())
        if missing_employees:
            raise CommandError(
                f"Employes introuvables : {sorted(missing_employees)}. "
                "Lancer d'abord seed_saint_louis_team."
            )

        activities = {
            a.code: a
            for a in Activity.objects.filter(
                project=project, is_active=True, deleted_at__isnull=True
            )
        }

        updated = 0
        missing = []
        for code, (start, end) in SCHEDULE.items():
            activity = activities.get(code)
            if activity is None:
                missing.append(code)
                continue
            matricule = RESPONSIBLE_BY_ACTIVITY.get(code)
            owner = employees[matricule] if matricule else None

            activity.planned_start_date = start
            activity.planned_end_date = end
            activity.responsible = owner
            activity.save(
                update_fields=[
                    "planned_start_date",
                    "planned_end_date",
                    "responsible",
                    "updated_at",
                ]
            )
            updated += 1
            end_str = end.isoformat() if end else "ongoing"
            owner_str = f"{owner.first_name} {owner.last_name}" if owner else "-"
            self.stdout.write(
                f"  ~ {code} : {start.isoformat()} -> {end_str}  [{owner_str}]"
            )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Calendrier Saint-Louis : {updated} activites calees avec "
                f"dates et responsable nominal par poste."
            )
        )
        if missing:
            self.stdout.write(self.style.WARNING(
                f"Activites introuvables (lancer import_activities_saint_louis) : {missing}"
            ))
