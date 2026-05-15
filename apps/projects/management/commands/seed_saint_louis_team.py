# -*- coding: utf-8 -*-
"""
Cale l'equipe technique du bureau local de Saint-Louis.

Source : "Liste_personnel technique.xlsx" (feuille "Liste personnel technique
de Saint Louis").

Les 7 personnes existent deja dans Employee (importes par seed RH plus tot),
mais sous des positions generiques ("Agent terrain", "Collaborateur siege").
Cette commande :
  - met a jour position, assignment_label, phone_primary pour les aligner sur
    le poste reel du bureau local.
  - cree les entrees ProjectTeam pour le projet NOUSCIMS-SL-2026 (avec le
    role correspondant), idempotent par (project, employee).

Idempotente.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.hr.models import Employee
from apps.projects.models import Project, ProjectTeam

PROJECT_CODE = "NOUSCIMS-SL-2026"
ASSIGNMENT_LABEL = "Nous-Cims Saint-Louis"

# (matricule, position, phone, role pour ProjectTeam)
TEAM = [
    (
        "REF-2026-005",
        "Cheikh Pathe FALL",
        "Point focal nutrition et securite alimentaire",
        "76 720 30 35",
        "Point focal nutrition et securite alimentaire",
    ),
    (
        "REF-2026-011",
        "Moustapha FALL",
        "Chef de projet charge du suivi-evaluation",
        "77 239 80 60",
        "Chef de projet S&E",
    ),
    (
        "REF-2026-015",
        "Papa Iba Mar FALL",
        "Animateur charge des concertations",
        "77 643 95 87",
        "Animateur concertations",
    ),
    (
        "REF-2026-016",
        "Farma DIEYE",
        "Animateur charge des concertations",
        "77 460 40 65",
        "Animateur concertations",
    ),
    (
        "REF-2026-022",
        "Rokhaya BA",
        "Secretaire comptable",
        "77 117 84 85",
        "Secretaire comptable",
    ),
    (
        "REF-2026-020",
        "Alassane BA",
        "Superviseur technique",
        "77 342 11 62",
        "Superviseur technique",
    ),
    (
        "REF-2026-021",
        "Youssoupha SY",
        "Superviseur technique",
        "77 206 01 11",
        "Superviseur technique",
    ),
]


class Command(BaseCommand):
    help = (
        "Met a jour postes / affectations des 7 personnes du bureau local "
        "Saint-Louis et les rattache au ProjectTeam NOUSCIMS-SL-2026."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            project = Project.objects.get(
                code=PROJECT_CODE, is_active=True, deleted_at__isnull=True
            )
        except Project.DoesNotExist:
            raise CommandError(f"Projet {PROJECT_CODE} introuvable.")

        emp_updated = 0
        team_created = 0
        team_already = 0
        missing = []

        for matricule, full_name, position, phone, role in TEAM:
            try:
                emp = Employee.objects.get(
                    matricule=matricule, is_active=True, deleted_at__isnull=True
                )
            except Employee.DoesNotExist:
                missing.append(matricule)
                continue

            updates = []
            if emp.position != position:
                emp.position = position
                updates.append("position")
            if emp.assignment_label != ASSIGNMENT_LABEL:
                emp.assignment_label = ASSIGNMENT_LABEL
                updates.append("assignment_label")
            if phone and emp.phone_primary != phone:
                emp.phone_primary = phone
                updates.append("phone_primary")
            if updates:
                emp.save(update_fields=[*updates, "updated_at"])
                emp_updated += 1
                self.stdout.write(f"  ~ {matricule} ({full_name}) : maj {updates}")

            pt, was_created = ProjectTeam.objects.get_or_create(
                project=project,
                employee=emp,
                defaults={
                    "role": role,
                    "is_active": True,
                },
            )
            if was_created:
                team_created += 1
            else:
                team_already += 1
                # Met a jour le role si il a change.
                if pt.role != role:
                    pt.role = role
                    pt.save(update_fields=["role", "updated_at"])

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Equipe Saint-Louis : {emp_updated} fiches Employee mises a jour, "
            f"{team_created} nouvelles entrees ProjectTeam, "
            f"{team_already} deja presentes."
        ))
        if missing:
            self.stdout.write(self.style.WARNING(
                f"Matricules introuvables : {missing}"
            ))
