"""Importe le plan de suivi 2026 (fichier JSON genere depuis l'Excel EVE).

Cree les projets listes dans le plan et leurs activites planifiees. Idempotent :
- les projets sont identifies par leur code ;
- les activites par (projet, titre).
Les dates de projet sont des valeurs par defaut (annee 2026) a ajuster ensuite
dans la fiche projet ; le responsable/echeance/commentaire de chaque action
sont consignes dans les notes de l'activite (les responsables sont des
fonctions, pas encore des fiches Employe).
"""

import json
from datetime import date
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.activities.models import Activity
from apps.projects.models import Project

DATA_FILE = Path(settings.BASE_DIR) / "apps" / "activities" / "data" / "plan_suivi_2026.json"
DEFAULT_START = date(2026, 1, 1)
DEFAULT_END = date(2026, 12, 31)


class Command(BaseCommand):
    help = "Importe le plan de suivi 2026 : projets + activites planifiees."

    @transaction.atomic
    def handle(self, *args, **opts):
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        n_proj = n_proj_new = n_act = n_act_new = 0

        for pj in data["projects"]:
            project, created = Project.objects.get_or_create(
                code=pj["code"],
                defaults={
                    "title": pj["title"][:200],
                    "start_date": DEFAULT_START,
                    "end_date": DEFAULT_END,
                },
            )
            n_proj += 1
            n_proj_new += 1 if created else 0

            for act in pj.get("activities", []):
                title = (act.get("title") or "").strip()[:200]
                if not title:
                    continue
                bits = []
                if act.get("responsable"):
                    bits.append(f"Responsable : {act['responsable']}")
                if act.get("echeance"):
                    bits.append(f"Échéance : {act['echeance']}")
                if act.get("commentaire"):
                    bits.append(f"Commentaire : {act['commentaire']}")
                notes = " | ".join(bits)

                obj, acreated = Activity.objects.get_or_create(
                    project=project,
                    title=title,
                    defaults={"planned_start_date": DEFAULT_START, "notes": notes},
                )
                n_act += 1
                if acreated:
                    n_act_new += 1
                elif obj.notes != notes:
                    obj.notes = notes
                    obj.save(update_fields=["notes"])

        self.stdout.write(self.style.SUCCESS(
            f"Plan de suivi importe : {n_proj} projets ({n_proj_new} crees), "
            f"{n_act} activites ({n_act_new} creees)."
        ))
        self.stdout.write(
            "Pensez a completer chaque fiche projet (dates reelles, bailleur, "
            "responsable) via la creation/edition manuelle."
        )
