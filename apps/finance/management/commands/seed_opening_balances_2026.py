# -*- coding: utf-8 -*-
"""
Ecritures d'a-nouveau au 01/01/2026 (cloture 31/12/2025).

Pose en compte de journal les soldes d'ouverture des comptes bancaires et de
la caisse, contrepartie 1211 - Report a nouveau excedents-resultat (officiel SYCEBNL).

Format SYCEBNL d'a-nouveau :
  - Pour chaque compte bancaire avec opening_balance > 0 :
        Debit  5211.x | opening_balance
        Credit 1211   | opening_balance  (officiel SYCEBNL)
  - Pour la petite caisse (si opening_balance > 0) :
        Debit  571.00 | opening_balance
        Credit 1211   | opening_balance  (officiel SYCEBNL)

Idempotente : repere les JournalEntry existantes par reference unique
"AN-2026-<code_compte>" et les regenere si necessaire.
"""

from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from datetime import date

from apps.finance.models import (
    BankAccount, CashRegister, ChartOfAccount,
    JournalEntry, JournalLine,
)


OPENING_DATE = date(2026, 1, 1)


class Command(BaseCommand):
    help = "Genere les ecritures d'a-nouveau (soldes d'ouverture) au 01/01/2026."

    @transaction.atomic
    def handle(self, *args, **options):
        # SYCEBNL officiel : compte 1211 "Report a nouveau excedents-resultat"
        # (anciennement code EVE invente 1101, remap par migration 0016).
        try:
            report_a_nouveau = ChartOfAccount.objects.get(code="1211")
        except ChartOfAccount.DoesNotExist:
            # Fallback : si pour une raison X le seed officiel n'a pas tourne,
            # on tente l'ancien code EVE 1101 pour ne pas crasher en UAT.
            try:
                report_a_nouveau = ChartOfAccount.objects.get(code="1101")
            except ChartOfAccount.DoesNotExist:
                raise CommandError(
                    "Compte 1211 (officiel SYCEBNL) ni 1101 (legacy EVE) "
                    "introuvable. Lancer d'abord seed_chart_of_accounts_official."
                )

        created = 0
        regenerated = 0
        total_balance = Decimal("0")

        # --- Comptes bancaires ---
        for bank in BankAccount.objects.filter(
            is_active=True, deleted_at__isnull=True, opening_balance__isnull=False,
        ).order_by("name"):
            if not bank.opening_balance:
                continue

            # Trouve le ChartOfAccount 5211.x associe via linked_bank_account
            chart_acc = ChartOfAccount.objects.filter(
                linked_bank_account=bank, is_active=True, deleted_at__isnull=True,
            ).first()
            if not chart_acc:
                self.stdout.write(self.style.WARNING(
                    f"  - {bank.name}: pas de 5211.x lie -> skip"
                ))
                continue

            reference = f"AN-2026-{chart_acc.code}"
            label = f"A-nouveau {bank.name} au {OPENING_DATE.isoformat()}"

            # Supprime ancienne entry si elle existe (regeneration propre)
            existing = JournalEntry.objects.filter(reference=reference).first()
            if existing:
                existing.lines.all().delete()
                existing.delete()
                regenerated += 1

            entry = JournalEntry.objects.create(
                entry_date=OPENING_DATE,
                reference=reference,
                label=label,
                posted=True,
            )
            JournalLine.objects.create(
                entry=entry, account=chart_acc,
                debit=bank.opening_balance, credit=Decimal("0"),
                label=label,
            )
            JournalLine.objects.create(
                entry=entry, account=report_a_nouveau,
                debit=Decimal("0"), credit=bank.opening_balance,
                label=label,
            )
            created += 1
            total_balance += bank.opening_balance
            self.stdout.write(
                f"  + {chart_acc.code:8} {bank.name:35} | {bank.opening_balance:>15.0f} XOF"
            )

        # --- Petite caisse (CashRegister) ---
        for register in CashRegister.objects.filter(
            is_active=True, deleted_at__isnull=True, opening_balance__isnull=False,
        ).order_by("name"):
            if not register.opening_balance:
                continue
            chart_acc = ChartOfAccount.objects.filter(
                linked_cash_register=register, is_active=True, deleted_at__isnull=True,
            ).first()
            if not chart_acc:
                self.stdout.write(self.style.WARNING(
                    f"  - {register.name}: pas de 571.x lie -> skip"
                ))
                continue

            reference = f"AN-2026-{chart_acc.code}"
            label = f"A-nouveau {register.name} au {OPENING_DATE.isoformat()}"
            existing = JournalEntry.objects.filter(reference=reference).first()
            if existing:
                existing.lines.all().delete()
                existing.delete()
                regenerated += 1

            entry = JournalEntry.objects.create(
                entry_date=OPENING_DATE, reference=reference, label=label, posted=True,
            )
            JournalLine.objects.create(
                entry=entry, account=chart_acc,
                debit=register.opening_balance, credit=Decimal("0"), label=label,
            )
            JournalLine.objects.create(
                entry=entry, account=report_a_nouveau,
                debit=Decimal("0"), credit=register.opening_balance, label=label,
            )
            created += 1
            total_balance += register.opening_balance
            self.stdout.write(
                f"  + {chart_acc.code:8} {register.name:35} | {register.opening_balance:>15.0f} XOF"
            )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Ecritures d'a-nouveau 01/01/2026 : {created} entrees creees ({regenerated} regenerees)."
        ))
        self.stdout.write(self.style.SUCCESS(
            f"Total soldes d'ouverture : {total_balance:>15.0f} XOF"
        ))
        self.stdout.write(self.style.SUCCESS(
            f"Contrepartie : 1211 Report a nouveau excedents-resultat (credit total)."
        ))
