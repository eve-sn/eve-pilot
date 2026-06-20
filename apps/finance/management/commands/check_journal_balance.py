"""
Controle d'integrite comptable : detecte les ecritures (JournalEntry) dont
la somme des debits n'egale pas la somme des credits.

Une telle ecriture viole l'invariant de la partie double et fausse la balance
generale, le compte de resultat et le bilan. Le posting (apps.finance.posting)
empeche desormais d'en creer, mais des ecritures anterieures au correctif
peuvent subsister : cette commande les revele.

Lecture seule : ne modifie rien. Code de sortie 1 si au moins une ecriture est
desequilibree (exploitable en CI / cron de surveillance), 0 sinon.

Usage :
  python manage.py check_journal_balance
  python manage.py check_journal_balance --posted-only
  python manage.py check_journal_balance --include-deleted
"""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db.models import Q, Sum

from apps.finance.models import JournalEntry


class Command(BaseCommand):
    help = "Detecte les ecritures comptables desequilibrees (debit != credit)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--posted-only",
            action="store_true",
            help="Ne controle que les ecritures postees (posted=True).",
        )
        parser.add_argument(
            "--include-deleted",
            action="store_true",
            help="Inclut aussi les ecritures soft-deleted / inactives.",
        )

    def handle(self, *args, posted_only=False, include_deleted=False, **options):
        qs = JournalEntry.objects.all()
        if not include_deleted:
            qs = qs.filter(is_active=True, deleted_at__isnull=True)
        if posted_only:
            qs = qs.filter(posted=True)

        # Agregation en base : une seule requete, pas de N+1.
        # On ne somme QUE les lignes actives (memes que account_balances() des
        # etats financiers) : une JournalLine soft-deleted ne compte plus dans la
        # balance generale, donc une ecriture dont une ligne a ete soft-deleted
        # doit apparaitre desequilibree ici aussi. Sans ce filtre, l'outil de
        # controle raterait precisement ce type de corruption.
        active_lines = Q(lines__is_active=True, lines__deleted_at__isnull=True)
        qs = qs.annotate(
            sum_debit=Sum("lines__debit", filter=active_lines),
            sum_credit=Sum("lines__credit", filter=active_lines),
        ).order_by("entry_date", "id")

        total = qs.count()
        unbalanced = []
        empty = []
        for entry in qs:
            d = entry.sum_debit or Decimal("0")
            c = entry.sum_credit or Decimal("0")
            if entry.sum_debit is None and entry.sum_credit is None:
                # Ecriture sans aucune ligne : anomalie distincte (en-tete orphelin).
                empty.append(entry)
            elif d != c:
                unbalanced.append((entry, d, c))

        self.stdout.write(f"Ecritures controlees : {total}.")

        if empty:
            self.stdout.write(
                self.style.WARNING(f"\nEcritures SANS LIGNE (en-tetes orphelins) : {len(empty)}")
            )
            for entry in empty:
                self._write_source(entry)

        if unbalanced:
            self.stdout.write(
                self.style.ERROR(f"\nEcritures DESEQUILIBREES : {len(unbalanced)}")
            )
            for entry, d, c in unbalanced:
                self.stderr.write(
                    f"  /!\\ ecriture #{entry.id} ({entry.entry_date}) "
                    f"debit={d} != credit={c} (ecart={d - c}) | {entry.label}"
                )
                self._write_source(entry)

        if unbalanced or empty:
            self.stdout.write(
                "\nRegeneration possible des ecritures issues d'un mouvement : "
                "python manage.py generate_journal_entries --regenerate"
            )
            # Code de sortie non nul -> exploitable en surveillance automatisee.
            raise SystemExit(1)

        self.stdout.write(self.style.SUCCESS("\nToutes les ecritures sont equilibrees."))

    def _write_source(self, entry):
        """Indique l'origine de l'ecriture pour faciliter la correction."""
        if entry.source_bank_movement_id:
            self.stdout.write(f"        source : BankMovement BM-{entry.source_bank_movement_id}")
        elif entry.source_cash_movement_id:
            self.stdout.write(f"        source : CashMovement CM-{entry.source_cash_movement_id}")
        else:
            self.stdout.write("        source : saisie manuelle (a corriger a la main)")
