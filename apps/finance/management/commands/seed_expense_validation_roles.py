"""
Seed des roles de validation des demandes de depense.

Cree trois Role (apps.accounts.Role) attendus par le workflow ExpenseRequest :
  - RAF : Responsable Administratif et Financier
  - DP  : Directrice des Programmes
  - SE  : Suivi & Evaluation

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
    {"code": "SE", "name": "Suivi et Evaluation",
     "description": "Valideur S&E des demandes de depense (apps.finance.ExpenseRequest)."},
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
