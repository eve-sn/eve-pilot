"""
Importe un releve bancaire SUNU Bank au format xls (export ancien Excel)
en mouvements BankMovement.

Usage :
  python manage.py import_bank_statement_xls <chemin_xls>
  python manage.py import_bank_statement_xls <chemin_xls> --account="Budget General"

Si --account n'est pas fourni, la commande tente d'identifier le compte cible
en extrayant le numero de compte du header du xls (ligne 'Compte N° : XXXXX')
et en cherchant un BankAccount avec ce account_reference.

Format attendu (export SUNU 'Account Activity') :
  R1   : entete banque
  R2   : Client
  R3   : Compte N° : XXXXX - XOF
  R4   : Periode
  R5   : Ordre
  R8   : entete colonnes (Date Operation, Date Valeur, Reference, Montant,
         Libelle, Solde, Devise)
  R9   : Solde de depart
  R10+ : mouvements (montant signe : negatif = debit, positif = credit)

Idempotence : update_or_create sur (account, date_operation, reference,
debit, credit) - cf. contrainte uq_bank_movement_idempotent_key.
"""

import re
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.finance.models import BankAccount, BankMovement


HEADER_ROW = 8  # 1-based : ligne des entetes "Date Operation | ..."
DATA_START_ROW = 10  # 1-based : premiere ligne de mouvement


class Command(BaseCommand):
    help = "Importe un releve SUNU Bank xls en BankMovement."

    def add_arguments(self, parser):
        parser.add_argument("xls_path", help="Chemin du fichier .xls a importer.")
        parser.add_argument(
            "--account",
            help="Nom du BankAccount cible (sinon detecte via le numero de compte du header).",
        )
        parser.add_argument(
            "--source-document",
            default="",
            help="Etiquette source_document a stocker sur chaque mouvement.",
        )

    @transaction.atomic
    def handle(self, *args, xls_path, account=None, source_document="", **options):
        try:
            import xlrd
        except ImportError:
            raise CommandError(
                "xlrd manquant. Installer avec : pip install 'xlrd<2.0'"
            )

        path = Path(xls_path)
        if not path.exists():
            raise CommandError(f"Fichier introuvable : {path}")

        wb = xlrd.open_workbook(str(path))
        sheet = wb.sheets()[0]

        # Detection du compte cible
        target_account = self._resolve_account(sheet, account)
        self.stdout.write(f"Compte cible : {target_account.name} ({target_account.account_reference})")

        # Header colonnes ligne 8 (index 7), donnees a partir de la ligne 10 (index 9)
        # Mais on parcourt tout a partir de la ligne 9 (index 8) qui est 'Solde de depart'
        created = 0
        updated = 0
        skipped = 0
        for r in range(DATA_START_ROW - 1, sheet.nrows):
            row = [sheet.cell_value(r, c) for c in range(sheet.ncols)]
            date_op = self._parse_xldate(row[0], wb)
            if date_op is None:
                skipped += 1
                continue

            date_value = self._parse_xldate(row[1], wb) if len(row) > 1 else None
            reference = str(row[2]).strip() if len(row) > 2 and row[2] else ""
            try:
                signed = Decimal(str(row[3])) if row[3] not in (None, "") else None
            except Exception:
                signed = None
            if signed is None:
                skipped += 1
                continue

            label = str(row[4]).strip() if len(row) > 4 and row[4] else ""
            try:
                balance_after = Decimal(str(row[5])) if len(row) > 5 and row[5] not in (None, "") else None
            except Exception:
                balance_after = None

            debit = -signed if signed < 0 else Decimal("0")
            credit = signed if signed > 0 else Decimal("0")

            movement, was_created = BankMovement.objects.update_or_create(
                account=target_account,
                date_operation=date_op,
                reference=reference,
                debit=debit,
                credit=credit,
                defaults={
                    "date_value": date_value,
                    "label": label[:300],
                    "balance_after": balance_after,
                    "source_document": source_document or path.name,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Import termine : {created} mouvements crees, "
                f"{updated} mis a jour, {skipped} lignes ignorees."
            )
        )

    def _resolve_account(self, sheet, name_arg):
        if name_arg:
            try:
                return BankAccount.objects.get(
                    name=name_arg, is_active=True, deleted_at__isnull=True
                )
            except BankAccount.DoesNotExist:
                raise CommandError(f"BankAccount '{name_arg}' introuvable.")

        # Tenter d'extraire le numero de compte du header
        for r in range(min(sheet.nrows, 6)):
            text = str(sheet.cell_value(r, 0))
            match = re.search(r"Compte\s*N[°O]\s*:\s*(\d+)", text)
            if match:
                ref = match.group(1)
                try:
                    return BankAccount.objects.get(
                        account_reference=ref,
                        is_active=True,
                        deleted_at__isnull=True,
                    )
                except BankAccount.DoesNotExist:
                    raise CommandError(
                        f"Aucun BankAccount trouve avec account_reference={ref}. "
                        "Lancer seed_bank_accounts_2026 d'abord ou passer --account=NOM."
                    )
        raise CommandError(
            "Impossible de detecter le numero de compte dans les premieres lignes du xls. "
            "Utiliser --account=NOM."
        )

    @staticmethod
    def _parse_xldate(value, workbook):
        if value in (None, ""):
            return None
        # Si c'est une chaine de date dd/mm/yyyy
        if isinstance(value, str):
            value = value.strip()
            if not value or value.lower().startswith("solde") or value.lower().startswith("date"):
                return None
            for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
                try:
                    from datetime import datetime
                    return datetime.strptime(value, fmt).date()
                except ValueError:
                    continue
            return None
        # Si c'est un float (date serielle Excel)
        try:
            import xlrd
            tup = xlrd.xldate_as_tuple(float(value), workbook.datemode)
            from datetime import date as _date
            return _date(tup[0], tup[1], tup[2])
        except Exception:
            return None
