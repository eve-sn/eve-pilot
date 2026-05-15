# -*- coding: utf-8 -*-
"""
Cree les communes du departement de Saint-Louis qui manquent au referentiel.

Le projet NOUSCIMS-SL-2026 cible 5 communes : Saint-Louis (deja en base),
Mpal, Fass Ngom, Gandon et Ndiebene Gandiol.

Idempotente : update_or_create par name.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.references.models import Commune

COMMUNES = [
    # (code, name, department, region)
    ("MPAL", "Mpal", "Saint-Louis", "Saint-Louis"),
    ("FNG", "Fass Ngom", "Saint-Louis", "Saint-Louis"),
    ("GAN", "Gandon", "Saint-Louis", "Saint-Louis"),
    ("NDG", "Ndiebene Gandiol", "Saint-Louis", "Saint-Louis"),
]


class Command(BaseCommand):
    help = "Cree les 4 communes manquantes du departement de Saint-Louis."

    @transaction.atomic
    def handle(self, *args, **options):
        created = 0
        updated = 0
        for code, name, department, region in COMMUNES:
            obj, was_created = Commune.objects.update_or_create(
                name=name,
                defaults={
                    "code": code,
                    "department": department,
                    "region": region,
                    "is_intervention_zone": True,
                    "is_active": True,
                    "deleted_at": None,
                },
            )
            if was_created:
                created += 1
                self.stdout.write(f"  + {name}")
            else:
                updated += 1
                self.stdout.write(f"  ~ {name}")
        self.stdout.write(
            self.style.SUCCESS(
                f"Communes Saint-Louis : {created} creees, {updated} mises a jour."
            )
        )
