"""Importe le personnel EVE (liste de fevrier 2026) depuis le JSON genere.

Idempotent : les employes sont identifies par leur matricule. Le type de
contrat (CDD/CP) figure dans assignment_label faute de champ dedie sur Employee
(le detail des contrats se gere via le modele Contract / la fiche employe).
"""

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.hr.models import Employee
from apps.hr.reference_data import RH_REFERENCE_SOURCE

DATA_FILE = Path(settings.BASE_DIR) / "apps" / "hr" / "data" / "personnel_2026.json"

# CDD = salarie/contractuel EVE ; CP = contrat de prestation -> prestataire terrain.
CATEGORY_BY_CONTRACT = {
    "CDD": Employee.WorkforceCategory.SALARIED,
    "CP": Employee.WorkforceCategory.SERVICE_PROVIDER,
}


class Command(BaseCommand):
    help = "Importe le personnel EVE (fevrier 2026)."

    @transaction.atomic
    def handle(self, *args, **opts):
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        n = new = updated = 0
        for e in data["employees"]:
            assignment = (e.get("assignment_label") or "").strip()
            ctype = (e.get("contract_type") or "").strip()
            if ctype:
                assignment = (f"[{ctype}] " + assignment).strip()
            category = CATEGORY_BY_CONTRACT.get(ctype, Employee.WorkforceCategory.SALARIED)
            fields = {
                "first_name": (e.get("first_name") or "").strip()[:80],
                "last_name": (e.get("last_name") or "").strip()[:80],
                "position": ((e.get("position") or "").strip() or "Non précisé")[:120],
                "hire_date": e.get("hire_date") or "2026-01-01",
                "birth_date": e.get("birth_date") or None,
                "email_professional": (e.get("email_professional") or "").strip()[:120],
                "phone_primary": (e.get("phone_primary") or "").strip()[:20],
                "assignment_label": assignment[:150],
                "workforce_category": category,
                "reference_source": RH_REFERENCE_SOURCE,
            }
            obj, created = Employee.objects.get_or_create(
                matricule=e["matricule"], defaults=fields
            )
            n += 1
            if created:
                new += 1
            else:
                # Reconcilie les fiches existantes (marqueur referentiel + categorie
                # notamment, qui pouvaient manquer sur d'anciens imports).
                changed = False
                for attr, value in fields.items():
                    if getattr(obj, attr) != value:
                        setattr(obj, attr, value)
                        changed = True
                if changed:
                    obj.save()
                    updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"Personnel importe : {n} employes traites ({new} crees, {updated} mis a jour)."
        ))
        self.stdout.write(
            "Completer si besoin chaque fiche (n° IPRES/CSS, banque, contrat) "
            "via la creation/edition manuelle dans l'espace RH."
        )
