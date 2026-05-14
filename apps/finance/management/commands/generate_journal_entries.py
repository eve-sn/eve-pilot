"""
Genere (ou regenere) en lot les ecritures comptables des mouvements de
tresorerie deja imputes (contra_account renseigne).

Utile apres une imputation en masse via /admin/, ou pour rattraper des
mouvements importes avant la mise en place du module comptable.

Usage :
  python manage.py generate_journal_entries
  python manage.py generate_journal_entries --regenerate   (force la regeneration)
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.finance.models import BankMovement, CashMovement
from apps.finance.posting import PostingError, post_bank_movement, post_cash_movement


class Command(BaseCommand):
    help = "Genere les ecritures comptables des mouvements de tresorerie imputes."

    def add_arguments(self, parser):
        parser.add_argument(
            "--regenerate",
            action="store_true",
            help="Regenere les ecritures meme si elles existent deja.",
        )

    @transaction.atomic
    def handle(self, *args, regenerate=False, **options):
        bank_qs = BankMovement.objects.filter(
            is_active=True, deleted_at__isnull=True, contra_account__isnull=False
        )
        cash_qs = CashMovement.objects.filter(
            is_active=True, deleted_at__isnull=True, contra_account__isnull=False
        )

        self.stdout.write(
            f"Mouvements imputes a traiter : {bank_qs.count()} bancaires, {cash_qs.count()} caisse."
        )

        bank_created = 0
        bank_errors = 0
        for movement in bank_qs:
            try:
                entry = post_bank_movement(movement, regenerate=regenerate)
                if entry is not None:
                    bank_created += 1
            except PostingError as exc:
                bank_errors += 1
                self.stderr.write(f"  /!\\ BM-{movement.id} : {exc}")

        cash_created = 0
        cash_errors = 0
        for movement in cash_qs:
            try:
                entry = post_cash_movement(movement, regenerate=regenerate)
                if entry is not None:
                    cash_created += 1
            except PostingError as exc:
                cash_errors += 1
                self.stderr.write(f"  /!\\ CM-{movement.id} : {exc}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Ecritures generees : {bank_created} (bancaires), {cash_created} (caisse). "
                f"Erreurs : {bank_errors + cash_errors}."
            )
        )
