# -*- coding: utf-8 -*-
"""
Relie les BudgetLine du projet Saint-Louis (NOUSCIMS-SL-2026) aux Activity
issues du cadre logique.

Le rattachement BudgetLine -> Activity est nominal pour les lignes qui
correspondent a une activite identifiable du cadre logique ; les lignes
transverses (personnel projet, suivi/evaluation, frais administratifs,
equipement, couts indirects) restent volontairement NON liees (activity = NULL).

Le mapping est defini par prefixe de code BudgetLine -> code Activity
(cf. apps.finance.management.commands.seed_budget_lines_saint_louis_2026 pour
la nomenclature, et apps.activities.management.commands.import_activities_saint_louis
pour les codes d'activite).

Idempotente.
"""

from collections import defaultdict
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.activities.models import Activity
from apps.finance.models import BudgetLine
from apps.projects.models import Project

PROJECT_CODE = "NOUSCIMS-SL-2026"

# Prefixe code BudgetLine -> code Activity (cadre logique).
# Les prefixes incluent le tiret final pour eviter les collisions ambigues
# (ex: "SL-A115-1-" ne matche pas "SL-A115-11-2026").
PREFIX_TO_ACTIVITY = [
    # A.1.1 Formations : 5 themes
    ("SL-A111-T1-", "SL-R1-A2"),  # Orientation et formation des elus
    ("SL-A111-T2-", "SL-R1-A3"),  # Renforcement capacites acteurs contributifs
    ("SL-A111-T3-", "SL-R2-A1"),  # Planification et suivi (elus, CT, secteurs cles)
    ("SL-A111-T4-", "SL-R3-A2"),  # Formation prestataires PECMAS
    ("SL-A111-T5-", "SL-R3-A4"),  # Formation acteurs communautaires PECMAM
    # A.1.4 Prestations professionnelles
    ("SL-A114-01-", "SL-R3-A1"),  # Conventions tripartites
    ("SL-A114-02-", "SL-R3-A8"),  # Prise en charge MAM
    ("SL-A114-03-", "SL-R3-A8"),  # Prise en charge MAS
    # A.1.5 AUTRES
    ("SL-A115-1-", "SL-R1-A1"),   # Ceremonie de lancement
    ("SL-A115-2-", "SL-R1-A4"),   # CDDN (cf. xls row 59 "2-")
    ("SL-A115-3-", "SL-R1-A5"),   # 5 cadres communaux (cf. xls row 64 "3-")
    ("SL-A115-4-", "SL-R1-A6"),   # Atelier feuilles de route CDDN/CLDN
    ("SL-A115-5-", "SL-R1-A6"),   # Rencontres annuelle de suivi CDDN/CLDN
    ("SL-A115-6-", "SL-R2-A2"),   # Plans d'action communaux
    ("SL-A115-7-", "SL-R2-A3"),   # Plaidoyer / Fora communautaires
    ("SL-A115-8-", "SL-R3-A5"),   # Planification campagnes depistage
    ("SL-A115-9-", "SL-R3-A6"),   # Organisation campagnes depistage
    ("SL-A115-10-", "SL-R3-A7"),  # Evaluation campagnes depistage
    # NON LIE volontairement :
    #  - SL-A112-*         constructions (vide dans le xls)
    #  - SL-A113-*         equipement (transverse)
    #  - SL-A115-11-       rehabilitation locaux (infrastructure transverse)
    #  - SL-A2-*           personnel projet (transverse)
    #  - SL-A3-*           missions de suivi (transverse)
    #  - SL-A4-*           depenses administratives (transverse)
    #  - SL-A5-*           divers (transverse)
    #  - SL-B-INDIRECT-*   couts indirects (transverse)
]


class Command(BaseCommand):
    help = (
        "Relie les BudgetLine du projet Saint-Louis aux Activity du cadre "
        "logique. Idempotente."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            project = Project.objects.get(
                code=PROJECT_CODE, is_active=True, deleted_at__isnull=True
            )
        except Project.DoesNotExist:
            raise CommandError(f"Projet {PROJECT_CODE} introuvable.")

        # Charge les activites du projet dans un dict {code: Activity}.
        activities = {
            a.code: a
            for a in Activity.objects.filter(
                project=project, is_active=True, deleted_at__isnull=True
            )
        }
        if not activities:
            raise CommandError(
                "Aucune activite trouvee pour ce projet. Importer d'abord le "
                "cadre logique (import_activities_saint_louis)."
            )

        lines = BudgetLine.objects.filter(
            project=project, is_active=True, deleted_at__isnull=True
        ).order_by("code")

        linked = 0
        already = 0
        unlinked = 0
        per_activity = defaultdict(lambda: {"count": 0, "amount": Decimal("0")})

        for line in lines:
            target_code = None
            for prefix, act_code in PREFIX_TO_ACTIVITY:
                if line.code.startswith(prefix):
                    target_code = act_code
                    break

            if target_code is None:
                unlinked += 1
                continue

            activity = activities.get(target_code)
            if activity is None:
                self.stderr.write(
                    f"  /!\\ Activite {target_code} introuvable pour {line.code}"
                )
                continue

            per_activity[target_code]["count"] += 1
            per_activity[target_code]["amount"] += line.planned_amount

            if line.activity_id == activity.id:
                already += 1
                continue

            line.activity = activity
            line.save(update_fields=["activity", "updated_at"])
            linked += 1

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Rattachement BudgetLine -> Activity :"))
        self.stdout.write(f"  Nouvelles liaisons : {linked}")
        self.stdout.write(f"  Deja liees         : {already}")
        self.stdout.write(f"  Non liees (transverse) : {unlinked}")
        self.stdout.write("")
        self.stdout.write("Synthese par activite :")
        for code in sorted(per_activity.keys()):
            stats = per_activity[code]
            title = activities[code].title[:55]
            self.stdout.write(
                f"  {code} ({title}) : {stats['count']} lignes, "
                f"{stats['amount']:,.0f} XOF"
            )
