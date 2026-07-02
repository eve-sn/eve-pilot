"""
Seed des roles de validation des demandes de depense.

Cree les Role (apps.accounts.Role) attendus par le workflow ExpenseRequest :
  - RAF  : Responsable Administratif et Financier (1ere signature)
  - DP   : Directrice des Programmes (2eme signature)
  - SE   : Secretaire Executif (3eme signature + valide rapports terrain)
  - ARAF : Assistante RAF (gere Budget General + petite caisse, ne valide pas)

Idempotent : update_or_create par code.
Les UserRole correspondants (attribuer un user au role) restent a faire
via /admin/accounts/userrole/.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import Role


VALIDATION_ROLES = [
    {"code": "RAF", "name": "Responsable Administratif et Financier",
     "description": "Valideur financier des demandes de depense (apps.finance.ExpenseRequest)."},
    {"code": "DP", "name": "Directrice des Programmes",
     "description": "Valideur metier des demandes de depense (apps.finance.ExpenseRequest)."},
    {"code": "SE", "name": "Secretaire Executif",
     "description": "Valideur Secretaire Executif des demandes de depense et des rapports d'activite."},
    {"code": "REFERENT_TECH", "name": "Referent technique",
     "description": "Valideur technique par projet (remplace la DP dans le trio de validation "
                    "des projets configures ; ex. Saint-Louis). Toujours porte via un UserRole "
                    "limite au projet concerne."},
    {"code": "ARAF", "name": "Assistante RAF",
     "description": "Assistante RAF - gere le Budget General et la petite caisse, ne valide pas les demandes."},
]


class Command(BaseCommand):
    help = "Cree / met a jour les 3 roles de validation des demandes de depense (RAF, DP, SE)."

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write("Seed roles de validation des demandes de depense...")
        for spec in VALIDATION_ROLES:
            role, created = Role.objects.update_or_create(
                code=spec["code"],
                defaults={"name": spec["name"], "description": spec["description"]},
            )
            self.stdout.write(f"  {role.code} ({role.name}) : {'cree' if created else 'mis a jour'}")
        self.stdout.write(self.style.SUCCESS("Done."))
